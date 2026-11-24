const assert = require('node:assert/strict')
const {readFileSync} = require('node:fs')
const {test} = require('node:test')
const vm = require('node:vm')
const {webcrypto} = require('node:crypto')

class Element {
  constructor(tag) {
    this.tag = tag
    this.children = []
    this.style = {}
    this.currentTime = 0
  }
  append(...children) {
    this.children.push(...children)
  }
  prepend(child) {
    this.children.unshift(child)
  }
  remove() {
    this.removed = true
  }
  showModal() {
    this.open = true
  }
  close() {
    this.open = false
  }
  play() {
    return Promise.resolve()
  }
  pause() {
    this.paused = true
  }
  load() {}
  removeAttribute() {}
}
const tick = () => new Promise(resolve => setImmediate(resolve))
function harness(overrides = {}) {
  const messages = [],
    sockets = [],
    tracks = []
  let captures = 0,
    screens = 0,
    destroyed = 0
  const document = {
    body: new Element('body'),
    createElement: tag => new Element(tag)
  }
  class Socket {
    static OPEN = 1
    static CLOSED = 3
    constructor(url, protocols) {
      this.url = url
      this.protocols = protocols
      this.bufferedAmount = 0
      this.readyState = 0
      sockets.push(this)
    }
    send(data) {
      this.sent = data
    }
    close() {
      this.closed = true
      this.readyState = 3
      this.onclose?.({code: 1000})
    }
  }
  function stream() {
    const track = {
      stop() {
        this.stopped = true
      },
      addEventListener(name, fn) {
        this[name] = fn
      }
    }
    tracks.push(track)
    return {
      getTracks: () => [track],
      getVideoTracks: () => [track],
      getAudioTracks: () => []
    }
  }
  class Recorder {
    static isTypeSupported() {
      return true
    }
    constructor(stream, options) {
      this.stream = stream
      this.mimeType = options.mimeType
      this.state = 'inactive'
    }
    start() {
      this.state = 'recording'
    }
    stop() {
      this.state = 'inactive'
    }
  }
  const policy = {
    permissions: {
      'ui.network.https': ['https://relay.example', 'https://another.example'],
      'ui.network.websocket': ['wss://relay.example', 'wss://another.example'],
      'ui.media.camera': [],
      'ui.media.microphone': [],
      'ui.media.screen': [],
      'ui.media.playback': []
    }
  }
  const context = {
    window: {
      location: {hostname: 'lnbits.example'},
      isSecureContext: true,
      MediaRecorder: Recorder,
      addEventListener() {},
      removeEventListener() {}
    },
    document,
    navigator: {
      mediaDevices: {
        getUserMedia: () => {
          captures++
          return Promise.resolve(stream())
        },
        getDisplayMedia: () => {
          screens++
          return Promise.resolve(stream())
        }
      }
    },
    MediaRecorder: Recorder,
    WebSocket: Socket,
    URL,
    ArrayBuffer,
    Uint8Array,
    Blob,
    AbortController,
    crypto: webcrypto,
    setTimeout,
    clearTimeout,
    setInterval: () => 1,
    clearInterval() {},
    ...overrides
  }
  vm.runInNewContext(
    readFileSync('lnbits/static/js/wasm-browser.js', 'utf8'),
    context
  )
  const session = new context.window.LNbitsBrowserSession({
    port: {
      start() {},
      close() {},
      postMessage: (message, transfer) => messages.push({message, transfer})
    },
    extensionId: 'demo',
    extensionName: 'Demo',
    surface: new Element('div'),
    readPolicy: async () => policy,
    destroyFrame: () => {
      destroyed++
    }
  })
  session.permissions = policy.permissions
  session.policyTime = Date.now()
  const decide = approved => {
    assert.ok(session.prompt)
    const buttons = session.prompt.dialog.children.filter(
      child => child.tag === 'button'
    )
    buttons[approved ? 1 : 0].onclick()
  }
  return {
    session,
    policy,
    context,
    decide,
    messages,
    sockets,
    tracks,
    stream,
    counts: () => ({captures, screens, destroyed})
  }
}

test('approval batches capabilities; grants are reused only for this capability and origin', async () => {
  const h = harness(),
    request = {
      capability: 'ui.network.websocket',
      destination: 'wss://relay.example/relay'
    }
  const pending = h.session.authorize([
    request,
    {capability: 'ui.media.camera'}
  ])
  assert.equal(h.session.grants.size, 0)
  assert.match(h.session.prompt.dialog.children[1].textContent, /Demo \(demo\)/)
  assert.match(
    h.session.prompt.dialog.children[2].children[0].textContent,
    /wss:\/\/relay.example/
  )
  h.decide(true)
  await pending
  await h.session.authorize([request])
  assert.equal(h.session.prompt, null)
  const extra = h.session.authorize([
    {...request, destination: 'wss://another.example/relay'}
  ])
  h.decide(false)
  await assert.rejects(extra, {code: 'user_denied'})
  const microphone = h.session.authorize([{capability: 'ui.media.microphone'}])
  h.decide(false)
  await assert.rejects(microphone, {code: 'user_denied'})
  assert.equal(harness().session.grants.size, 0)
  h.session.close()
})

test('denial, cancellation, and policy denial do not start capture or networking', async () => {
  const h = harness()
  const denied = h.session.capture({camera: true})
  h.decide(false)
  await assert.rejects(denied, {code: 'user_denied'})
  const cancelled = h.session.capture({microphone: true})
  h.session.prompt.dialog.oncancel({preventDefault() {}})
  await assert.rejects(cancelled, {code: 'cancelled'})
  const disallowed = h.session.websocket({url: 'wss://evil.example'})
  await assert.rejects(disallowed, {code: 'policy_denied'})
  assert.deepEqual(h.counts(), {captures: 0, screens: 0, destroyed: 0})
  assert.equal(h.sockets.length, 0)
  assert.equal(h.session.resources.size, 0)
  h.session.close()
})

test('screen picker starts synchronously in Allow and every capture needs a fresh gesture', async () => {
  const h = harness()
  for (let i = 1; i <= 2; i++) {
    const pending = h.session.capture({screen: true})
    assert.equal(h.counts().screens, i - 1)
    h.decide(true)
    assert.equal(h.counts().screens, i)
    const capture = await pending
    h.session.closeResource(capture.handle)
  }
  h.session.close()
})

test('camera browser denial, unsupported APIs and missing devices return safe structured errors', async () => {
  for (const [name, code] of [
    ['NotAllowedError', 'browser_denied'],
    ['NotFoundError', 'device_missing'],
    ['NotReadableError', 'device_unavailable']
  ]) {
    const h = harness()
    h.context.navigator.mediaDevices.getUserMedia = () =>
      Promise.reject(Object.assign(new Error('private device detail'), {name}))
    const request = h.session.receive({
      type: 'request',
      id: '1',
      action: 'capture',
      params: {camera: true}
    })
    await tick()
    h.decide(true)
    await request
    const reply = h.messages.find(({message}) => message.id === '1').message
    assert.equal(reply.error.code, code)
    assert.ok(!reply.error.message.includes('private'))
    h.session.close()
  }
  const h = harness()
  h.context.navigator.mediaDevices = {}
  await assert.rejects(h.session.capture({screen: true}), {code: 'unsupported'})
  h.session.close()
})

test('revocation and browser-ended tracks stop capture; late browser consent cannot resurrect it', async () => {
  const h = harness()
  const pending = h.session.capture({camera: true})
  h.decide(true)
  const capture = await pending
  h.session.record({handle: capture.handle})
  h.tracks[0].ended()
  assert.equal(h.tracks[0].stopped, true)
  assert.equal(h.session.resources.size, 0)
  let resolve
  h.context.navigator.mediaDevices.getUserMedia = () =>
    new Promise(r => {
      resolve = r
    })
  const late = h.session.capture({camera: true})
  h.session.revoke()
  resolve(h.stream())
  await assert.rejects(late, {code: 'revoked'})
  assert.equal(h.tracks[1].stopped, true)
  assert.equal(h.counts().destroyed, 1)
})

test('binary sockets check ownership and bound send and unacknowledged receive data', async () => {
  const h = harness(),
    other = harness()
  const opening = h.session.websocket({url: 'wss://relay.example/relay'})
  h.decide(true)
  const {handle} = await opening
  assert.throws(
    () => other.session.send({handle, buffer: new ArrayBuffer(1)}),
    {code: 'invalid_handle'}
  )
  const socket = h.sockets[0]
  socket.readyState = 1
  socket.onopen()
  h.session.send({handle, buffer: new ArrayBuffer(8)})
  assert.equal(socket.sent.byteLength, 8)
  socket.onmessage({data: new ArrayBuffer(8)})
  await tick()
  const event = h.messages.find(({message}) => message.event === 'data')
  assert.equal(event.transfer[0], event.message.buffer)
  await h.session.receive({type: 'ack', handle, sequence: 999, bytes: 100000})
  assert.equal(h.session.resource(handle).buffered, 8)
  await h.session.receive({
    type: 'ack',
    handle,
    sequence: event.message.sequence
  })
  assert.equal(h.session.resource(handle).buffered, 0)
  for (let i = 0; i < 5; i++)
    socket.onmessage?.({data: new ArrayBuffer(1024 * 1024)})
  assert.equal(socket.closed, true)
  assert.equal(h.session.resources.size, 0)
  assert.equal(h.messages.at(-1).message.reason, 'slow_consumer')
  other.session.close()
  h.session.close()
})

test('connection limits include pending approval and closing resources', async () => {
  const h = harness()
  const request = {
    capability: 'ui.network.websocket',
    destination: 'wss://relay.example'
  }
  const approve = h.session.authorize([request])
  h.decide(true)
  await approve
  for (let i = 0; i < 8; i++)
    await h.session.websocket({url: request.destination})
  await assert.rejects(h.session.websocket({url: request.destination}), {
    code: 'limit_exceeded'
  })
  h.session.revoke()
  assert.ok(h.sockets.every(socket => socket.closed))
  assert.equal(h.session.grants.size, 0)
})

test('network restrictions exclude LNbits, insecure/local URLs, credentials and undeclared destinations', async () => {
  const h = harness()
  for (const url of [
    'https://lnbits.example/api/v1/wallet',
    'https://lnbits.example:8443/api',
    'http://relay.example',
    'https://user:pass@relay.example',
    'https://127.1',
    'https://10.0.0.1',
    'https://[::1]',
    'https://printer.local',
    'https://relay.example/#fragment'
  ]) {
    assert.throws(() => h.session.destination(url, 'ui.network.https'), {
      code: 'invalid_destination'
    })
  }
  assert.throws(
    () =>
      h.session.authorize([{capability: 'wallet.pay_invoice', approved: true}]),
    {code: 'policy_denied'}
  )
  assert.throws(
    () =>
      h.session.authorize([
        {
          capability: 'ui.network.https',
          destination: 'https://evil.example',
          grantId: 'spoofed'
        }
      ]),
    {code: 'policy_denied'}
  )
  h.session.close()
})

test('HTTPS omits credentials, rejects redirects and bounds response data', async () => {
  let options
  const h = harness({
    fetch: async (_url, opts) => {
      options = opts
      return new Response(new Uint8Array([1, 2, 3]), {status: 200})
    }
  })
  const pending = h.session.https({url: 'https://relay.example/test'})
  h.decide(true)
  const result = await pending
  assert.equal(options.credentials, 'omit')
  assert.equal(options.redirect, 'error')
  assert.equal(options.referrerPolicy, 'no-referrer')
  assert.equal(result.buffer.byteLength, 3)
  h.context.fetch = async () =>
    new Response(new Uint8Array(4 * 1024 * 1024 + 1))
  await assert.rejects(h.session.https({url: 'https://relay.example/test'}), {
    code: 'limit_exceeded'
  })
  await assert.rejects(
    h.session.https({
      url: 'https://relay.example/test',
      headers: {'X-Api-Key': 'secret'}
    }),
    {code: 'invalid_request'}
  )
  h.session.close()
})

test('policy changes and expired leases revoke grants and destroy the frame', async () => {
  const h = harness()
  await h.session.refreshPolicy()
  delete h.policy.permissions['ui.media.camera']
  await assert.rejects(h.session.refreshPolicy(), {code: 'revoked'})
  assert.equal(h.counts().destroyed, 1)
  const stale = harness()
  stale.session.policyTime = 0
  assert.throws(
    () => stale.session.authorize([{capability: 'ui.media.camera'}]),
    {code: 'revoked'}
  )
  assert.equal(stale.counts().captures, 0)
})

test('control bridge rejects spoofed source/origin, port replacement and stale-port requests', () => {
  const context = {window: {}}
  vm.runInNewContext(
    readFileSync('lnbits/static/js/wasm-extension-component.js', 'utf8'),
    context
  )
  const component = context.window.WasmExtensionComponent
  const frame = {},
    instance = {...component.data(), $refs: {frame: {contentWindow: frame}}}
  for (const [key, method] of Object.entries(component.methods))
    instance[key] = method.bind(instance)
  let handler,
    requests = 0
  const port = {
    addEventListener(_event, fn) {
      handler = fn
    },
    start() {},
    postMessage() {},
    close() {}
  }
  instance.handleBridgeRequest = () => {
    requests++
  }
  const message = {
    type: 'lnbits-extension:connect',
    id: '1',
    extensionId: 'spoofed'
  }
  instance.onWindowMessage({
    source: {},
    origin: 'null',
    data: message,
    ports: [port]
  })
  instance.onWindowMessage({
    source: frame,
    origin: 'https://evil.example',
    data: message,
    ports: [port]
  })
  assert.equal(instance.bridgePort, null)
  instance.onWindowMessage({
    source: frame,
    origin: 'null',
    data: message,
    ports: [port]
  })
  assert.equal(instance.bridgePort, port)
  instance.onWindowMessage({
    source: frame,
    origin: 'null',
    data: message,
    ports: [{}]
  })
  assert.equal(instance.bridgePort, port)
  handler({data: {}})
  assert.equal(requests, 1)
  instance.closeBridgePort()
  handler({data: {}})
  assert.equal(requests, 1)
})

test('stopping sharing while consent is pending prevents the later Allow from starting capture', async () => {
  const h = harness()
  const capture = h.session.capture({camera: true})
  const handle = [...h.session.resources.keys()][0]
  h.session.closeResource(handle)
  h.decide(true)
  await assert.rejects(capture, {code: 'invalid_handle'})
  assert.equal(h.counts().captures, 0)
  h.session.close()
})

test('playback limits cover timeline, byte volume and concurrent appends', async () => {
  const h = harness()
  function playback() {
    const resource = h.session.reserve('playback', 6)
    let end = 1
    const sb = new EventTarget()
    sb.buffered = {length: 1, start: () => 0, end: () => end}
    sb.appendBuffer = () =>
      queueMicrotask(() => sb.dispatchEvent(new Event('updateend')))
    sb.remove = () =>
      queueMicrotask(() => sb.dispatchEvent(new Event('updateend')))
    resource.sourceBuffer = sb
    resource.video = {currentTime: 0}
    resource.mediaBytes = 0
    resource.segments = []
    return {
      resource,
      setEnd: value => {
        end = value
      }
    }
  }
  const first = playback()
  await h.session.append({
    handle: first.resource.handle,
    buffer: new ArrayBuffer(12)
  })
  assert.equal(first.resource.mediaBytes, 12)
  first.resource.writing = true
  await assert.rejects(
    h.session.append({
      handle: first.resource.handle,
      buffer: new ArrayBuffer(1)
    }),
    {code: 'slow_consumer'}
  )
  first.resource.writing = false
  first.setEnd(20)
  await assert.rejects(
    h.session.append({
      handle: first.resource.handle,
      buffer: new ArrayBuffer(1)
    }),
    {code: 'slow_consumer'}
  )
  assert.equal(h.session.resources.has(first.resource.handle), false)
  const second = playback()
  second.resource.mediaBytes = 16 * 1024 * 1024
  await assert.rejects(
    h.session.append({
      handle: second.resource.handle,
      buffer: new ArrayBuffer(1)
    }),
    {code: 'limit_exceeded'}
  )
  assert.equal(h.session.resources.size, 0)
  h.session.close()
})

test('SDK revocation terminates workers, revokes URLs and rejects pending operations', async () => {
  const {BrowserClient} =
    await import('../../lnbits/static/js/wasm-browser-sdk.mjs')
  const originalAdd = global.addEventListener,
    originalRemove = global.removeEventListener
  global.addEventListener = () => {}
  global.removeEventListener = () => {}
  try {
    const port = {
      start() {},
      postMessage() {},
      close() {
        this.closed = true
      }
    }
    const sdk = new BrowserClient(port)
    let terminated = false
    const worker = {
      terminate() {
        terminated = true
      }
    }
    sdk.workers.set(worker, URL.createObjectURL(new Blob(['test'])))
    const pending = sdk.capabilities()
    await sdk.receive({type: 'revoked'})
    await assert.rejects(pending, {code: 'revoked'})
    assert.equal(terminated, true)
    assert.equal(sdk.workers.size, 0)
    assert.equal(port.closed, true)
    assert.equal(sdk.resources.size, 0)
  } finally {
    global.addEventListener = originalAdd
    global.removeEventListener = originalRemove
  }
})

test('sockets still closing keep their connection slots', async () => {
  const h = harness()
  const permission = h.session.authorize([
    {capability: 'ui.network.websocket', destination: 'wss://relay.example'}
  ])
  h.decide(true)
  await permission
  for (let i = 0; i < 8; i++) {
    const {handle} = await h.session.websocket({url: 'wss://relay.example'})
    h.sockets[i].close = function () {
      this.readyState = 2
    }
    h.session.closeResource(handle)
  }
  assert.equal(h.session.resources.size, 0)
  await assert.rejects(h.session.websocket({url: 'wss://relay.example'}), {
    code: 'limit_exceeded'
  })
  h.sockets[0].onclose()
  const replacement = await h.session.websocket({url: 'wss://relay.example'})
  assert.ok(replacement.handle)
  h.session.close()
})

test('public sessions cannot use browser permissions to invoke wallet or existing payment actions', async () => {
  const h = harness()
  await h.session.receive({
    type: 'request',
    id: 'wallet',
    action: 'api',
    params: {method: 'wallet.pay_invoice'}
  })
  const denied = h.messages.find(({message}) => message.id === 'wallet').message
  assert.equal(denied.ok, false)
  assert.equal(denied.error.code, 'invalid_request')
  assert.equal(h.session.grants.size, 0)
  h.session.close()
})
