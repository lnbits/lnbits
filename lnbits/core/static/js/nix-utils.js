function initNix() {
  const indentSpaceCount = 2
  const typesMap = {
    attrs: 'attrs',
    float: 'number',
    bool: 'bool',
    enum: 'select',
    lines: 'text',
    package: 'str',
    path: 'str',
    port: 'number',
    str: 'str'
  }

  function handleData(data, depth = indentSpaceCount) {
    const lines = data.split('\n')
    const nextDepth = depth + indentSpaceCount
    const result = {
      service: '',
      options: []
    }
    for (let i = 0; i < lines.length; i++) {
      const optionsLines = extractObject(lines.slice(i + 1), nextDepth)
      const servicesPrefix = nested('options.', depth)
      if (lines[i].startsWith(servicesPrefix)) {
        result.service = lines[i].substring(servicesPrefix.length).split(' ')[0]
        handleOptions(result.options, optionsLines, nextDepth)
        return result
      }
      if (lines[i].startsWith(nested('options', depth))) {
        return handleService(optionsLines, nextDepth)
      }
    }
    return result
  }

  function handleService(lines, depth) {
    const nextDepth = depth + indentSpaceCount
    const result = {
      service: '',
      options: []
    }
    const serviceNamePrefix = nested('services.', depth)
    for (let i = 0; i < lines.length; i++) {
      if (lines[i].startsWith(serviceNamePrefix)) {
        result.service = lines[i]
          .substring(serviceNamePrefix.length)
          .split(' ')[0]
      }
      if (lines[i].endsWith(' mkOption {')) {
        handleOptions(result.options, lines.slice(i), nextDepth)
        return result
      }
      const optionsLines = extractObject(lines.slice(i + 1), nextDepth)
      handleOptions(result.options, optionsLines, nextDepth)
      return result
    }
    return result
  }

  function handleOptions(options, lines, depth) {
    const nextDepth = depth + indentSpaceCount
    for (let i = 0; i < lines.length; i++) {
      if (lines[i].endsWith(' mkOption {')) {
        const optionLines = extractObject(lines.slice(i + 1), nextDepth)
        const option = extractOption(optionLines, nextDepth)
        option.name = lines[i].trim().split(' ')[0].split('.').slice(-1)[0]
        options.push(option)
        i += optionLines.length
      } else if (lines[i].endsWith(' = {')) {
        const option = {
          name: lines[i].trim().split(' ')[0],
          options: []
        }
        const nestedObject = extractObject(lines.slice(i + 1), nextDepth)
        handleOptions(option.options, nestedObject, nextDepth)
        if (option.options.length) {
          options.push(option)
        }
        i += nestedObject.length
      }
    }
  }

  function extractOption(lines, depth) {
    const nextDepth = depth + indentSpaceCount
    const op = {}
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i].trim()
      if (line.startsWith(`description = mdDoc "`)) {
        op.description = line.slice(
          `description = mdDoc "`.length,
          line.length - 2
        )
      } else if (
        line.startsWith(`description = mdDoc ''`) ||
        line.startsWith(`description = ''`)
      ) {
        const longDescriptionLines = extractObject(
          lines.slice(i + 1),
          nextDepth
        )
        op.description = longDescriptionLines.map(l => l.trim()).join('\n')
        i += longDescriptionLines
      } else if (line.startsWith('type =') && line.endsWith(';')) {
        // todo: handle with types
        const types = line
          .substring('type ='.length + 1, line.length - 1)
          .split(' ')
          .join(';')
          .split('[')
          .join(';')
          .split(']')
          .join(';')
          .split('(')
          .join(';')
          .split(')')
          .join(';')
          .split(';')
          .filter(v => v.length)
          .map(t => (t.startsWith('types.') ? t.slice('types.'.length) : t))

        op.isList = types.includes('listOf')
        op.isOptional = types.includes('nullOr')
        const enumIndex = types.indexOf('enum')
        if (enumIndex !== -1) {
          op.values = types.slice(enumIndex + 1).map(v => extractValue(v))
        }
        if (types.find(t => t.startsWith('ints.'))) {
          op.type = 'number'
        } else {
          const type = types.find(t => typesMap[t])
          op.type = type ? typesMap[type] : 'str'
        }
      } else if (line.startsWith('default =') && line.endsWith(';')) {
        const value = extractValue(
          line.slice('default ='.length, line.length - 1).trim()
        )
        if (value !== undefined) {
          op.default = value
        }
      }
    }

    return op
  }
  function extractValue(value) {
    if (!Number.isNaN(+value)) {
      return +value
    } else if (value === 'true' || value === 'false') {
      return value === 'true'
    } else if (value.startsWith('"') && value.endsWith('"')) {
      return value.slice(1, value.length - 1)
    } else if (value.startsWith('[') && value.endsWith(']')) {
      return value
        .slice(1, value.length - 1)
        .split(' ')
        .filter(v => v !== '')
        .map(v => extractValue(v))
    }
  }

  function extractObject(lines, nestingLevel) {
    const prefix = nested('', nestingLevel)
    const objectLines = []
    for (const line of lines) {
      if (!line.length || line.startsWith(prefix)) {
        objectLines.push(line)
      } else {
        return objectLines
      }
    }
    return objectLines
  }

  function nested(str, level) {
    const prefix = Array(level).fill(' ').join('')
    return prefix + str
  }

  return handleData
}
var nixConfigToJson = initNix()
