const assert = require('node:assert/strict')
const {readFileSync} = require('node:fs')
const {resolve} = require('node:path')
const {test} = require('node:test')
const vm = require('node:vm')
const Vue = require('vue')

function harness() {
  const components = {}
  const calls = []
  const updates = []
  const state = {
    addresses: [],
    snapshots: [],
    scanning: false,
    checked_at: 0,
    balance_sat: 0
  }
  const context = {
    window: {app: {component: (name, value) => (components[name] = value)}},
    Vue,
    LNbits: {
      api: {
        async request(method, path) {
          calls.push(path)
          return {data: path.endsWith('/state') ? state : []}
        }
      },
      utils: {notifyApiError: assert.fail},
      onchain: {
        utils: {addressBalance: () => 0, satOrBtc: String},
        map: {mapAddressesData: address => address},
        OnchainLiveUpdates: class {
          constructor(options) {
            this.options = options
            this.running = false
            updates.push(this)
          }
          start() {
            this.running = true
          }
          update() {}
          stop() {
            this.running = false
          }
        }
      }
    },
    Quasar: {colors: {changeAlpha() {}, getPaletteColor() {}}},
    clearTimeout
  }
  for (const file of ['onchain/wallet.js', 'lnbits-wallet-charts.js']) {
    vm.runInNewContext(
      readFileSync(
        resolve(__dirname, '../../lnbits/static/js/components', file),
        'utf8'
      ),
      context
    )
  }
  const wallet = components['lnbits-onchain-wallet']
  const template = readFileSync(
    resolve(__dirname, '../../lnbits/templates/components/onchain/wallet.vue'),
    'utf8'
  ).replace(/^<template[^>]*>|<\/template>\s*$/g, '')
  wallet.render = Vue.compile(template)
  delete wallet.template
  const charts = components['lnbits-wallet-charts']
  charts.render = () => null
  delete charts.template

  // Render components in memory; no browser, network, or e2e runner is used.
  const element = () => ({children: [], parent: null})
  const remove = child => {
    const siblings = child.parent?.children
    if (siblings) siblings.splice(siblings.indexOf(child), 1)
    child.parent = null
  }
  const renderer = Vue.createRenderer({
    createElement: element,
    createText: element,
    createComment: element,
    setText() {},
    setElementText() {},
    patchProp() {},
    insert(child, parent, anchor) {
      remove(child)
      child.parent = parent
      const index = anchor ? parent.children.indexOf(anchor) : -1
      parent.children.splice(
        index < 0 ? parent.children.length : index,
        0,
        child
      )
    },
    remove,
    parentNode: child => child.parent,
    nextSibling: child =>
      child.parent?.children[child.parent.children.indexOf(child) + 1] || null
  })
  const app = renderer.createApp({
    render: () =>
      Vue.h(
        wallet,
        {},
        {
          'wallet-tools': () =>
            Vue.h(charts, {
              apiUrl: '/api/v1/onchain/stats/daily',
              paymentFilter: {},
              chartConfig: {}
            })
        }
      )
  })
  const stub = {
    render() {
      if (this.$attrs.modelValue === false) return null
      return Vue.h('div', this.$slots.default?.())
    }
  }
  const tags = new Set(
    [...template.matchAll(/<([a-z][\w]*-[\w-]+)/g)].map(m => m[1])
  )
  for (const tag of tags) {
    app.component(tag, {...stub})
  }
  app.directive('close-popup', {})
  app.config.globalProperties.g = {
    user: {wallets: [{}]},
    wallet: {id: 'wallet', inkey: 'read-key', adminkey: 'admin-key'}
  }
  app.config.globalProperties.$q = {
    screen: {gt: {sm: true}},
    notify: assert.fail
  }
  app.config.globalProperties.$t = key => key
  app.mount(element())
  const instance = app._instance.subTree.component.proxy
  return {app, instance, calls, updates, context, state}
}

test('onchain requests and live updates start only after setup and stop when cleared', async t => {
  const {app, instance, calls, updates} = harness()
  t.after(() => app.unmount())
  await instance.updateAccounts([])
  await instance.hydrateState()
  await instance.scanAllAddresses()
  assert.deepEqual(calls, [])
  assert.equal(updates.length, 0)

  const account = {id: 'wallet', onchain_wallet_kind: 'watch', onchain_meta: {}}
  await instance.updateAccounts([account])
  await Vue.nextTick()
  for (const path of ['/state', '/sync', '/stats/daily']) {
    assert.ok(calls.includes('/api/v1/onchain' + path), path)
  }
  assert.equal(updates.length, 1)
  assert.equal(updates[0].running, true)

  await instance.updateAccounts([])
  await Vue.nextTick()
  const count = calls.length
  // Already queued callbacks must also become harmless after clearing setup.
  await updates[0].options.refresh()
  await updates[0].options.scan()
  assert.equal(calls.length, count)
  assert.equal(updates[0].running, false)
  assert.equal(instance.scan.scanning, false)

  await instance.updateAccounts([account])
  await Vue.nextTick()
  assert.equal(updates[1].running, true)
  assert.equal(calls.filter(path => path.endsWith('/stats/daily')).length, 2)
})

test('clearing setup during a state request prevents a follow-up scan', async t => {
  const {app, instance, context, state, calls, updates} = harness()
  t.after(() => app.unmount())
  await instance.updateAccounts([
    {id: 'wallet', onchain_wallet_kind: 'watch', onchain_meta: {}}
  ])
  calls.length = 0
  let finish
  context.LNbits.api.request = async (method, path) => {
    calls.push(path)
    return new Promise(resolve => {
      finish = resolve
    })
  }
  const scan = instance.scanAllAddresses()
  await instance.updateAccounts([])
  await Vue.nextTick()
  finish({data: {...state, scanning: true, balance_sat: 100}})
  await scan
  assert.deepEqual(calls, ['/api/v1/onchain/state'])
  assert.equal(instance.scan.scanning, false)
  assert.equal(instance.g.wallet.sat, 0)
  assert.equal(updates[0].running, false)
})
