// The launcher owns stdin. EOF also stops the daemon if the launcher crashes.
import {spawn} from 'node:child_process'
import {fileURLToPath} from 'node:url'

if (process.argv[2] === 'phoenixd') {
  const daemon = spawn(
    fileURLToPath(new URL('./phoenixd', import.meta.url)),
    [
      '--http-bind-ip=127.0.0.1',
      `--http-bind-port=${process.env.LNBITS_DAEMON_PORT}`,
      '--agree-to-terms-of-service'
    ],
    {stdio: ['ignore', 'inherit', 'inherit']}
  )
  let stopping = false
  const stop = () => {
    if (stopping) return
    stopping = true
    daemon.kill('SIGTERM')
    setTimeout(() => daemon.kill('SIGKILL'), 15000).unref()
  }
  process.stdin.on('end', stop)
  process.on('SIGINT', stop)
  process.on('SIGTERM', stop)
  daemon.on('error', () => process.exit(1))
  daemon.on('exit', code => process.exit(code ?? 1))
} else if (process.argv[2] === 'spark') {
  await import('./spark/server.mjs')
  // Emitting the event runs the existing cleanup handler on Windows too.
  process.stdin.on('end', () => process.emit('SIGTERM'))
} else {
  process.exit(2)
}
process.stdin.resume()
