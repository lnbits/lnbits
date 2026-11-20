const assert = require('node:assert/strict')
const {readFileSync} = require('node:fs')
const {resolve} = require('node:path')
const {test} = require('node:test')
const vm = require('node:vm')
const {createSSRApp, h} = require('vue')
const {renderToString} = require('vue/server-renderer')

function harness() {
  let component
  let confirm
  const requests = []
  const notices = []
  const errors = []
  const freshUser = {
    wallets: [{id: 'wallet', adminkey: 'new', inkey: 'new-in'}]
  }
  const api = {
    async request(...args) {
      requests.push(args)
      return {data: {wallets_updated: 42}}
    },
    async getAuthUser() {
      return {data: freshUser}
    }
  }
  vm.runInNewContext(
    readFileSync(
      resolve(
        __dirname,
        '../../lnbits/static/js/components/admin/lnbits-admin-users.js'
      ),
      'utf8'
    ),
    {
      window: {app: {component: (_, value) => (component = value)}},
      LNbits: {
        api,
        map: {user: value => value},
        utils: {
          confirmDialog: () => ({onOk: callback => (confirm = callback)}),
          notifyApiError: error => errors.push(error)
        }
      },
      Quasar: {Notify: {create: notice => notices.push(notice)}}
    }
  )
  const instance = {
    ...component.data(),
    isSuperUser: true,
    g: {
      user: {wallets: [{id: 'wallet', adminkey: 'old'}]},
      wallet: {id: 'wallet', adminkey: 'old'}
    }
  }
  for (const [name, method] of Object.entries(component.methods)) {
    instance[name] = method.bind(instance)
  }
  return {
    component,
    instance,
    api,
    requests,
    notices,
    errors,
    freshUser,
    confirm: () => confirm?.()
  }
}

test('the reset button is rendered only for the superuser', async () => {
  const {component} = harness()
  const template = readFileSync(
    resolve(__dirname, '../../lnbits/templates/components/admin/users.vue'),
    'utf8'
  )
    .replace(/^<template[^>]*>/, '')
    .replace(/<\/template>\s*$/, '')
  for (const isSuperUser of [false, true]) {
    const app = createSSRApp(
      {...component, template},
      {formData: {}, isSuperUser}
    )
    app.config.globalProperties.$t = key => key
    app.directive('ripple', {})
    for (const [, name] of template.matchAll(/<(q-[\w-]+)/g)) {
      if (app.component(name)) continue
      app.component(name, {
        props: ['label'],
        setup:
          (props, {slots}) =>
          () =>
            h(name === 'q-btn' ? 'button' : 'div', [
              props.label,
              slots.default?.()
            ])
      })
    }
    const html = await renderToString(app)
    assert.equal(html.includes('Reset Wallet Keys'), isSuperUser)
  }
})

test('reset requires both the superuser and confirmation', async () => {
  const h = harness()
  h.instance.isSuperUser = false
  h.instance.resetWalletKeys()
  await h.confirm()
  assert.equal(h.requests.length, 0)
  h.instance.isSuperUser = true
  h.instance.resetWalletKeys()
  // Dismissing the dialog never calls its onOk callback.
  assert.equal(h.requests.length, 0)
})

test('confirmed reset prevents duplicate requests and refreshes wallet keys', async () => {
  const h = harness()
  h.instance.resetWalletKeys()
  const pending = h.confirm()
  assert.equal(h.instance.resettingWalletKeys, true)
  await h.confirm()
  await pending
  assert.deepEqual(h.requests, [['POST', '/admin/api/v1/wallets/reset-keys']])
  assert.equal(h.instance.resettingWalletKeys, false)
  assert.equal(h.instance.g.user, h.freshUser)
  assert.equal(h.instance.g.wallet, h.freshUser.wallets[0])
  assert.equal(h.notices[0].message, 'Keys reset for 42 wallets.')
  assert.equal(h.errors.length, 0)
})

test('reset failure preserves local keys and allows retry', async () => {
  const h = harness()
  const error = new Error('request failed')
  h.api.request = async () => {
    throw error
  }
  h.instance.resetWalletKeys()
  await h.confirm()
  assert.equal(h.instance.resettingWalletKeys, false)
  assert.equal(h.instance.g.wallet.adminkey, 'old')
  assert.deepEqual(h.errors, [error])
  assert.equal(h.notices.length, 0)
})

test('refresh failure still reports the completed reset and asks for reload', async () => {
  const h = harness()
  h.api.getAuthUser = async () => {
    throw new Error('refresh failed')
  }
  h.instance.resetWalletKeys()
  await h.confirm()
  assert.equal(h.instance.resettingWalletKeys, false)
  assert.deepEqual(
    h.notices.map(notice => notice.type),
    ['positive', 'warning']
  )
  assert.match(h.notices[1].message, /Reload/)
  assert.equal(h.errors.length, 0)
})
