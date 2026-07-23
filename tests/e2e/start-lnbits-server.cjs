const childProcess = require('node:child_process')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')

const rootDir = path.resolve(__dirname, '../..')
const baseUrl = new URL(
  process.env.LNBITS_E2E_BASE_URL ?? 'http://127.0.0.1:5009'
)
const host = baseUrl.hostname
const port = baseUrl.port || (baseUrl.protocol === 'https:' ? '443' : '80')
const dataDir =
  process.env.LNBITS_E2E_DATA_FOLDER ??
  fs.mkdtempSync(path.join(os.tmpdir(), 'lnbits-e2e-'))
const logDir = path.join(rootDir, 'test-results')
const logFile = path.join(logDir, 'lnbits-e2e-server.log')

fs.mkdirSync(dataDir, {recursive: true})
fs.mkdirSync(logDir, {recursive: true})

const log = fs.openSync(logFile, 'a')
const server = childProcess.spawn(
  'uv',
  [
    'run',
    'uvicorn',
    'lnbits.__main__:app',
    '--host',
    host,
    '--port',
    port,
    '--log-level',
    'warning'
  ],
  {
    cwd: rootDir,
    env: {
      ...process.env,
      AUTH_HTTPS_ONLY: 'false',
      DEBUG: 'true',
      HOST: host,
      LNBITS_ADMIN_UI: 'true',
      LNBITS_BACKEND_WALLET_CLASS: 'FakeWallet',
      LNBITS_DATA_FOLDER: dataDir,
      LNBITS_ENABLE_LOG_TO_FILE: 'false',
      LNBITS_EXTENSIONS_MANIFESTS: '[]',
      LNBITS_EXTENSIONS_PATH: dataDir,
      PORT: port,
      PYTHONUNBUFFERED: '1'
    },
    stdio: ['ignore', log, log]
  }
)

let shuttingDown = false

const shutdown = signal => {
  if (shuttingDown) return
  shuttingDown = true

  if (server.pid && server.exitCode === null) {
    try {
      server.kill(signal)
    } catch (_error) {}
  }

  setTimeout(() => {
    if (server.pid && server.exitCode === null) {
      try {
        server.kill('SIGKILL')
      } catch (_error) {}
    }
    process.exit(0)
  }, 15_000).unref()
}

process.on('SIGTERM', () => shutdown('SIGTERM'))
process.on('SIGINT', () => shutdown('SIGINT'))

server.on('exit', (code, signal) => {
  fs.closeSync(log)
  if (!shuttingDown) {
    process.exit(code ?? (signal ? 1 : 0))
  }
})
