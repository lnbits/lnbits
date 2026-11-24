/* Trusted browser broker. No extension code executes in this context. */
;(() => {
  const labels = {
    'ui.network.https': 'Send and receive HTTPS data',
    'ui.network.websocket': 'Exchange binary data over a secure WebSocket',
    'ui.media.camera':
      'Use your camera and share its recording with this extension',
    'ui.media.microphone':
      'Use your microphone and share its recording with this extension',
    'ui.media.screen':
      'Share a screen or window you choose, including selected audio',
    'ui.media.playback': 'Play audio and video supplied by this extension'
  }
  const limits = Object.freeze({
    resources: 12,
    sockets: 8,
    captures: 3,
    playbacks: 6,
    requests: 8,
    packetBytes: 1024 * 1024,
    bufferedBytes: 4 * 1024 * 1024,
    unacknowledgedPackets: 16,
    playbackBytes: 16 * 1024 * 1024,
    policyLeaseMs: 30000
  })
  const mimeTypes = [
    'video/webm;codecs=vp8,opus',
    'video/webm;codecs=vp8',
    'audio/webm;codecs=opus'
  ]
  const failure = (code, message) => Object.assign(new Error(message), {code})
  const safeError = error => {
    if (error?.code && typeof error.code === 'string') return error
    const codes = {
      NotAllowedError: [
        'browser_denied',
        'Browser permission was denied or cancelled.'
      ],
      SecurityError: ['browser_denied', 'The browser blocked this operation.'],
      NotFoundError: [
        'device_missing',
        'No matching media device is available.'
      ],
      NotReadableError: [
        'device_unavailable',
        'The media device is busy or unavailable.'
      ],
      OverconstrainedError: [
        'device_unavailable',
        'The media device cannot provide this format.'
      ],
      AbortError: ['cancelled', 'The operation was cancelled.']
    }
    return failure(
      ...(codes[error?.name] || [
        'operation_failed',
        'The browser operation failed.'
      ])
    )
  }

  class BrowserSession {
    constructor({
      port,
      extensionId,
      extensionName,
      surface,
      readPolicy,
      destroyFrame
    }) {
      this.port = port
      this.extensionId = extensionId
      this.extensionName = extensionName
      this.surface = surface
      this.readPolicy = readPolicy
      this.destroyFrame = destroyFrame
      this.resources = new Map()
      this.closingSockets = new Set()
      this.grants = new Set()
      this.permissions = {}
      this.pending = 0
      this.closed = false
      this.policyTime = 0
      this.policySignature = null
      this.prompt = null
      this.lastSeen = Date.now()
      this.port.onmessage = event => this.receive(event.data)
      this.port.start()
      this.timer = setInterval(() => {
        if (Date.now() - this.lastSeen > 30000) {
          this.revoke()
          return
        }
        this.refreshPolicy().catch(() => this.revoke())
      }, 10000)
      this.pageHide = () => this.close()
      window.addEventListener('pagehide', this.pageHide)
      this.renderControls()
    }

    async refreshPolicy() {
      if (this.refreshing) return this.refreshing
      this.refreshing = (async () => {
        this.checkOpen()
        const policy = await this.readPolicy()
        this.checkOpen()
        const signature = JSON.stringify(policy.permissions)
        if (
          this.policySignature !== null &&
          this.policySignature !== signature
        ) {
          this.revoke()
          throw failure(
            'revoked',
            'Administrator policy changed. Start a new session.'
          )
        }
        this.permissions = policy.permissions || {}
        this.policySignature = signature
        this.policyTime = Date.now()
      })()
      try {
        await this.refreshing
      } catch (error) {
        this.revoke()
        throw safeError(error)
      } finally {
        this.refreshing = null
      }
    }

    checkOpen() {
      if (this.closed) throw failure('revoked', 'Browser session has ended.')
    }

    checkLease() {
      this.checkOpen()
      if (Date.now() - this.policyTime > limits.policyLeaseMs) {
        this.revoke()
        throw failure('revoked', 'Browser policy could not be refreshed.')
      }
    }

    async receive(message) {
      if (!message || this.closed) return
      this.lastSeen = Date.now()
      if (message.type === 'unload') {
        this.revoke()
        return
      }
      if (message.type === 'ping') return
      if (message.type === 'ack') {
        const resource = this.resources.get(message.handle)
        const bytes = resource?.unacked.get(message.sequence)
        if (bytes !== undefined) {
          resource.unacked.delete(message.sequence)
          resource.buffered -= bytes
        }
        return
      }
      if (
        message.type !== 'request' ||
        typeof message.id !== 'string' ||
        message.id.length > 128
      )
        return
      if (this.pending >= limits.requests) {
        this.reply(
          message.id,
          null,
          failure('limit_exceeded', 'Too many pending browser requests.')
        )
        return
      }
      this.pending++
      try {
        // Binary sends use a short, fail-closed lease; control operations recheck
        // installation policy. Neither path accepts identities or grant IDs.
        if (['send', 'append', 'close', 'stop'].includes(message.action))
          this.checkLease()
        else await this.refreshPolicy()
        const result = await this.dispatch(message.action, message.params || {})
        this.checkOpen()
        this.reply(message.id, result)
      } catch (error) {
        this.reply(message.id, null, safeError(error))
      } finally {
        this.pending--
      }
    }

    reply(id, data, error) {
      if (this.closed) return
      const transfer = data?.buffer instanceof ArrayBuffer ? [data.buffer] : []
      this.port.postMessage(
        error
          ? {
              type: 'response',
              id,
              ok: false,
              error: {code: error.code, message: error.message}
            }
          : {type: 'response', id, ok: true, data},
        transfer
      )
    }

    async dispatch(action, params) {
      switch (action) {
        case 'capabilities':
          return {
            limits,
            capture: Boolean(
              navigator.mediaDevices?.getUserMedia && window.MediaRecorder
            ),
            screen: Boolean(
              navigator.mediaDevices?.getDisplayMedia && window.MediaRecorder
            ),
            recordMimeTypes: mimeTypes.filter(type =>
              window.MediaRecorder?.isTypeSupported(type)
            ),
            playbackMimeTypes: mimeTypes.filter(type =>
              window.MediaSource?.isTypeSupported(type)
            )
          }
        case 'permissions':
          await this.authorize(params.requests)
          return {approved: true, lifetime: 'frame-session'}
        case 'https':
          return this.https(params)
        case 'websocket':
          return this.websocket(params)
        case 'capture':
          return this.capture(params)
        case 'record':
          return this.record(params)
        case 'playback':
          return this.playback(params)
        case 'send':
          return this.send(params)
        case 'append':
          return this.append(params)
        case 'close':
          this.resource(params.handle)
          this.closeResource(params.handle)
          return {closed: true}
        case 'stop':
          // Reply before destroying the frame and its workers/URLs/contexts.
          setTimeout(() => this.revoke(), 0)
          return {stopped: true}
        default:
          throw failure('invalid_request', 'Unknown browser operation.')
      }
    }

    destination(raw, capability) {
      let url
      try {
        url = new URL(raw)
      } catch (_) {
        throw failure(
          'invalid_destination',
          'Use an absolute HTTPS or WSS URL.'
        )
      }
      const scheme = capability === 'ui.network.https' ? 'https:' : 'wss:'
      const host = url.hostname.toLowerCase()
      // Never offer a browser proxy to LNbits itself, even on another port.
      // Non-public literal addresses and local names are also excluded.
      const privateHost =
        !host.includes('.') ||
        host.endsWith('.') ||
        /(?:^|\.)(?:localhost|local|internal)$/.test(host) ||
        /^(?:0|10|127|169\.254|192\.168)\./.test(host) ||
        /^172\.(?:1[6-9]|2\d|3[01])\./.test(host) ||
        /^100\.(?:6[4-9]|[7-9]\d|1[01]\d|12[0-7])\./.test(host) ||
        /^192\.0\.(?:0|2)\./.test(host) ||
        /^198\.(?:1[89]|51\.100)\./.test(host) ||
        /^203\.0\.113\./.test(host) ||
        /^(?:22[4-9]|2[3-5]\d)\./.test(host) ||
        host.startsWith('[')
      if (
        typeof raw !== 'string' ||
        raw.length > 4096 ||
        url.protocol !== scheme ||
        url.username ||
        url.password ||
        url.hash ||
        privateHost ||
        host === window.location.hostname.toLowerCase().replace(/\.$/, '')
      ) {
        throw failure(
          'invalid_destination',
          'This browser network destination is not allowed.'
        )
      }
      return url
    }

    permissionRequests(requests) {
      if (
        !Array.isArray(requests) ||
        !requests.length ||
        requests.length > 32
      ) {
        throw failure(
          'invalid_request',
          'Request between 1 and 32 browser permissions.'
        )
      }
      const entries = new Map()
      for (const request of requests) {
        const capability = request?.capability
        if (
          !Object.hasOwn(labels, capability) ||
          !Object.hasOwn(this.permissions, capability)
        ) {
          throw failure(
            'policy_denied',
            'The extension has not been allowed this browser capability.'
          )
        }
        let origin = ''
        if (capability.startsWith('ui.network.')) {
          origin = this.destination(request.destination, capability).origin
          if (!this.permissions[capability].includes(origin)) {
            throw failure(
              'policy_denied',
              'This destination is outside administrator policy.'
            )
          }
        }
        const key = `${capability} ${origin}`
        entries.set(key, {key, text: labels[capability], origin})
      }
      return [...entries.values()]
    }

    authorize(requests, start = () => undefined, force = false) {
      this.checkLease()
      const entries = this.permissionRequests(requests)
      if (!force && entries.every(entry => this.grants.has(entry.key))) {
        return Promise.resolve(start())
      }
      if (this.prompt)
        throw failure(
          'prompt_busy',
          'A browser permission dialog is already open.'
        )
      return new Promise((resolve, reject) => {
        const dialog = document.createElement('dialog')
        dialog.style.cssText =
          'max-width:520px;width:calc(100% - 48px);max-height:90vh;overflow:auto;overflow-wrap:anywhere;border:1px solid #777;border-radius:8px;padding:24px;'
        const title = document.createElement('h2')
        title.textContent = 'Browser access'
        const identity = document.createElement('p')
        identity.textContent = `${this.extensionName} (${this.extensionId}) requests access on this device:`
        const list = document.createElement('ul')
        for (const entry of entries) {
          const item = document.createElement('li')
          item.textContent =
            entry.text + (entry.origin ? ` — ${entry.origin}` : '')
          item.style.overflowWrap = 'anywhere'
          list.append(item)
        }
        const lifetime = document.createElement('p')
        lifetime.textContent =
          'Access lasts for this page session. Browser permission prompts still apply. Use Stop sharing or Revoke access above the extension at any time.'
        const finish = (approved, cancelled = false) => {
          if (this.prompt?.dialog !== dialog) return
          this.prompt = null
          dialog.close()
          dialog.remove()
          if (!approved) {
            reject(
              failure(
                cancelled ? 'cancelled' : 'user_denied',
                cancelled
                  ? 'Browser access cancelled.'
                  : 'Browser access declined.'
              )
            )
            return
          }
          try {
            this.checkLease()
            entries.forEach(entry => this.grants.add(entry.key))
            this.renderControls()
            // Deliberately synchronous from the trusted Allow click. Awaiting
            // another message or fetch here would lose screen-picker activation.
            resolve(start())
          } catch (error) {
            reject(safeError(error))
          }
        }
        const deny = document.createElement('button')
        deny.textContent = 'Deny'
        deny.onclick = () => finish(false)
        const allow = document.createElement('button')
        allow.textContent = 'Allow for this session'
        allow.style.marginLeft = '16px'
        allow.onclick = () => finish(true)
        dialog.oncancel = event => {
          event.preventDefault()
          finish(false, true)
        }
        dialog.append(title, identity, list, lifetime, deny, allow)
        document.body.append(dialog)
        this.prompt = {dialog, reject}
        dialog.showModal()
      })
    }

    reserve(kind, maximum) {
      this.checkLease()
      if (
        this.resources.size + this.closingSockets.size >= limits.resources ||
        [...this.resources.values()].filter(r => r.kind === kind).length +
          (kind === 'websocket' ? this.closingSockets.size : 0) >=
          maximum
      ) {
        throw failure(
          'limit_exceeded',
          'The browser resource limit has been reached.'
        )
      }
      const resource = {
        handle: crypto.randomUUID(),
        kind,
        unacked: new Map(),
        buffered: 0,
        sequence: 0,
        dispose: () => {}
      }
      this.resources.set(resource.handle, resource)
      return resource
    }

    resource(handle, kind) {
      this.checkLease()
      const resource = this.resources.get(handle)
      if (!resource || (kind && resource.kind !== kind)) {
        throw failure(
          'invalid_handle',
          'Unknown browser resource for this session.'
        )
      }
      return resource
    }

    event(resource, event, data = {}, transfer = []) {
      if (this.closed || !this.resources.has(resource.handle)) return
      this.port.postMessage(
        {type: 'event', handle: resource.handle, event, ...data},
        transfer
      )
    }

    packet(resource, value) {
      try {
        this.checkLease()
      } catch (_) {
        return
      }
      const size = value instanceof ArrayBuffer ? value.byteLength : value.size
      if (!size || !this.resources.has(resource.handle)) return
      if (
        size > limits.packetBytes ||
        resource.buffered + size > limits.bufferedBytes ||
        resource.unacked.size >= limits.unacknowledgedPackets
      ) {
        this.closeResource(resource.handle, 'slow_consumer')
        return
      }
      const sequence = ++resource.sequence
      resource.unacked.set(sequence, size)
      resource.buffered += size
      // Reserve credit before asynchronous Blob conversion; preserve recorder order.
      resource.delivery = (resource.delivery || Promise.resolve())
        .then(async () => {
          const buffer =
            value instanceof ArrayBuffer ? value : await value.arrayBuffer()
          this.event(resource, 'data', {sequence, buffer}, [buffer])
        })
        .catch(() => this.closeResource(resource.handle, 'operation_failed'))
    }

    async https(params) {
      const url = this.destination(params.url, 'ui.network.https')
      const method = params.method || 'GET'
      if (
        !['GET', 'HEAD', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'].includes(
          method
        )
      ) {
        throw failure('invalid_request', 'Unsupported HTTPS method.')
      }
      const headers = {}
      for (const [key, value] of Object.entries(params.headers || {})) {
        if (
          !['accept', 'content-type'].includes(key.toLowerCase()) ||
          typeof value !== 'string' ||
          value.length > 256
        ) {
          throw failure(
            'invalid_request',
            'Only Accept and Content-Type headers are supported.'
          )
        }
        headers[key] = value
      }
      const body =
        params.body === undefined ? undefined : this.binary(params.body)
      const resource = this.reserve('https', 4)
      const controller = new AbortController()
      resource.dispose = () => controller.abort()
      try {
        await this.authorize([
          {capability: 'ui.network.https', destination: url.href}
        ])
        this.resource(resource.handle)
        resource.timer = setTimeout(
          () => this.closeResource(resource.handle, 'timeout'),
          15000
        )
        const response = await fetch(url.href, {
          method,
          headers,
          body,
          signal: controller.signal,
          credentials: 'omit',
          mode: 'cors',
          redirect: 'error',
          referrerPolicy: 'no-referrer',
          cache: 'no-store'
        })
        const chunks = []
        let size = 0
        const reader = response.body?.getReader()
        if (reader) {
          for (;;) {
            const {done, value} = await reader.read()
            if (done) break
            size += value.byteLength
            if (size > limits.bufferedBytes)
              throw failure('limit_exceeded', 'HTTPS response is too large.')
            chunks.push(value)
          }
        }
        this.resource(resource.handle)
        const bytes = new Uint8Array(size)
        let offset = 0
        for (const chunk of chunks) {
          bytes.set(chunk, offset)
          offset += chunk.byteLength
        }
        return {
          status: response.status,
          headers: Object.fromEntries(response.headers),
          buffer: bytes.buffer
        }
      } finally {
        this.closeResource(resource.handle)
      }
    }

    async websocket(params) {
      const url = this.destination(params.url, 'ui.network.websocket')
      const protocols = params.protocols || []
      if (
        !Array.isArray(protocols) ||
        protocols.length > 4 ||
        protocols.some(
          p => typeof p !== 'string' || !/^[A-Za-z0-9._-]{1,128}$/.test(p)
        )
      ) {
        throw failure('invalid_request', 'Invalid WebSocket subprotocols.')
      }
      const resource = this.reserve('websocket', limits.sockets)
      try {
        await this.authorize([
          {capability: 'ui.network.websocket', destination: url.href}
        ])
        this.resource(resource.handle)
        const socket = new WebSocket(url.href, protocols)
        resource.socket = socket
        resource.dispose = () => {
          socket.onopen = socket.onmessage = socket.onerror = null
          socket.onclose = null
          if (socket.readyState !== WebSocket.CLOSED) {
            // Closing is asynchronous. Keep its slot until the browser confirms
            // closure so repeated close/open requests cannot evade the limit.
            this.closingSockets.add(socket)
            socket.onclose = () => this.closingSockets.delete(socket)
            socket.close()
          }
        }
        socket.binaryType = 'arraybuffer'
        resource.timer = setTimeout(
          () => this.closeResource(resource.handle, 'timeout'),
          15000
        )
        socket.onopen = () => {
          clearTimeout(resource.timer)
          this.event(resource, 'open', {protocol: socket.protocol})
        }
        socket.onmessage = event => {
          if (!(event.data instanceof ArrayBuffer))
            this.closeResource(resource.handle, 'invalid_data')
          else this.packet(resource, event.data)
        }
        socket.onerror = () =>
          this.closeResource(resource.handle, 'network_error')
        socket.onclose = event =>
          this.closeResource(resource.handle, 'closed', event.code)
        return {handle: resource.handle}
      } catch (error) {
        this.closeResource(resource.handle)
        throw error
      }
    }

    binary(value) {
      if (
        !(value instanceof ArrayBuffer) ||
        value.byteLength > limits.packetBytes
      ) {
        throw failure('invalid_data', 'Supply an ArrayBuffer of at most 1 MiB.')
      }
      return value
    }

    send(params) {
      const resource = this.resource(params.handle, 'websocket')
      const data = this.binary(params.buffer)
      if (resource.socket.readyState !== WebSocket.OPEN)
        throw failure('not_open', 'WebSocket is not open.')
      if (
        resource.socket.bufferedAmount + data.byteLength >
        limits.bufferedBytes
      ) {
        this.closeResource(resource.handle, 'slow_consumer')
        throw failure('slow_consumer', 'WebSocket send buffer is full.')
      }
      resource.socket.send(data)
      return {bufferedAmount: resource.socket.bufferedAmount}
    }

    async capture(params) {
      const screen = params.screen === true
      const camera = params.camera === true
      const microphone = params.microphone === true
      if (
        (!screen && !camera && !microphone) ||
        (screen && (camera || microphone))
      ) {
        throw failure(
          'invalid_request',
          'Choose camera/microphone or a separate screen capture.'
        )
      }
      const devices = navigator.mediaDevices
      if (
        !window.isSecureContext ||
        !window.MediaRecorder ||
        !(screen ? devices?.getDisplayMedia : devices?.getUserMedia)
      ) {
        throw failure(
          'unsupported',
          'This browser cannot capture the requested media in this context.'
        )
      }
      const requests = []
      if (screen) requests.push({capability: 'ui.media.screen'})
      if (camera) requests.push({capability: 'ui.media.camera'})
      if (microphone) requests.push({capability: 'ui.media.microphone'})
      const resource = this.reserve('capture', limits.captures)
      let stream
      try {
        stream = await this.authorize(
          requests,
          () => {
            this.resource(resource.handle)
            return screen
              ? devices.getDisplayMedia({
                  video: {frameRate: {ideal: 30, max: 30}},
                  audio: params.screenAudio === true
                })
              : devices.getUserMedia({
                  video: camera
                    ? {
                        width: {ideal: 1280, max: 1920},
                        height: {ideal: 720, max: 1080},
                        frameRate: {ideal: 30, max: 30}
                      }
                    : false,
                  audio: microphone
                    ? {echoCancellation: true, noiseSuppression: true}
                    : false
                })
          },
          screen
        )
        // A browser prompt can finish after revocation/navigation. Never retain
        // a late stream or deliver it to a replacement frame.
        this.resource(resource.handle)
        resource.stream = stream
        resource.dispose = () => {
          if (resource.recorder?.state !== 'inactive') resource.recorder?.stop()
          stream.getTracks().forEach(track => track.stop())
          this.removeSurface(resource)
        }
        for (const track of stream.getTracks()) {
          track.addEventListener(
            'ended',
            () => this.closeResource(resource.handle, 'track_ended'),
            {once: true}
          )
        }
        const video = this.mediaSurface(
          resource,
          screen ? 'Screen preview' : 'Camera / microphone preview'
        )
        video.muted = true
        video.srcObject = stream
        video.play().catch(() => {})
        return {
          handle: resource.handle,
          audio: stream.getAudioTracks().length > 0,
          video: stream.getVideoTracks().length > 0
        }
      } catch (error) {
        stream?.getTracks().forEach(track => track.stop())
        this.closeResource(resource.handle)
        throw error
      }
    }

    record(params) {
      const resource = this.resource(params.handle, 'capture')
      if (resource.recorder)
        throw failure('invalid_request', 'Capture is already recording.')
      const mimeType =
        params.mimeType ||
        (resource.stream.getVideoTracks().length ? mimeTypes[0] : mimeTypes[2])
      if (
        !mimeTypes.includes(mimeType) ||
        !MediaRecorder.isTypeSupported(mimeType)
      ) {
        throw failure('unsupported', 'This recording format is unavailable.')
      }
      const recorder = new MediaRecorder(resource.stream, {
        mimeType,
        videoBitsPerSecond: 2000000,
        audioBitsPerSecond: 96000
      })
      resource.recorder = recorder
      recorder.ondataavailable = event => this.packet(resource, event.data)
      recorder.onerror = () =>
        this.closeResource(resource.handle, 'media_error')
      recorder.start(100)
      return {mimeType: recorder.mimeType}
    }

    async playback(params) {
      const mimeType = params.mimeType
      if (
        !mimeTypes.includes(mimeType) ||
        !window.MediaSource?.isTypeSupported(mimeType)
      ) {
        throw failure('unsupported', 'This playback format is unavailable.')
      }
      const resource = this.reserve('playback', limits.playbacks)
      try {
        await this.authorize([{capability: 'ui.media.playback'}])
        this.resource(resource.handle)
        const source = new MediaSource()
        const video = this.mediaSurface(resource, 'Extension playback')
        const url = URL.createObjectURL(source)
        resource.source = source
        resource.segments = []
        resource.mediaBytes = 0
        resource.dispose = () => {
          resource.abortAppend?.()
          this.removeSurface(resource)
          URL.revokeObjectURL(url)
        }
        const ready = new Promise((resolve, reject) => {
          resource.abortAppend = () =>
            reject(failure('cancelled', 'Playback closed.'))
          source.addEventListener(
            'sourceopen',
            () => {
              try {
                this.resource(resource.handle)
                resource.sourceBuffer = source.addSourceBuffer(mimeType)
                resource.abortAppend = null
                resolve()
              } catch (error) {
                reject(error)
              }
            },
            {once: true}
          )
        })
        resource.timer = setTimeout(
          () => this.closeResource(resource.handle, 'timeout'),
          10000
        )
        video.src = url
        await ready
        clearTimeout(resource.timer)
        return {handle: resource.handle}
      } catch (error) {
        this.closeResource(resource.handle)
        throw error
      }
    }

    async append(params) {
      const resource = this.resource(params.handle, 'playback')
      const buffer = this.binary(params.buffer)
      if (resource.writing)
        throw failure('slow_consumer', 'Wait for the previous playback append.')
      resource.writing = true
      const sb = resource.sourceBuffer
      const update = operation =>
        new Promise((resolve, reject) => {
          const finish = error => {
            sb.removeEventListener('updateend', done)
            sb.removeEventListener('error', failed)
            clearTimeout(resource.timer)
            resource.abortAppend = null
            error ? reject(error) : resolve()
          }
          const done = () => finish()
          const failed = () =>
            finish(
              failure('media_error', 'Playback data could not be decoded.')
            )
          resource.abortAppend = () =>
            finish(failure('cancelled', 'Playback closed.'))
          resource.timer = setTimeout(
            () => this.closeResource(resource.handle, 'timeout'),
            10000
          )
          sb.addEventListener('updateend', done, {once: true})
          sb.addEventListener('error', failed, {once: true})
          try {
            operation()
          } catch (error) {
            finish(error)
          }
        })
      try {
        const time = resource.video.currentTime
        if (sb.buffered.length) {
          if (sb.buffered.end(sb.buffered.length - 1) - time > 15) {
            throw failure(
              'slow_consumer',
              'Playback is more than 15 seconds behind.'
            )
          }
          if (time > 10 && sb.buffered.start(0) < time - 10) {
            await update(() => sb.remove(0, time - 10))
            resource.segments = resource.segments.filter(segment => {
              if (segment.end > time - 10) return true
              resource.mediaBytes -= segment.bytes
              return false
            })
          }
        }
        this.resource(resource.handle)
        if (
          resource.mediaBytes + buffer.byteLength > limits.playbackBytes ||
          resource.segments.length >= 4096
        ) {
          throw failure('limit_exceeded', 'Playback buffer is full.')
        }
        await update(() => sb.appendBuffer(buffer))
        resource.mediaBytes += buffer.byteLength
        resource.segments.push({
          bytes: buffer.byteLength,
          end: sb.buffered.length
            ? sb.buffered.end(sb.buffered.length - 1)
            : Infinity
        })
        return {appended: true}
      } catch (error) {
        this.closeResource(resource.handle, error.code || 'media_error')
        throw error
      } finally {
        resource.writing = false
      }
    }

    mediaSurface(resource, label) {
      const container = document.createElement('figure')
      container.style.cssText =
        'display:inline-block;max-width:100%;margin:8px;vertical-align:top'
      const caption = document.createElement('figcaption')
      caption.textContent = `${this.extensionName}: ${label}`
      const video = document.createElement('video')
      video.controls = true
      video.playsInline = true
      video.style.cssText =
        'display:block;width:360px;max-width:100%;max-height:240px;background:#111'
      video.onerror = () => this.closeResource(resource.handle, 'media_error')
      const stop = document.createElement('button')
      stop.textContent = 'Stop'
      stop.onclick = () => this.closeResource(resource.handle)
      container.append(caption, video, stop)
      this.surface.append(container)
      resource.container = container
      resource.video = video
      return video
    }

    removeSurface(resource) {
      if (!resource.video) return
      resource.video.onerror = null
      resource.video.pause()
      resource.video.srcObject = null
      resource.video.removeAttribute('src')
      resource.video.load()
      resource.container.remove()
    }

    renderControls() {
      if (this.controls) this.controls.remove()
      const controls = document.createElement('div')
      controls.style.cssText = 'padding:12px;border:1px solid #888'
      const label = document.createElement('span')
      label.textContent = `${this.extensionName} — browser access for this page session. `
      const stop = document.createElement('button')
      stop.textContent = 'Stop sharing'
      stop.onclick = () => {
        for (const resource of [...this.resources.values()]) {
          if (resource.kind === 'capture') this.closeResource(resource.handle)
        }
      }
      const revoke = document.createElement('button')
      revoke.textContent = 'Revoke access'
      revoke.style.marginLeft = '12px'
      revoke.onclick = () => this.revoke()
      controls.append(label, stop, revoke)
      this.surface.prepend(controls)
      this.controls = controls
    }

    closeResource(handle, reason = 'closed', closeCode) {
      const resource = this.resources.get(handle)
      if (!resource) return
      this.event(resource, 'close', {reason, closeCode})
      this.resources.delete(handle)
      clearTimeout(resource.timer)
      resource.unacked.clear()
      try {
        resource.dispose()
      } catch (_) {}
    }

    revoke() {
      if (this.closed) return
      this.close()
      this.destroyFrame()
    }

    close() {
      if (this.closed) return
      for (const handle of [...this.resources.keys()])
        this.closeResource(handle, 'revoked')
      if (this.prompt) {
        this.prompt.dialog.close()
        this.prompt.dialog.remove()
        this.prompt.reject(
          failure('cancelled', 'Browser permission request cancelled.')
        )
        this.prompt = null
      }
      this.port.postMessage({type: 'revoked'})
      this.closed = true
      this.grants.clear()
      clearInterval(this.timer)
      window.removeEventListener('pagehide', this.pageHide)
      this.port.close()
      this.controls?.remove()
    }
  }
  window.LNbitsBrowserSession = BrowserSession
})()
