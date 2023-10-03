console.log('### play.js')

const fs = require('fs')

const data = fs.readFileSync('sample.config.nix', 'utf8')
const lines = data.split('\n')
console.log('### data', lines.length)

const optionsPrefix = '  options ='
const serviceNamePrefix = '    services.'

const result = {
  service: ''
}

for (let i = 0; i < lines.length; i++) {
  if (lines[i].startsWith(optionsPrefix)) {
    handleService(extractObject(lines.slice(i + 1), 4))
  }
}

function handleService(lines) {
  for (let i = 0; i < lines.length; i++) {
    if (lines[i].startsWith(serviceNamePrefix)) {
      result.service = lines[i]
        .substring(serviceNamePrefix.length)
        .split(' ')[0]
    }
    handleOptions(extractObject(lines.slice(i + 1), 4))
    return
  }
}

function handleOptions(lines) {
    console.log('### lines', lines.join('\n'))
}

function extractObject(lines, nestingLevel) {
  const prefix = Array(nestingLevel).fill(' ').join('')
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

console.log('### result', result)
