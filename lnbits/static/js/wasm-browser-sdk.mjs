/* Optional browser SDK, executed only inside the extension sandbox. */
const bridgeError = error =>
  Object.assign(new Error(error.message || String(error)), {
    code: error.code || 'operation_failed'
  })

export async function connectBrowser() {
  const channel = new MessageChannel()
  const requests = new Map()
  let sequence = 0
  const connected = new Promise((resolve, reject) => {
    const timer = setTimeout(
      () => reject(new Error('LNbits bridge connection timed out.')),
      5000
    )
    channel.port1.onmessage = ({data}) => {
      if (data.type === 'lnbits-extension:connected') {
        clearTimeout(timer)
        resolve()
      }
      if (data.type !== 'lnbits-extension:response') return
      const pending = requests.get(data.id)
      if (!pending) return
      requests.delete(data.id)
      data.ok
        ? pending.resolve(data.data)
        : pending.reject(bridgeError(data.error))
    }
  })
  window.parent.postMessage(
    {type: 'lnbits-extension:connect', id: 'browser-sdk'},
    '*',
    [channel.port2]
  )
  await connected
  const request = (action, params = {}) =>
    new Promise((resolve, reject) => {
      if (requests.size >= 32) {
        reject(new Error('Too many bridge requests.'))
        return
      }
      const id = String(++sequence)
      requests.set(id, {resolve, reject})
      channel.port1.postMessage({
        ...params,
        type: 'lnbits-extension:request',
        id,
        action
      })
    })
  const browser = await attachBrowser(request)
  browser.request = request
  browser.onClose = () => {
    channel.port1.close()
    for (const pending of requests.values())
      pending.reject(
        bridgeError({code: 'revoked', message: 'Browser session ended.'})
      )
    requests.clear()
  }
  return browser
}

// Existing SDKs can keep their one frame-bound bridge and pass their request
// function here. It must return response.data without JSON serialization, so
// the transferred MessagePort survives.
export async function attachBrowser(request) {
  const {port} = await request('browser.connect')
  return new BrowserClient(port)
}

export class BrowserClient {
  constructor(port) {
    this.port = port
    this.pending = new Map()
    this.resources = new Map()
    this.workers = new Map()
    this.sequence = 0
    this.closed = false
    this.port.onmessage = event => this.receive(event.data)
    this.port.start()
    this.pageHide = () => {
      this.port.postMessage({type: 'unload'})
      this.dispose()
    }
    globalThis.addEventListener('pagehide', this.pageHide)
    this.heartbeat = setInterval(
      () => this.port.postMessage({type: 'ping'}),
      2000
    )
  }

  async receive(message) {
    if (message.type === 'revoked') {
      this.dispose()
      return
    }
    if (message.type === 'response') {
      const pending = this.pending.get(message.id)
      if (!pending) return
      this.pending.delete(message.id)
      message.ok
        ? pending.resolve(message.data)
        : pending.reject(bridgeError(message.error))
      return
    }
    if (message.type !== 'event') return
    const resource = this.resources.get(message.handle)
    if (!resource) return
    if (message.event === 'data') {
      try {
        // Await consumption before returning credit. A worker may receive the
        // ArrayBuffer by transfer and acknowledge it after processing.
        if (!resource.onData) throw new Error('No data consumer installed.')
        await resource.onData(message.buffer)
        if (!this.closed)
          this.port.postMessage({
            type: 'ack',
            handle: message.handle,
            sequence: message.sequence
          })
      } catch (_) {
        resource.close().catch(() => {})
      }
    } else {
      if (message.event === 'open') resource.protocol = message.protocol
      if (message.event === 'close') {
        resource.closed = true
        this.resources.delete(message.handle)
      }
      resource.onEvent?.(message)
    }
  }

  call(action, params = {}, transfer = []) {
    if (this.closed)
      return Promise.reject(
        bridgeError({code: 'revoked', message: 'Browser session ended.'})
      )
    if (this.pending.size >= 8)
      return Promise.reject(
        bridgeError({
          code: 'limit_exceeded',
          message: 'Too many pending browser operations.'
        })
      )
    const id = String(++this.sequence)
    return new Promise((resolve, reject) => {
      this.pending.set(id, {resolve, reject})
      try {
        this.port.postMessage({type: 'request', id, action, params}, transfer)
      } catch (error) {
        this.pending.delete(id)
        reject(error)
      }
    })
  }

  capabilities() {
    return this.call('capabilities')
  }
  approve(requests) {
    return this.call('permissions', {requests})
  }
  https(params) {
    return this.call(
      'https',
      params,
      params.body instanceof ArrayBuffer ? [params.body] : []
    )
  }

  async websocket(url, protocols = []) {
    return this.resource(await this.call('websocket', {url, protocols}))
  }
  async capture(options) {
    return this.resource(await this.call('capture', options))
  }
  async playback(mimeType) {
    return this.resource(await this.call('playback', {mimeType}))
  }

  resource(info) {
    const resource = {
      ...info,
      closed: false,
      onData: null,
      onEvent: null,
      record: mimeType => this.call('record', {handle: info.handle, mimeType}),
      send: buffer =>
        this.call('send', {handle: info.handle, buffer}, [buffer]),
      append: buffer =>
        this.call('append', {handle: info.handle, buffer}, [buffer]),
      close: () => this.call('close', {handle: info.handle})
    }
    this.resources.set(info.handle, resource)
    return resource
  }

  createWorker(moduleUrl) {
    if (this.closed || this.workers.size >= 4)
      throw new Error('Worker limit reached or session ended.')
    // Classic blob workers work in opaque origins where Chromium rejects blob
    // module workers. Dynamic import still supports extension ES modules.
    const url = new URL(moduleUrl, document.baseURI)
    const blobUrl = URL.createObjectURL(
      new Blob(
        [
          `import(${JSON.stringify(url.href)}).catch(error => { throw error });`
        ],
        {
          type: 'text/javascript'
        }
      )
    )
    let worker
    try {
      worker = new Worker(blobUrl)
    } catch (error) {
      URL.revokeObjectURL(blobUrl)
      throw error
    }
    this.workers.set(worker, blobUrl)
    return worker
  }

  stopWorker(worker) {
    worker.terminate()
    URL.revokeObjectURL(this.workers.get(worker))
    this.workers.delete(worker)
  }

  async stop() {
    try {
      await this.call('stop')
    } finally {
      this.dispose()
    }
  }

  dispose() {
    if (this.closed) return
    this.closed = true
    clearInterval(this.heartbeat)
    globalThis.removeEventListener('pagehide', this.pageHide)
    for (const worker of this.workers.keys()) this.stopWorker(worker)
    for (const pending of this.pending.values())
      pending.reject(
        bridgeError({code: 'revoked', message: 'Browser session ended.'})
      )
    this.pending.clear()
    for (const resource of this.resources.values()) {
      resource.closed = true
      resource.onEvent?.({event: 'close', reason: 'revoked'})
    }
    this.resources.clear()
    this.port.close()
    this.onClose?.()
  }
}
