const assert = require('node:assert/strict')
const {readFileSync} = require('node:fs')
const {test} = require('node:test')
const vm = require('node:vm')

function harness() {
  const messages = [],
    observed = []
  const colors = {
    '--q-primary': '#ea611d',
    '--q-secondary': '#e56f35',
    '--q-dark-page': '#2d293b',
    '--private-key': 'not-a-theme-value'
  }
  const classes = new Set(['gradient-bg'])
  const document = {
    body: {
      dataset: {theme: 'bitcoin'},
      classList: {contains: key => classes.has(key)}
    },
    documentElement: {}
  }
  let callback,
    disconnected = false
  const window = {
    getComputedStyle: () => ({getPropertyValue: name => colors[name] || ''}),
    removeEventListener() {}
  }
  const context = {
    window,
    document,
    CSS: {
      supports: (property, value) =>
        property === 'color' && /^#[0-9a-f]{6}$/i.test(value)
    },
    MutationObserver: class {
      constructor(handler) {
        callback = handler
      }
      observe(element, options) {
        observed.push({element, options})
      }
      disconnect() {
        disconnected = true
      }
    }
  }
  vm.runInNewContext(
    readFileSync('lnbits/static/js/wasm-extension-component.js', 'utf8'),
    context
  )
  const component = window.WasmExtensionComponent
  const instance = {...component.data(), $q: {dark: {isActive: true}}}
  for (const [name, method] of Object.entries(component.methods))
    instance[name] = method.bind(instance)
  instance.bridge = {...instance.bridge, extensionId: 'lnticketwasm'}
  instance.bridgePort = {
    postMessage: m => messages.push(JSON.parse(JSON.stringify(m))),
    close() {}
  }
  return {
    instance,
    component,
    messages,
    colors,
    classes,
    observed,
    document,
    mutate: () => callback(),
    disconnected: () => disconnected
  }
}

test('context supplies only selected theme fields and allowlisted valid colors', () => {
  const {instance, colors} = harness()
  colors['--q-negative'] = 'url(https://example.com/image)'
  colors['--q-info'] = 'x'.repeat(129)
  const context = instance.plainBridgeContext()
  assert.deepEqual(JSON.parse(JSON.stringify(context.theme)), {
    dark: true,
    name: 'bitcoin',
    gradient: true,
    colors: {primary: '#ea611d', secondary: '#e56f35', 'dark-page': '#2d293b'}
  })
  assert.equal(context.extensionId, 'lnticketwasm')
  assert.equal(context.public, false)
})

test('parent palette and dark-mode changes notify the existing port without duplicates', () => {
  const f = harness()
  f.component.mounted.call(f.instance)
  assert.equal(f.observed.length, 2)
  assert.deepEqual(Array.from(f.observed[0].options.attributeFilter), [
    'class',
    'style',
    'data-theme'
  ])
  f.mutate()
  f.mutate()
  assert.equal(f.messages.length, 1)
  f.colors['--q-primary'] = '#3ab77d'
  f.document.body.dataset.theme = 'mint'
  f.instance.$q.dark.isActive = false
  f.classes.clear()
  f.mutate()
  assert.equal(f.messages.length, 2)
  assert.equal(f.messages[1].type, 'lnbits-extension:event')
  assert.equal(f.messages[1].event, 'ui.theme')
  assert.equal(f.messages[1].data.colors.primary, '#3ab77d')
  assert.equal(f.messages[1].data.dark, false)
  assert.equal(f.messages[1].data.gradient, false)
  f.instance.closeBridgePort()
  f.colors['--q-primary'] = '#ff00ff'
  f.mutate()
  assert.equal(f.messages.length, 2)
  f.component.unmounted.call(f.instance)
  assert.equal(f.disconnected(), true)
})

test('the theme bridge does not accept guest theme mutations', async () => {
  const {instance} = harness(),
    responses = []
  await instance.handleBridgeRequest(
    {
      type: 'lnbits-extension:request',
      id: 'theme-change',
      action: 'ui.theme',
      data: {dark: false}
    },
    r => responses.push(r)
  )
  assert.equal(responses[0].ok, false)
  assert.equal(instance.$q.dark.isActive, true)
})
