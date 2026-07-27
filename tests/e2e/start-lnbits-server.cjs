const childProcess = require('node:child_process')
const crypto = require('node:crypto')
const fs = require('node:fs')
const http = require('node:http')
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
const logDir = path.join(rootDir, 'test-reports', 'test-results')
const logFile = path.join(logDir, 'lnbits-e2e-server.log')
const extensionFixtureUrl = new URL(
  process.env.LNBITS_E2E_EXTENSION_FIXTURE_URL ?? 'http://127.0.0.1:5010'
)

fs.mkdirSync(dataDir, {recursive: true})
fs.mkdirSync(logDir, {recursive: true})

const supportchatFixture = createSupportchatFixture(extensionFixtureUrl)
const wasmExtensionManifests = [
  ...(supportchatFixture
    ? [new URL('/manifest.json', extensionFixtureUrl).toString()]
    : []),
  'https://raw.githubusercontent.com/lnbits/lnbits-extensions-wasm/refs/heads/main/extensions.json'
]
const extensionFixtureServer = supportchatFixture
  ? http.createServer((request, response) => {
      const pathname = new URL(request.url ?? '/', extensionFixtureUrl).pathname
      const fixture = supportchatFixture.responses[pathname]
      if (!fixture) {
        response.writeHead(404, {'Content-Type': 'text/plain; charset=utf-8'})
        response.end('Not found')
        return
      }
      response.writeHead(200, {
        'Cache-Control': 'no-store',
        'Content-Type': fixture.contentType
      })
      response.end(fixture.body)
    })
  : null
extensionFixtureServer?.listen(
  Number(extensionFixtureUrl.port || 80),
  extensionFixtureUrl.hostname
)

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
      LNBITS_EXTENSIONS_PATH: dataDir,
      LNBITS_WASM_EXTENSIONS_MANIFESTS: JSON.stringify(wasmExtensionManifests),
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
  extensionFixtureServer?.close()

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
  extensionFixtureServer?.close()
  fs.closeSync(log)
  if (!shuttingDown) {
    process.exit(code ?? (signal ? 1 : 0))
  }
})

function createSupportchatFixture(fixtureUrl) {
  const sourceDir =
    process.env.LNBITS_E2E_SUPPORTCHAT_DIR ??
    path.join(rootDir, 'data', 'extensions', 'supportchat')
  if (!fs.existsSync(path.join(sourceDir, 'config.json'))) return null
  const config = JSON.parse(
    fs.readFileSync(path.join(sourceDir, 'config.json'), 'utf8')
  )
  const fixtureRoot = fs.mkdtempSync(
    path.join(os.tmpdir(), 'lnbits-supportchat-e2e-')
  )
  const archiveRootName = `supportchat-${config.version}`
  const archiveRoot = path.join(fixtureRoot, archiveRootName)
  fs.mkdirSync(archiveRoot, {recursive: true})

  for (const name of ['config.json', 'static', 'storage', 'ui', 'wasm']) {
    fs.cpSync(path.join(sourceDir, name), path.join(archiveRoot, name), {
      recursive: true
    })
  }

  const archivePath = path.join(fixtureRoot, 'supportchat.zip')
  const zipped = childProcess.spawnSync(
    'zip',
    ['-q', '-r', archivePath, archiveRootName],
    {
      cwd: fixtureRoot,
      encoding: 'utf8'
    }
  )
  if (zipped.status !== 0) {
    throw new Error(`Could not create supportchat fixture: ${zipped.stderr}`)
  }
  const archive = fs.readFileSync(archivePath)
  const hash = crypto.createHash('sha256').update(archive).digest('hex')
  const archiveUrl = new URL('/supportchat.zip', fixtureUrl).toString()
  const configUrl = new URL('/config.json', fixtureUrl).toString()
  const manifest = {
    extensions: [
      {
        id: 'supportchat',
        name: config.name,
        version: config.version,
        archive: archiveUrl,
        hash,
        repo: 'local-e2e',
        short_description: config.short_description,
        min_lnbits_version: config.min_lnbits_version,
        details_link: configUrl
      }
    ]
  }

  return {
    responses: {
      '/config.json': {
        body: Buffer.from(JSON.stringify(config)),
        contentType: 'application/json; charset=utf-8'
      },
      '/manifest.json': {
        body: Buffer.from(JSON.stringify(manifest)),
        contentType: 'application/json; charset=utf-8'
      },
      '/supportchat.zip': {
        body: archive,
        contentType: 'application/zip'
      }
    }
  }
}
