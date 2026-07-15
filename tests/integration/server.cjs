const fs = require('fs')
const http = require('http')
const path = require('path')
const {spawn} = require('child_process')

const root = path.resolve(__dirname, '..', '..')
const host = process.env.HOST || '127.0.0.1'
const port = process.env.PORT || '5000'
const mirrorPort = process.env.MIRROR_PORT || '8500'
const dataFolder =
  process.env.LNBITS_DATA_FOLDER ||
  path.join(root, 'tests', 'data', 'integration')

if (process.env.LNBITS_INTEGRATION_RESET_DATA !== 'false') {
  fs.rmSync(dataFolder, {recursive: true, force: true})
}
fs.mkdirSync(dataFolder, {recursive: true})

const mirrorRequests = []

function readBody(req) {
  return new Promise((resolve, reject) => {
    const chunks = []
    req.on('data', chunk => chunks.push(chunk))
    req.on('error', reject)
    req.on('end', () => resolve(Buffer.concat(chunks).toString('utf8')))
  })
}

function parseBody(body) {
  if (!body) return null
  try {
    return JSON.parse(body)
  } catch {
    return body
  }
}

const mirror = http.createServer(async (req, res) => {
  const bodyText = await readBody(req)
  const body = parseBody(bodyText)
  const record = {
    method: req.method,
    url: req.url,
    headers: req.headers,
    body,
    bodyText,
    receivedAt: new Date().toISOString()
  }

  if (req.url === '/__mirror__/clear') {
    mirrorRequests.splice(0, mirrorRequests.length)
    res.writeHead(204)
    res.end()
    return
  }

  if (req.url === '/__mirror__/requests') {
    res.writeHead(200, {'content-type': 'application/json'})
    res.end(JSON.stringify(mirrorRequests))
    return
  }

  mirrorRequests.push(record)
  res.writeHead(200, {
    'content-type': 'application/json',
    h1: '1'
  })
  res.end(JSON.stringify(body ?? record))
})

mirror.listen(Number(mirrorPort), '127.0.0.1', () => {
  console.log(`Mirror server listening on http://127.0.0.1:${mirrorPort}`)
})

const env = {
  ...process.env,
  HOST: host,
  PORT: port,
  LNBITS_DATA_FOLDER: dataFolder,
  LNBITS_ADMIN_UI: process.env.LNBITS_ADMIN_UI || 'true',
  AUTH_HTTPS_ONLY: process.env.AUTH_HTTPS_ONLY || 'false',
  LNBITS_BACKEND_WALLET_CLASS:
    process.env.LNBITS_BACKEND_WALLET_CLASS || 'FakeWallet',
  LNBITS_EXTENSIONS_DEFAULT_INSTALL:
    process.env.LNBITS_EXTENSIONS_DEFAULT_INSTALL ||
    'watchonly,satspay,tipjar,tpos,lnurlp,withdraw'
}

const lnbits = spawn('uv', ['run', 'lnbits', '--host', host, '--port', port], {
  cwd: root,
  env,
  stdio: 'inherit'
})

function shutdown(signal) {
  mirror.close()
  if (!lnbits.killed) {
    lnbits.kill(signal)
  }
}

process.on('SIGINT', () => shutdown('SIGINT'))
process.on('SIGTERM', () => shutdown('SIGTERM'))

lnbits.on('exit', code => {
  mirror.close()
  process.exit(code ?? 0)
})
