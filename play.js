console.log('### play.js')

const fs = require('fs')

const data = fs.readFileSync('sample.config6.nix', 'utf8')
const lines = data.split('\n')
console.log('### data', lines.length)

//nullOr, listOf
const typesMap = {
  attrs: 'attrs',
  float: 'number',
  bool: 'bool',
  enum: 'select',
  lines: 'text',
  package: 'str',
  path: 'str',
  port: 'str',
  str: 'str'
}

const indentSpaceCount = 2

const result = {
  service: '',
  options: []
}

handleData(lines, indentSpaceCount)

function handleData(lines, depth) {
  const nextDepth = depth + indentSpaceCount
  for (let i = 0; i < lines.length; i++) {
    const servicesPrefix = nested('options.services.', depth)
    if (lines[i].startsWith(servicesPrefix)) {
      result.service = lines[i].substring(servicesPrefix.length).split(' ')[0]
      handleOptions(
        result.options,
        extractObject(lines.slice(i + 1), nextDepth),
        nextDepth
      )
      return
    }
    if (lines[i].startsWith(nested('options', depth))) {
      handleService(extractObject(lines.slice(i + 1), nextDepth), nextDepth)
      return
    }
  }
}

function handleService(lines, depth) {
  const nextDepth = depth + indentSpaceCount
  const serviceNamePrefix = nested('services.', depth)
  for (let i = 0; i < lines.length; i++) {
    if (lines[i].startsWith(serviceNamePrefix)) {
      result.service = lines[i]
        .substring(serviceNamePrefix.length)
        .split(' ')[0]
    }
    handleOptions(
      result.options,
      extractObject(lines.slice(i + 1), nextDepth),
      nextDepth
    )
    return
  }
}

function handleOptions(options, lines, depth) {
  const nextDepth = depth + indentSpaceCount
  for (let i = 0; i < lines.length; i++) {
    if (lines[i].endsWith('= mkOption {')) {
      const optionLines = extractObject(lines.slice(i + 1), nextDepth)
      const option = extractOption(optionLines, nextDepth)
      option.name = lines[i].trim().split(' ')[0]
      options.push(option)
      // handle option
      //   console.log('### x', x)
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
      const longDescriptionLines = extractObject(lines.slice(i + 1), nextDepth)
      op.description = longDescriptionLines.map(l => l.trim()).join('\n')
      i += longDescriptionLines
    } else if (line.startsWith('type =') && line.endsWith(';')) {
      // todo: handle with types
      const types = line
        .substring('type ='.length + 1, line.length - 1)
        .split(' ')
        .map(t => (t.startsWith('types.') ? t.slice('types.'.length) : t))

      op.isList = types.includes('listOf')
      op.isOptional = types.includes('nullOr')
      if (types.find(t => t.startsWith('ints.'))) {
        op.type = 'number'
      } else {
        const type = types.find(t => typesMap[t])
        op.type = type ? typesMap[type] : 'str'
      }
    } else if (line.startsWith('default =') && line.endsWith(';')) {
      const value = line.slice('default ='.length, line.length - 1).trim()
      if (!Number.isNaN(+value)) {
        op.default = +value
      } else if (typeof value === 'boolean') {
        op.default = value
      } else if (value.startsWith(`"`) && value.endsWith(`"`)) {
        op.default = value.slice(1, value.length - 1)
      }
    }
  }

  return op
}

function extractObject(lines, nestingLevel) {
  const prefix = nested('', nestingLevel)
  const objectLines = []
  for (const line of lines) {
    if (line.startsWith(prefix)) {
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

console.log('### result', JSON.stringify(result, null, 2))
// console.log('### result', result)
