window.WasmExtensionComponent = {
  template: `
    <div class="wasm-extension-page relative-position">
      <q-inner-loading :showing="loading && !frameUrl">
        <q-spinner-dots size="40px"></q-spinner-dots>
      </q-inner-loading>
      <q-banner v-if="error" class="q-ma-md bg-negative text-white">
        {{ error }}
      </q-banner>
      <iframe
        v-else-if="frameUrl"
        ref="frame"
        :key="frameUrl"
        class="wasm-extension-frame"
        :src="frameUrl"
        :title="extensionName || 'Extension'"
        sandbox="allow-scripts"
        allow="clipboard-write"
        referrerpolicy="no-referrer"
      ></iframe>
      <q-dialog v-model="cameraPrompt.show" persistent>
        <q-card style="width: min(520px, calc(100vw - 32px)); max-width: 520px">
          <q-card-section>
            <div class="text-h6">Camera access</div>
          </q-card-section>
          <q-card-section class="q-pt-none">
            {{ cameraPrompt.extensionName }} wants to access the camera to scan a QR code.
          </q-card-section>
          <q-card-actions align="right">
            <q-btn
              flat
              color="negative"
              label="Deny"
              @click="resolveCameraPrompt('deny')"
            ></q-btn>
            <q-btn
              flat
              color="primary"
              label="Allow"
              @click="resolveCameraPrompt('allow')"
            ></q-btn>
            <q-btn
              unelevated
              color="primary"
              label="Allow and Remember"
              @click="resolveCameraPrompt('allow_remember')"
            ></q-btn>
          </q-card-actions>
        </q-card>
      </q-dialog>
    </div>
  `,
  data() {
    return {
      allowedPaymentHashes: new Set(),
      bridge: {
        apiRoutes: [],
        extensionId: '',
        permissions: [],
        public: false,
        query: {},
        routeParams: {}
      },
      bridgePort: null,
      cameraPrompt: {
        extensionName: '',
        reject: null,
        resolve: null,
        show: false
      },
      error: '',
      extensionName: '',
      frameUrl: '',
      handleWindowMessage: null,
      loading: false,
      loadId: 0,
      paymentSubscriptions: new Map()
    }
  },
  created() {
    this.handleWindowMessage = event => this.onWindowMessage(event)
    window.addEventListener('message', this.handleWindowMessage)
  },
  unmounted() {
    window.removeEventListener('message', this.handleWindowMessage)
    this.rejectCameraPrompt('Camera scan cancelled.')
    this.closeBridgePort()
  },
  watch: {
    '$route.fullPath': {
      immediate: true,
      handler() {
        this.loadFrameConfig()
      }
    }
  },
  methods: {
    emptyBridge() {
      return {
        apiRoutes: [],
        extensionId: '',
        permissions: [],
        public: false,
        query: {},
        routeParams: {}
      }
    },
    plainBridgeContext() {
      return {
        extensionId: String(this.bridge.extensionId || ''),
        public: Boolean(this.bridge.public),
        routeParams: this.plainValue(this.bridge.routeParams || {}),
        query: this.plainValue(this.bridge.query || {})
      }
    },
    hasBridgePermission(permission) {
      return (this.bridge.permissions || []).includes(permission)
    },
    cameraPromptStorageKey() {
      return `lnbits.ext.permissions.${this.bridge.extensionId}.ui.camera.scan_qr`
    },
    emptyCameraPrompt() {
      return {
        extensionName: '',
        reject: null,
        resolve: null,
        show: false
      }
    },
    plainValue(value) {
      try {
        return JSON.parse(JSON.stringify(value))
      } catch (_error) {
        return {}
      }
    },
    async loadFrameConfig() {
      const extId = String(this.$route.params.extId || '')
      const loadId = ++this.loadId
      this.loading = true
      this.error = ''
      this.frameUrl = ''
      this.bridge = this.emptyBridge()
      this.allowedPaymentHashes.clear()
      this.rejectCameraPrompt('Camera scan cancelled.')
      this.closeBridgePort()

      try {
        const response = await fetch(
          `/api/v1/ext/${encodeURIComponent(extId)}/_ui/frame`,
          {
            method: 'POST',
            headers: {'content-type': 'application/json'},
            credentials: 'same-origin',
            body: JSON.stringify({
              path: this.$route.path,
              query: this.$route.query || {}
            })
          }
        )
        const text = await response.text()
        let data = {}
        if (text) {
          try {
            data = JSON.parse(text)
          } catch (_error) {
            data = {detail: text}
          }
        }
        if (!response.ok) {
          throw new Error(data?.detail || 'Failed to load extension page.')
        }
        if (loadId !== this.loadId) return

        this.bridge = data.bridge || this.emptyBridge()
        this.extensionName = data.extension?.name || extId
        this.frameUrl = data.frameUrl
      } catch (error) {
        if (loadId !== this.loadId) return
        console.error('[lnbits wasm extension] Failed to load frame.', error)
        this.error = error instanceof Error ? error.message : String(error)
      } finally {
        if (loadId === this.loadId) {
          this.loading = false
        }
      }
    },
    extensionFrameWindow() {
      return this.$refs.frame?.contentWindow
    },
    sendResponse(reply, id, payload) {
      reply({
        type: 'lnbits-extension:response',
        id,
        ...payload
      })
    },
    allowedApiRoute(method, path) {
      let url
      try {
        url = new URL(path, window.location.origin)
      } catch (_error) {
        return false
      }
      if (url.origin !== window.location.origin) return false

      method = String(method || 'GET').toUpperCase()
      return (this.bridge.apiRoutes || []).some(route => {
        return (
          route.method === method &&
          new RegExp(route.pattern).test(url.pathname)
        )
      })
    },
    async callApi(message) {
      const method = String(message.method || 'GET').toUpperCase()
      const path = String(message.path || '')
      if (!this.allowedApiRoute(method, path)) {
        throw new Error('Extension API route is not allowed.')
      }

      const options = {
        method,
        headers: {},
        credentials: 'same-origin'
      }
      if (message.body !== undefined && message.body !== null) {
        options.headers['content-type'] = 'application/json'
        options.body = JSON.stringify(message.body)
      }

      const response = await fetch(path, options)
      const text = await response.text()
      let data = text
      if (text) {
        try {
          data = JSON.parse(text)
        } catch (_error) {
          data = text
        }
      }
      if (!response.ok) {
        throw new Error(
          typeof data === 'object' && data.detail ? data.detail : text
        )
      }
      this.rememberPaymentHashes(data)
      return data
    },
    notify(message) {
      const level = ['positive', 'negative', 'warning', 'info'].includes(
        message.level
      )
        ? message.level
        : 'info'
      if (window.Quasar?.Notify) {
        window.Quasar.Notify.create({
          color: level,
          message: String(message.message || '')
        })
      }
    },
    async scanQrCode() {
      if (!this.hasBridgePermission('ui.camera.scan_qr')) {
        throw new Error('Extension is missing scanner permission.')
      }
      if (!this.g) {
        throw new Error('LNbits scanner is not available.')
      }
      if (this.g.scanner) {
        throw new Error('A scanner is already active.')
      }
      await this.requireCameraScanApproval()
      if (this.g.scanner) {
        throw new Error('A scanner is already active.')
      }

      return new Promise((resolve, reject) => {
        let completed = false

        const cleanup = () => {
          window.clearTimeout(timeout)
          window.clearInterval(cancelPoll)
          if (this.g.scanner === onScan) {
            this.g.scanner = null
          }
        }

        const complete = callback => value => {
          if (completed) return
          completed = true
          cleanup()
          callback(value)
        }

        const onScan = value => {
          complete(resolve)({value: String(value || '')})
        }

        const timeout = window.setTimeout(() => {
          complete(reject)(new Error('QR scan timed out.'))
        }, 120000)

        const cancelPoll = window.setInterval(() => {
          if (!completed && this.g.scanner !== onScan) {
            complete(reject)(new Error('QR scan cancelled.'))
          }
        }, 250)

        this.g.scanner = onScan
      })
    },
    requireCameraScanApproval() {
      if (this.isCameraScanRemembered()) return Promise.resolve()
      if (this.cameraPrompt.show) {
        return Promise.reject(
          new Error('Camera access prompt is already open.')
        )
      }

      return new Promise((resolve, reject) => {
        this.cameraPrompt = {
          extensionName:
            this.extensionName || this.bridge.extensionId || 'This extension',
          reject,
          resolve,
          show: true
        }
      })
    },
    isCameraScanRemembered() {
      try {
        return (
          this.$q.localStorage.getItem(this.cameraPromptStorageKey()) ===
          'allow'
        )
      } catch (_error) {
        return false
      }
    },
    rememberCameraScanApproval() {
      try {
        this.$q.localStorage.set(this.cameraPromptStorageKey(), 'allow')
      } catch (_error) {}
    },
    resolveCameraPrompt(decision) {
      const resolve = this.cameraPrompt.resolve
      const reject = this.cameraPrompt.reject
      this.cameraPrompt = this.emptyCameraPrompt()

      if (decision === 'allow_remember') {
        this.rememberCameraScanApproval()
        resolve?.()
        return
      }
      if (decision === 'allow') {
        resolve?.()
        return
      }
      reject?.(new Error('Camera scan denied by user.'))
    },
    rejectCameraPrompt(message) {
      const reject = this.cameraPrompt.reject
      this.cameraPrompt = this.emptyCameraPrompt()
      reject?.(new Error(message))
    },
    rememberPaymentHashes(value) {
      if (!value || typeof value !== 'object') return

      if (Array.isArray(value)) {
        value.forEach(item => this.rememberPaymentHashes(item))
        return
      }

      for (const [key, item] of Object.entries(value)) {
        if (
          ['paymentHash', 'payment_hash'].includes(key) &&
          this.isPaymentHash(item)
        ) {
          this.allowedPaymentHashes.add(item)
        }
        this.rememberPaymentHashes(item)
      }
    },
    isPaymentHash(value) {
      return typeof value === 'string' && /^[a-f0-9]{64}$/i.test(value)
    },
    websocketUrl(path) {
      const url = new URL(window.location.href)
      url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:'
      url.pathname = path
      url.search = ''
      url.hash = ''
      return url.toString()
    },
    sendBridgeEvent(message) {
      if (!this.bridgePort) return
      this.bridgePort.postMessage({
        type: 'lnbits-extension:event',
        ...message
      })
    },
    closePaymentSubscription(subscriptionId) {
      const subscription = this.paymentSubscriptions.get(subscriptionId)
      if (!subscription) return
      this.paymentSubscriptions.delete(subscriptionId)
      try {
        subscription.socket.close()
      } catch (_error) {}
    },
    closePaymentSubscriptions() {
      for (const subscriptionId of Array.from(
        this.paymentSubscriptions.keys()
      )) {
        this.closePaymentSubscription(subscriptionId)
      }
    },
    closeBridgePort() {
      this.closePaymentSubscriptions()
      this.bridgePort?.close()
      this.bridgePort = null
    },
    subscribePayment(message) {
      const subscriptionId = String(message.subscriptionId || '')
      const paymentHash = String(message.paymentHash || '')

      if (!subscriptionId || !this.isPaymentHash(paymentHash)) {
        throw new Error('Invalid payment subscription.')
      }
      if (!this.allowedPaymentHashes.has(paymentHash)) {
        throw new Error('Payment subscription is not allowed.')
      }

      this.closePaymentSubscription(subscriptionId)

      const socket = new WebSocket(
        this.websocketUrl(`/api/v1/ws/${encodeURIComponent(paymentHash)}`)
      )
      this.paymentSubscriptions.set(subscriptionId, {paymentHash, socket})

      socket.addEventListener('message', event => {
        let data = event.data
        try {
          data = JSON.parse(event.data)
        } catch (_error) {}

        this.sendBridgeEvent({
          event: 'payment.update',
          subscriptionId,
          paymentHash,
          data
        })

        if (
          data &&
          typeof data === 'object' &&
          (data.pending === false ||
            ['success', 'settled', 'paid'].includes(String(data.status || '')))
        ) {
          this.sendBridgeEvent({
            event: 'payment.settled',
            subscriptionId,
            paymentHash,
            data
          })
          this.closePaymentSubscription(subscriptionId)
        }
      })
      socket.addEventListener('error', () => {
        this.sendBridgeEvent({
          event: 'payment.error',
          subscriptionId,
          paymentHash
        })
        this.closePaymentSubscription(subscriptionId)
      })
      socket.addEventListener('close', () => {
        this.paymentSubscriptions.delete(subscriptionId)
      })
    },
    async handleBridgeRequest(message, reply) {
      if (!message || message.type !== 'lnbits-extension:request') return

      try {
        if (message.action === 'context') {
          this.sendResponse(reply, message.id, {
            ok: true,
            data: this.plainBridgeContext()
          })
          return
        }

        if (message.action === 'api') {
          this.sendResponse(reply, message.id, {
            ok: true,
            data: await this.callApi(message)
          })
          return
        }

        if (message.action === 'ui.notify') {
          this.notify(message)
          this.sendResponse(reply, message.id, {
            ok: true,
            data: {ok: true}
          })
          return
        }

        if (message.action === 'ui.scan_qr') {
          this.sendResponse(reply, message.id, {
            ok: true,
            data: await this.scanQrCode()
          })
          return
        }

        if (message.action === 'payment.subscribe') {
          this.subscribePayment(message)
          this.sendResponse(reply, message.id, {
            ok: true,
            data: {ok: true}
          })
          return
        }

        if (message.action === 'payment.unsubscribe') {
          this.closePaymentSubscription(String(message.subscriptionId || ''))
          this.sendResponse(reply, message.id, {
            ok: true,
            data: {ok: true}
          })
          return
        }

        throw new Error('Unknown extension bridge action.')
      } catch (error) {
        this.sendResponse(reply, message.id, {
          ok: false,
          error: error instanceof Error ? error.message : String(error)
        })
      }
    },
    onWindowMessage(event) {
      if (event.source !== this.extensionFrameWindow()) return
      const message = event.data
      if (!message || message.type !== 'lnbits-extension:connect') return

      const port = event.ports?.[0]
      if (!port) return

      this.closeBridgePort()
      this.bridgePort = port
      this.bridgePort.addEventListener('message', portEvent => {
        this.handleBridgeRequest(portEvent.data, response => {
          port.postMessage(response)
        })
      })
      this.bridgePort.start()
      this.bridgePort.postMessage({
        type: 'lnbits-extension:connected',
        id: message.id
      })
    }
  }
}
