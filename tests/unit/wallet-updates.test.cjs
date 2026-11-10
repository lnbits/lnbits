const assert = require('node:assert/strict')
const {readFileSync} = require('node:fs')
const {resolve} = require('node:path')
const {test} = require('node:test')
const vm = require('node:vm')

function harness(getWallet) {
  let component
  const sockets = []
  const timers = []
  const reactions = []
  const warnings = []
  const wallet = {id: 'wallet', inkey: 'invoice-key', sat: 1}
  const context = {
    window: {app: {component: (_, value) => (component = value)}},
    LNbits: {api: {getWallet}},
    websocketUrl: 'wss://example.com/api/v1/ws',
    WebSocket: class {
      static OPEN = 1
      readyState = 1
      constructor(url) {
        this.url = url
        sockets.push(this)
      }
    },
    setTimeout: callback => timers.push(callback),
    clearTimeout() {},
    console: {log() {}, warn: (...args) => warnings.push(args)},
    eventReaction: amount => reactions.push(amount)
  }
  vm.runInNewContext(
    readFileSync(
      resolve(
        __dirname,
        '../../lnbits/static/js/components/lnbits-manage-wallet-list.js'
      ),
      'utf8'
    ),
    context
  )
  const instance = {
    ...component.data(),
    maxWallets: 10,
    g: {
      user: {wallets: [wallet]},
      wallet: {...wallet},
      walletEventListeners: [],
      updatePayments: false,
      updatePaymentsHash: false
    }
  }
  for (const [name, method] of Object.entries(component.methods)) {
    instance[name] = method.bind(instance)
  }
  instance.paymentEvents()
  return {instance, wallet, sockets, timers, reactions, warnings}
}

test('socket open and reconnect refresh balances and payments without a payment reaction', async () => {
  let balance = 21000
  const {instance, wallet, sockets, timers, reactions} = harness(
    async wallet => {
      assert.equal(wallet.inkey, 'invoice-key')
      return {data: {balance}}
    }
  )
  await sockets[0].onopen()
  assert.equal(wallet.sat, 21)
  assert.equal(instance.g.wallet.sat, 21)
  assert.equal(instance.g.updatePayments, true)
  assert.equal(instance.g.updatePaymentsHash, false)
  assert.deepEqual(reactions, [])

  sockets[0].onclose()
  // A payment arrives while disconnected; only the HTTP balance knows about it.
  balance = 42001
  timers.at(-1)()
  assert.equal(sockets.length, 2)
  await sockets[1].onopen()
  assert.equal(wallet.sat, 42)
  assert.equal(instance.g.wallet.sat, 42)
  assert.equal(instance.g.updatePayments, false)
  assert.equal(instance.g.updatePaymentsHash, false)
  assert.deepEqual(reactions, [])
})

test('refresh updates a background wallet without changing the active wallet', async () => {
  const {instance, wallet, sockets} = harness(async () => ({
    data: {balance: 0}
  }))
  instance.g.wallet = {id: 'other-wallet', sat: 100}
  await sockets[0].onopen()
  assert.equal(wallet.sat, 0)
  assert.equal(instance.g.wallet.sat, 100)
  assert.equal(instance.g.updatePayments, false)
})

test('a late HTTP snapshot cannot overwrite a live payment update', async () => {
  let finish
  const {instance, wallet, sockets, reactions} = harness(
    () => new Promise(resolve => (finish = resolve))
  )
  const refreshing = sockets[0].onopen()
  sockets[0].onmessage({
    data: JSON.stringify({
      wallet_balance: 42,
      payment: {wallet_id: wallet.id, amount: 21000}
    })
  })
  finish({data: {balance: 21000}})
  await refreshing
  assert.equal(wallet.sat, 42)
  assert.equal(instance.g.wallet.sat, 42)
  assert.equal(instance.g.updatePayments, true)
  assert.equal(instance.g.updatePaymentsHash, true)
  assert.deepEqual(reactions, [42000])
})

test('refresh failure is handled and the next connection retries', async () => {
  let fail = true
  const {instance, wallet, sockets, timers, warnings} = harness(async () => {
    if (fail) throw new Error('offline')
    return {data: {balance: 42000}}
  })
  await sockets[0].onopen()
  assert.equal(wallet.sat, 1)
  assert.equal(instance.g.updatePayments, false)
  assert.equal(warnings.length, 1)
  fail = false
  sockets[0].onclose()
  timers.at(-1)()
  await sockets[1].onopen()
  assert.equal(wallet.sat, 42)
  assert.equal(instance.g.updatePayments, true)
})
