const assert = require('node:assert/strict')
const {readFileSync} = require('./source.cjs')
const {resolve} = require('node:path')
const {test} = require('node:test')
const vm = require('node:vm')

function component(file, globals = {}) {
  let definition
  vm.runInNewContext(readFileSync(resolve(__dirname, '../../', file), 'utf8'), {
    window: {app: {component: (_name, value) => (definition = value)}},
    console,
    ...globals
  })
  const instance = {...definition.data()}
  for (const [name, method] of Object.entries(definition.methods)) {
    instance[name] = method.bind(instance)
  }
  return {definition, instance}
}

function wallets() {
  const sockets = []
  const timers = new Map()
  let timerId = 0
  const h = component(
    'lnbits/static/js/components/lnbits-manage-wallet-list.js',
    {
      websocketUrl: 'wss://example.test/api/v1/ws',
      setTimeout: fn => {
        timers.set(++timerId, fn)
        return timerId
      },
      clearTimeout: id => timers.delete(id),
      WebSocket: class {
        constructor(url) {
          this.url = url
          sockets.push(this)
        }
        close() {
          this.closed = true
          this.onclose?.()
        }
      }
    }
  )
  h.instance.g = {
    user: {
      wallets: [
        {id: 'a', inkey: 'key-a'},
        {id: 'b', inkey: 'key-b'}
      ]
    },
    walletEventListeners: []
  }
  h.route = (path, id) =>
    h.definition.watch.$route.handler.call(h.instance, {path, params: {id}})
  return {...h, sockets, timers}
}

test('only the open wallet connects; switches, leaving, and unmount close it', () => {
  const h = wallets()
  h.route('/wallet/b', 'b')
  assert.equal(h.sockets.length, 1)
  assert.match(h.sockets[0].url, /key-b$/)
  h.instance.paymentEvents()
  assert.equal(h.sockets.length, 1)
  const staleClose = h.sockets[0].onclose
  h.route('/wallet/a', 'a')
  assert.equal(h.sockets[0].closed, true)
  staleClose()
  assert.equal(h.timers.size, 0)
  assert.equal(h.sockets.length, 2)
  h.route('/wallets')
  assert.equal(h.sockets[1].closed, true)
  h.route('/wallet/b', 'b')
  h.definition.beforeUnmount.call(h.instance)
  assert.equal(h.sockets[2].closed, true)
  assert.equal(h.timers.size, 0)
})

test('error and close schedule one retry; switching cancels the old retry', () => {
  const h = wallets()
  h.route('/wallet/a', 'a')
  const closed = h.sockets[0].onclose
  h.sockets[0].onerror()
  closed()
  assert.equal(h.timers.size, 1)
  const retry = [...h.timers.values()][0]
  h.timers.clear()
  retry()
  assert.equal(h.sockets.length, 2)
  h.sockets[1].onerror()
  h.route('/wallet/b', 'b')
  assert.equal(h.timers.size, 0)
  assert.match(h.sockets[2].url, /key-b$/)
  h.instance.g.user = null
  h.instance.paymentEvents()
  assert.equal(h.sockets[2].closed, true)
})

for (const failure of [false, true]) {
  test(`signing dialog closes and PIN clears after ${failure ? 'failure' : 'success'}`, async () => {
    const {instance: signer} = component(
      'lnbits/onchain/static/components/nostr-signer.js'
    )
    signer.ensureConnected = async () => {
      assert.equal(signer.dialog, false)
      assert.equal(signer.signingDialog, true)
    }
    signer.client = {
      sign: async () => {
        signer.pin = '123456'
        signer.pinRequired = true
        if (failure) throw new Error('Device rejected request')
        return 'signed-psbt'
      }
    }
    if (failure) {
      await assert.rejects(signer.signPsbt('psbt'), /Device rejected/)
    } else {
      assert.equal(await signer.signPsbt('psbt'), 'signed-psbt')
    }
    assert.equal(signer.dialog, false)
    assert.equal(signer.signingDialog, false)
    assert.equal(signer.signing, false)
    assert.equal(signer.pinRequired, false)
    assert.equal(signer.pin, '')
  })
}

test('saved pairing reconnects without opening pairing setup', async () => {
  const {instance: signer} = component(
    'lnbits/onchain/static/components/nostr-signer.js'
  )
  signer.hasPairing = () => true
  signer.connect = async () => {
    assert.equal(signer.dialog, false)
    signer.connected = true
    signer.client = {}
  }
  await signer.ensureConnected()
  assert.equal(signer.dialog, false)
})

test('wallet removal and credential changes release the current socket', () => {
  const h = wallets()
  h.route('/account')
  assert.equal(h.sockets.length, 0)
  h.route('/wallet/a', 'a')
  h.instance.g.user.wallets[0].inkey = 'replacement-key'
  h.instance.paymentEvents()
  assert.equal(h.sockets[0].closed, true)
  assert.match(h.sockets[1].url, /replacement-key$/)
  h.instance.g.user.wallets = []
  h.instance.paymentEvents()
  assert.equal(h.sockets[1].closed, true)
  assert.equal(h.timers.size, 0)
})
