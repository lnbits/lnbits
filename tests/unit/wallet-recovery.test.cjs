const assert = require('node:assert/strict')
const {readFileSync} = require('node:fs')
const {resolve} = require('node:path')
const {test} = require('node:test')
const vm = require('node:vm')
const Vue = require('vue')

function harness(getAuthenticatedUser) {
  const window = {app: {component: (_, value) => (window.component = value)}}
  const timers = new Map()
  const listeners = new Map()
  const sockets = []
  const document = {
    hidden: false,
    addEventListener: (name, fn) => listeners.set(name, fn),
    removeEventListener: name => listeners.delete(name)
  }
  const context = {
    window,
    document,
    console,
    LNbits: {api: {getAuthenticatedUser}},
    websocketUrl: 'wss://wallet.test/api/v1/ws',
    setTimeout: (fn, delay) => {
      const id = Symbol()
      timers.set(id, {fn, delay})
      return id
    },
    clearTimeout: id => timers.delete(id),
    WebSocket: class {
      constructor() {
        sockets.push(this)
      }
    }
  }
  for (const file of [
    'components/lnbits-manage-wallet-list.js',
    'components/lnbits-payment-list.js',
    'pages/wallet.js'
  ]) {
    vm.runInNewContext(
      readFileSync(resolve(__dirname, '../../lnbits/static/js', file), 'utf8'),
      context
    )
    if (file.includes('manage-wallet')) window.walletList = window.component
  }
  const wallet = {id: 'wallet-1', inkey: 'key', msat: 1000, sat: 1}
  const g = Vue.reactive({
    user: {wallets: [wallet]},
    wallet,
    offline: true,
    walletEventListeners: [],
    updatePayments: false,
    updatePaymentsHash: false
  })
  const definition = window.walletList
  const instance = {...definition.data(), g, maxWallets: 10}
  for (const [name, fn] of Object.entries(definition.methods)) {
    instance[name] = fn.bind(instance)
  }
  const page = {g, parse: {show: true}}
  let fetched = 0
  Vue.watch(
    () => g.updatePayments,
    () => {
      window.PageWallet.watch['g.updatePayments'].call(page)
      window.component.watch['g.updatePayments'].call({
        fetchPayments: () => fetched++
      })
    },
    {flush: 'sync'}
  )
  Vue.watch(() => g.offline, definition.watch['g.offline'].bind(instance), {
    flush: 'sync'
  })
  definition.mounted.call(instance)
  return {
    instance,
    g,
    page,
    document,
    sockets,
    timers,
    listeners,
    fetched: () => fetched,
    unmount: () => definition.beforeUnmount.call(instance),
    async flush() {
      const jobs = [...timers.values()]
      timers.clear()
      for (const job of jobs) await job.fn()
    }
  }
}

test('socket open and reconnect refresh history even with an unchanged balance', async () => {
  let requests = 0
  const h = harness(async () => {
    requests++
    return {data: {wallets: [{id: 'wallet-1', balance_msat: 1000}]}}
  })
  h.instance.paymentEvents()
  h.sockets[0].onopen()
  h.sockets[0].onopen()
  assert.equal(h.timers.size, 1)
  assert.equal([...h.timers.values()][0].delay, 500)
  await h.flush()
  assert.equal(requests, 1)
  assert.equal(h.fetched(), 1)
  assert.equal(h.page.parse.show, true)
  assert.equal(h.g.updatePaymentsHash, false)

  h.sockets[0].onclose()
  await h.flush()
  h.sockets[1].onopen()
  await h.flush()
  assert.equal(requests, 2)
  assert.equal(h.fetched(), 2)
})

test('visibility and existing online state refresh balances without closing Send', async () => {
  const h = harness(async () => ({
    data: {wallets: [{id: 'wallet-1', balance_msat: 2500}]}
  }))
  h.document.hidden = true
  h.listeners.get('visibilitychange')()
  assert.equal(h.timers.size, 0)
  h.document.hidden = false
  h.listeners.get('visibilitychange')()
  h.g.offline = false
  assert.equal(h.timers.size, 1)
  await h.flush()
  assert.equal(h.g.wallet.msat, 2500)
  assert.equal(h.g.user.wallets[0].sat, 2)
  assert.equal(h.fetched(), 1)
  assert.equal(h.page.parse.show, true)
  h.instance.scheduleWalletRefresh()
  h.unmount()
  assert.equal(h.timers.size, 0)
  assert.equal(h.listeners.size, 0)
})

test('a recovery trigger during a request waits and queues one fresh snapshot', async () => {
  let finish
  let requests = 0
  const h = harness(() => {
    requests++
    return new Promise(resolve => (finish = resolve))
  })
  const pending = h.instance.refreshWallets()
  h.instance.scheduleWalletRefresh()
  const recovery = h.flush()
  const repeated = h.instance.refreshWallets()
  let recovered = false
  recovery.then(() => (recovered = true))
  await Promise.resolve()
  assert.equal(recovered, false)
  assert.equal(requests, 1)
  finish({data: {wallets: [{id: 'wallet-1', balance_msat: 1000}]}})
  await Promise.all([pending, recovery, repeated])
  assert.equal(h.instance.walletRefreshPromise, null)
  assert.equal(h.timers.size, 1)
  assert.equal([...h.timers.values()][0].delay, 500)
  const next = h.flush()
  assert.equal(requests, 2)
  finish({data: {wallets: [{id: 'wallet-1', balance_msat: 2500}]}})
  await next
  assert.equal(h.g.wallet.msat, 2500)
  assert.equal(h.timers.size, 0)
})
