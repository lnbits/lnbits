const assert = require('node:assert/strict')
const {readFileSync} = require('node:fs')
const {resolve} = require('node:path')
const {test} = require('node:test')
const vm = require('node:vm')

const LiveUpdates = vm.runInNewContext(
  readFileSync(
    resolve(__dirname, '../../lnbits/onchain/static/js/live-updates.js'),
    'utf8'
  ).replace('export class ', 'class ') + '\nOnchainLiveUpdates'
)

function harness(local = true) {
  let time = 0
  let next = 0
  const jobs = new Map()
  const sockets = []
  const listeners = new Map()
  const calls = {refresh: 0, scan: 0, clock: 0}
  const state = {local, scanning: false, addresses: ['address-one']}
  const schedule = (fn, delay, interval = false) => {
    const id = ++next
    jobs.set(id, {fn, time: time + delay, interval: interval ? delay : 0})
    return id
  }
  const browser = {
    document: {
      hidden: false,
      addEventListener: (name, fn) => listeners.set(name, fn),
      removeEventListener: name => listeners.delete(name)
    },
    location: {protocol: 'https:', host: 'wallet.test'},
    Date: {now: () => time},
    setTimeout: (fn, delay) => schedule(fn, delay),
    clearTimeout: id => jobs.delete(id),
    setInterval: (fn, delay) => schedule(fn, delay, true),
    clearInterval: id => jobs.delete(id),
    WebSocket: class {
      constructor(url) {
        this.url = url
        this.closed = false
        sockets.push(this)
      }
      close(code = 1000) {
        this.closed = true
        this.onclose?.({code})
      }
      message(value) {
        this.onmessage?.({data: JSON.stringify(value)})
      }
    }
  }
  const updates = new LiveUpdates(
    {
      localExplorer: () => state.local,
      scanning: () => state.scanning,
      addresses: () => state.addresses,
      refresh: async () => calls.refresh++,
      scan: async () => {
        calls.scan++
        state.scanning = true
      },
      clock: () => calls.clock++
    },
    browser
  )
  async function advance(milliseconds) {
    const end = time + milliseconds
    while (true) {
      const entry = [...jobs].sort((a, b) => a[1].time - b[1].time)[0]
      if (!entry || entry[1].time > end) break
      const [id, job] = entry
      time = job.time
      jobs.delete(id)
      if (job.interval) jobs.set(id, {...job, time: time + job.interval})
      await job.fn()
    }
    time = end
  }
  updates.start()
  return {updates, calls, state, browser, sockets, jobs, listeners, advance}
}

test('idle state polls once a minute; relative dates update without requests', async () => {
  const h = harness(false)
  assert.equal(h.sockets.length, 0)
  await h.advance(59000)
  assert.equal(h.calls.refresh, 0)
  assert.equal(h.calls.clock, 3)
  await h.advance(1000)
  assert.equal(h.calls.refresh, 1)
  await h.advance(120000)
  assert.equal(h.calls.refresh, 3)
  h.updates.stop()
})

test('existing block/address sockets coalesce activity and ignore duplicate messages', async () => {
  const h = harness()
  assert.deepEqual(
    h.sockets.map(s => s.url),
    [
      'wss://wallet.test/blockexplorer/api/v1/ws/blocks',
      'wss://wallet.test/blockexplorer/api/v1/ws/address/address-one'
    ]
  )
  h.sockets[0].message({height: 1})
  await h.advance(1000)
  assert.equal(h.calls.scan, 0)
  h.sockets[0].message({height: 2})
  h.sockets[1].message({confirmed: 100})
  h.sockets[1].message({confirmed: 100})
  await h.advance(1000)
  assert.equal(h.calls.scan, 1)
  h.sockets[1].message({confirmed: 100})
  await h.advance(9000)
  assert.equal(h.calls.refresh, 0)
  await h.advance(1000)
  assert.equal(h.calls.refresh, 1)
  assert.equal(h.calls.scan, 1)
  h.state.scanning = false
  h.updates.update()
  await h.advance(59000)
  assert.equal(h.calls.refresh, 1)
  await h.advance(1000)
  assert.equal(h.calls.refresh, 2)
  h.updates.stop()
})

test('hiding the page closes streams and pauses polling; returning refreshes once', async () => {
  const h = harness()
  h.sockets[1].message({confirmed: 100})
  h.browser.document.hidden = true
  h.listeners.get('visibilitychange')()
  assert.ok(h.sockets.every(s => s.closed))
  await h.advance(120000)
  assert.deepEqual(h.calls, {refresh: 0, scan: 0, clock: 0})
  h.browser.document.hidden = false
  h.listeners.get('visibilitychange')()
  await Promise.resolve()
  assert.equal(h.calls.refresh, 1)
  assert.equal(h.sockets.length, 4)
  h.updates.stop()
  assert.equal(h.jobs.size, 0)
  assert.equal(h.listeners.size, 0)
  await h.advance(120000)
  assert.equal(h.calls.refresh, 1)
})

test('connections are bounded and cleaned up when switching providers', async () => {
  const h = harness()
  h.state.addresses = Array.from({length: 50}, (_, i) => 'address-' + i)
  h.updates.update()
  assert.equal(h.sockets.filter(s => !s.closed).length, 9)
  h.state.local = false
  h.updates.update()
  assert.ok(h.sockets.every(s => s.closed))
  await h.advance(60000)
  assert.equal(h.calls.refresh, 1)
  assert.equal(h.updates.sockets.size, 0)
  h.updates.stop()
})

test('closed streams reconnect with backoff and a disabled explorer keeps fallback polling', async () => {
  const h = harness()
  h.sockets[0].close()
  await h.advance(4999)
  assert.equal(h.sockets.length, 2)
  await h.advance(1)
  assert.equal(h.sockets.length, 3)
  h.sockets[2].close()
  await h.advance(9999)
  assert.equal(h.sockets.length, 3)
  await h.advance(1)
  assert.equal(h.sockets.length, 4)
  h.sockets[3].close(1008)
  await h.advance(60000)
  assert.equal(h.sockets.length, 4)
  assert.equal(h.calls.refresh, 1)
  h.updates.stop()
})
