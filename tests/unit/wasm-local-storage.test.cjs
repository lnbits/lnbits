const assert = require('node:assert/strict')
const {readFileSync} = require('node:fs')
const {webcrypto} = require('node:crypto')
const {test} = require('node:test')
const vm = require('node:vm')

function harness() {
  const stored = new Map()
  let now = 1700000000000
  const window = {
    crypto: webcrypto,
    localStorage: {
      getItem: key => stored.get(key) ?? null,
      setItem: (key, value) => stored.set(key, value),
      removeItem: key => stored.delete(key)
    }
  }
  const context = {window, TextEncoder, Date: {now: () => now}}
  vm.runInNewContext(
    readFileSync('lnbits/static/js/wasm-extension-component.js', 'utf8'),
    context
  )
  const component = window.WasmExtensionComponent
  const instance = {
    ...component.data(),
    g: {user: {id: 'alice'}},
    $route: {path: '/ext/paywallwasm/one'}
  }
  for (const [name, method] of Object.entries(component.methods))
    instance[name] = method.bind(instance)
  instance.bridge.extensionId = 'paywallwasm'
  instance.bridge.permissions = ['ui.storage.local']
  const call = (action, value, key = 'receipt') =>
    instance.localBridgeStorage({action: 'storage.local.' + action, key, value})
  return {
    instance,
    stored,
    call,
    advance: delta => {
      now += delta
    }
  }
}

test('remembered receipts are isolated by page, extension and account, including anonymous visitors', async () => {
  const {instance, stored, call} = harness()
  await call('set', 'opaque-token')
  assert.equal((await call('get')).value, 'opaque-token')
  instance.$route.path = '/ext/paywallwasm/two'
  assert.equal((await call('get')).value, '')
  instance.$route.path = '/ext/paywallwasm/one'
  instance.g.user.id = 'bob'
  assert.equal((await call('get')).value, '')
  instance.g.user = null
  assert.equal((await call('get')).value, '')
  await call('set', 'anonymous-receipt')
  instance.g.user = {id: 'alice'}
  assert.equal((await call('get')).value, 'opaque-token')
  instance.bridge.extensionId = 'other'
  assert.equal((await call('get')).value, '')
  instance.bridge.extensionId = 'paywallwasm'
  await call('remove')
  assert.equal((await call('get')).value, '')
  assert.ok([...stored.keys()].every(key => !key.includes('alice')))
})

test('permission checks, key/value limits and account changes fail closed', async () => {
  const {instance, stored, call} = harness()
  instance.bridge.permissions = []
  await assert.rejects(call('set', 'token'), /not permitted/)
  instance.bridge.permissions = ['ui.storage.local']
  for (const key of ['', 'a/b', 'x'.repeat(129)])
    await assert.rejects(call('get', '', key), /Invalid/)
  for (const value of ['x'.repeat(1025), {}, null])
    await assert.rejects(call('set', value), /invalid/)
  const pending = call('set', 'token')
  instance.g.user.id = 'bob'
  await assert.rejects(pending, /context changed/)
  assert.equal(stored.size, 0)
})

test('receipts expire without reads extending their life; corrupt cache is discarded', async () => {
  const {call, stored, advance} = harness()
  await call('set', 'token')
  advance(179 * 86400000)
  assert.equal((await call('get')).value, 'token')
  advance(86400001)
  assert.equal((await call('get')).value, '')
  assert.equal(stored.size, 0)
  await call('set', 'token')
  const key = [...stored.keys()][0]
  stored.set(key, '{bad json')
  assert.equal((await call('get')).value, '')
})

test('quotas cover all pages within an extension/account and reject oversized writes atomically', async () => {
  const {instance, call, stored} = harness()
  for (let i = 0; i < 128; i++) {
    instance.$route.path = '/ext/paywallwasm/' + i
    await call('set', 'token')
  }
  const before = [...stored.values()][0]
  instance.$route.path = '/ext/paywallwasm/overflow'
  await assert.rejects(call('set', 'token'), /quota/)
  assert.equal([...stored.values()][0], before)
  const second = harness()
  for (let i = 0; i < 50; i++)
    await second.call('set', 'x'.repeat(1024), 'k' + i)
  await assert.rejects(async () => {
    for (let i = 50; i < 80; i++)
      await second.call('set', 'x'.repeat(1024), 'k' + i)
  }, /quota/)
})

test('the bridge routes only the three allowed storage actions', async () => {
  const {instance} = harness()
  const replies = []
  instance.sendResponse = (_, id, result) => replies.push({id, result})
  for (const [id, action] of ['set', 'get', 'remove'].entries()) {
    await instance.handleBridgeRequest(
      {
        type: 'lnbits-extension:request',
        id,
        action: 'storage.local.' + action,
        key: 'receipt',
        value: 'token'
      },
      {}
    )
  }
  assert.ok(replies.every(reply => reply.result.ok))
  assert.equal(replies[1].result.data.value, 'token')
})
