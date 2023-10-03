console.log('### play.js')

const fs = require('fs')

const data = fs.readFileSync('sample.config.nix', 'utf8')
const lines = data.split('\n')
console.log('### data', lines.length)

const indentSpaceCount = 2

const result = {
  service: ''
}

handleData(lines, indentSpaceCount)

function handleData(lines, depth) {
  const nextDepth = depth + indentSpaceCount
  for (let i = 0; i < lines.length; i++) {
    const servicesPrefix = nested('options.services.', depth)
    if (lines[i].startsWith(servicesPrefix)) {
      result.service = lines[i].substring(servicesPrefix.length).split(' ')[0]
      handleOptions(extractObject(lines.slice(i + 1), nextDepth), nextDepth)
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
    handleOptions(extractObject(lines.slice(i + 1), nextDepth), nextDepth)
    return
  }
}

function handleOptions(lines, depth) {
  console.log('### option.lines', lines.length, depth)
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

console.log('### result', result)
