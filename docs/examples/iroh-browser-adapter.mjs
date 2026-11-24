// Compatibility example: install ONLY in the extension iframe or its worker,
// before initializing an iroh wasm-bindgen module. This is not core code.
// Targets browser WebSocket and fetch imports used by iroh's ws_stream_wasm
// transport and HTTPS address lookup. No Iroh packets are interpreted here.
export function installIrohBrowserAdapter(browser, assetBase) {
  const nativeFetch = globalThis.fetch.bind(globalThis)
  const NativeWebSocket = globalThis.WebSocket
  const assets = new URL(assetBase)
  const destination = value => {
    const url = new URL(value)
    // Iroh's default relay map uses fully qualified names with a final dot.
    // Match the ordinary HTTPS/WSS origins declared in the extension manifest.
    url.hostname = url.hostname.replace(/\.$/, '')
    return url
  }
  class BridgeWebSocket extends EventTarget {
    static CONNECTING = 0
    static OPEN = 1
    static CLOSING = 2
    static CLOSED = 3
    constructor(url, protocols = []) {
      super()
      this.url = destination(String(url)).href
      this.readyState = 0
      this.binaryType = 'arraybuffer'
      this.bufferedAmount = 0
      this.protocol = ''
      this.extensions = ''
      this.queue = []
      browser
        .websocket(
          this.url,
          typeof protocols === 'string' ? [protocols] : protocols
        )
        .then(resource => {
          this.resource = resource
          if (this.readyState !== 0) {
            resource.close().catch(() => {})
            this.finish()
            return
          }
          resource.onData = buffer =>
            this.emit(
              new MessageEvent('message', {
                data: this.binaryType === 'blob' ? new Blob([buffer]) : buffer
              })
            )
          resource.onEvent = event => {
            if (event.event === 'open') {
              this.readyState = 1
              this.protocol = event.protocol
              this.emit(new Event('open'))
            } else if (event.event === 'close') {
              if (!['closed', 'revoked'].includes(event.reason))
                this.emit(new Event('error'))
              this.finish(event.closeCode || 1006)
            }
          }
        })
        .catch(() => {
          this.emit(new Event('error'))
          this.finish()
        })
    }
    emit(event) {
      this.dispatchEvent(event)
      this['on' + event.type]?.(event)
    }
    send(value) {
      if (this.readyState !== 1)
        throw new DOMException('Socket is not open', 'InvalidStateError')
      // Copy the typed-array view, never detach the WASM linear memory buffer.
      const buffer =
        value instanceof ArrayBuffer
          ? value.slice(0)
          : ArrayBuffer.isView(value)
            ? value.buffer.slice(
                value.byteOffset,
                value.byteOffset + value.byteLength
              )
            : null
      if (
        !buffer ||
        buffer.byteLength > 1024 * 1024 ||
        this.queue.length >= 256 ||
        this.bufferedAmount + buffer.byteLength > 4 * 1024 * 1024
      ) {
        this.emit(new Event('error'))
        this.close()
        return
      }
      this.queue.push(buffer)
      this.bufferedAmount += buffer.byteLength
      this.flush()
    }
    async flush() {
      if (this.flushing) return
      this.flushing = true
      try {
        while (this.queue.length && this.readyState === 1) {
          const buffer = this.queue.shift(),
            size = buffer.byteLength
          await this.resource.send(buffer)
          this.bufferedAmount -= size
        }
      } catch (_) {
        this.emit(new Event('error'))
        this.close()
      } finally {
        this.flushing = false
      }
    }
    close() {
      if (this.readyState >= 2) return
      this.readyState = 2
      this.resource?.close().catch(() => {})
      this.finish(1000)
    }
    finish(code = 1006) {
      if (this.readyState === 3) return
      this.readyState = 3
      this.queue.length = 0
      this.bufferedAmount = 0
      this.emit(new CloseEvent('close', {code, wasClean: code === 1000}))
    }
  }
  globalThis.WebSocket = BridgeWebSocket
  globalThis.fetch = async (input, init) => {
    const request = new Request(input, init)
    const url = destination(request.url)
    // Only extension assets may use the sandbox's native fetch; CSP remains
    // authoritative. Credentials are never sent by this adapter.
    if (
      url.origin === assets.origin &&
      url.pathname.startsWith(assets.pathname)
    ) {
      return nativeFetch(request, {credentials: 'omit'})
    }
    if (request.signal.aborted) throw new DOMException('Aborted', 'AbortError')
    const body = ['GET', 'HEAD'].includes(request.method)
      ? undefined
      : await request.arrayBuffer()
    const result = await browser.https({
      url: url.href,
      method: request.method,
      headers: Object.fromEntries(request.headers),
      body
    })
    if (request.signal.aborted) throw new DOMException('Aborted', 'AbortError')
    const response = new Response(
      [204, 205, 304].includes(result.status) ? null : result.buffer,
      {status: result.status, headers: result.headers}
    )
    // reqwest's WASM backend reads Response.url; constructed Responses have an
    // empty URL by default. The broker rejects all redirects.
    Object.defineProperty(response, 'url', {value: url.href})
    return response
  }
  return () => {
    globalThis.fetch = nativeFetch
    globalThis.WebSocket = NativeWebSocket
  }
}
