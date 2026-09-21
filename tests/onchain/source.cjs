const {readFileSync} = require('node:fs')
// The VM exercises hardware byte streams without a browser. Browser tests load
// the original ES modules, including their real dependency graph.
exports.readFileSync = (path, encoding) =>
  readFileSync(path, encoding)
    .replace(/^import[\s\S]*?from ['"][^'"]+['"]\n/gm, '')
    .replace(/^export (const|function) /gm, '$1 ')
