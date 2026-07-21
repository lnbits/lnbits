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
      <q-dialog v-model="backgroundPaymentPrompt.show" persistent>
        <q-card style="width: min(560px, calc(100vw - 32px)); max-width: 560px">
          <q-card-section>
            <div class="text-h6">Background payments</div>
          </q-card-section>
          <q-card-section class="q-pt-none q-gutter-md">
            <div>
              {{ backgroundPaymentPrompt.extensionName }} wants permission to make
              background payments from
              <strong>{{ backgroundPaymentPrompt.walletName }}</strong>.
            </div>
            <q-banner dense rounded class="bg-warning text-dark">
              This permission can move funds later without an active click.
            </q-banner>
            <q-input
              v-model.number="backgroundPaymentPrompt.form.maxAmount"
              type="number"
              label="Max payment amount (sats)"
              min="1"
              dense
              outlined
            ></q-input>
            <q-select
              v-model="backgroundPaymentPrompt.form.destinationPolicy"
              :options="backgroundPaymentDestinationOptions"
              emit-value
              map-options
              label="Allowed destinations"
              dense
              outlined
            ></q-select>
          </q-card-section>
          <q-card-actions align="right">
            <q-btn
              flat
              color="negative"
              label="Deny"
              @click="resolveBackgroundPaymentPrompt(false)"
            ></q-btn>
            <q-btn
              unelevated
              color="primary"
              label="Allow"
              @click="resolveBackgroundPaymentPrompt(true)"
            ></q-btn>
          </q-card-actions>
        </q-card>
      </q-dialog>
      <q-dialog v-model="walletPaymentWatchPrompt.show" persistent>
        <q-card style="width: min(520px, calc(100vw - 32px)); max-width: 520px">
          <q-card-section>
            <div class="text-h6">Watch wallet payments</div>
          </q-card-section>
          <q-card-section class="q-pt-none q-gutter-md">
            <div>
              {{ walletPaymentWatchPrompt.extensionName }} wants permission to receive
              payment notifications for
              <strong>{{ walletPaymentWatchPrompt.walletName }}</strong>.
            </div>
            <q-banner dense rounded class="bg-warning text-dark">
              This permission exposes payment metadata for this wallet to the extension.
            </q-banner>
          </q-card-section>
          <q-card-actions align="right">
            <q-btn
              flat
              color="negative"
              label="Deny"
              @click="resolveWalletPaymentWatchPrompt(false)"
            ></q-btn>
            <q-btn
              unelevated
              color="primary"
              label="Allow"
              @click="resolveWalletPaymentWatchPrompt(true)"
            ></q-btn>
          </q-card-actions>
        </q-card>
      </q-dialog>
      <q-dialog v-model="newTabPrompt.show" persistent>
        <q-card style="width: min(560px, calc(100vw - 32px)); max-width: 560px">
          <q-card-section>
            <div class="text-h6">Open link</div>
          </q-card-section>
          <q-card-section class="q-pt-none q-gutter-md">
            <div>
              {{ newTabPrompt.extensionName }} wants to open this link in a new
              tab.
            </div>
            <div
              class="text-body1 text-weight-medium text-dark bg-grey-2 q-pa-sm rounded-borders"
              style="word-break: break-all"
            >
              {{ newTabPrompt.url }}
            </div>
            <q-banner
              v-if="newTabPrompt.external"
              dense
              rounded
              class="bg-warning text-dark"
            >
              This link is not on the same domain as this LNbits page.
            </q-banner>
          </q-card-section>
          <q-card-actions align="right">
            <q-btn
              flat
              color="negative"
              label="Cancel"
              @click="resolveNewTabPrompt(false)"
            ></q-btn>
            <q-btn
              flat
              color="primary"
              icon="content_copy"
              label="Copy Link"
              @click="copyNewTabLink"
            ></q-btn>
            <q-btn
              unelevated
              color="primary"
              label="Open New Tab"
              @click="resolveNewTabPrompt(true)"
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
      backgroundPaymentDestinationOptions: [
        {
          label: 'Only transfers to my wallets',
          value: 'own_wallets_only'
        },
        {
          label: 'Allow external payments',
          value: 'external_allowed'
        }
      ],
      backgroundPaymentPrompt: {
        extensionName: '',
        form: {
          destinationPolicy: 'own_wallets_only',
          maxAmount: 0
        },
        reject: null,
        resolve: null,
        show: false,
        walletId: '',
        walletName: ''
      },
      walletPaymentWatchPrompt: {
        extensionName: '',
        reject: null,
        resolve: null,
        show: false,
        walletId: '',
        walletName: ''
      },
      newTabPrompt: {
        extensionName: '',
        external: false,
        reject: null,
        resolve: null,
        show: false,
        url: ''
      },
      error: '',
      extensionName: '',
      frameUrl: '',
      handleWindowMessage: null,
      loading: false,
      loadId: 0,
      paymentSubscriptions: new Map(),
      websocketSubscriptions: new Map()
    }
  },
  created() {
    this.handleWindowMessage = event => this.onWindowMessage(event)
    window.addEventListener('message', this.handleWindowMessage)
  },
  unmounted() {
    window.removeEventListener('message', this.handleWindowMessage)
    this.rejectCameraPrompt('Camera scan cancelled.')
    this.rejectBackgroundPaymentPrompt(
      'Background payment permission cancelled.'
    )
    this.rejectWalletPaymentWatchPrompt(
      'Wallet payment watch permission cancelled.'
    )
    this.rejectNewTabPrompt('Open link cancelled.')
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
    emptyBackgroundPaymentPrompt() {
      return {
        extensionName: '',
        form: {
          destinationPolicy: 'own_wallets_only',
          maxAmount: 0
        },
        reject: null,
        resolve: null,
        show: false,
        walletId: '',
        walletName: ''
      }
    },
    emptyCameraPrompt() {
      return {
        extensionName: '',
        reject: null,
        resolve: null,
        show: false
      }
    },
    emptyWalletPaymentWatchPrompt() {
      return {
        extensionName: '',
        reject: null,
        resolve: null,
        show: false,
        walletId: '',
        walletName: ''
      }
    },
    emptyNewTabPrompt() {
      return {
        extensionName: '',
        external: false,
        reject: null,
        resolve: null,
        show: false,
        url: ''
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
      this.rejectBackgroundPaymentPrompt(
        'Background payment permission cancelled.'
      )
      this.rejectWalletPaymentWatchPrompt(
        'Wallet payment watch permission cancelled.'
      )
      this.rejectNewTabPrompt('Open link cancelled.')
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
    extensionRoute(path) {
      let url
      try {
        url = new URL(String(path || ''), window.location.origin)
      } catch (_error) {
        throw new Error('Invalid extension route.')
      }
      if (url.origin !== window.location.origin) {
        throw new Error('Extension route must stay on this server.')
      }

      const basePath = `/ext/${encodeURIComponent(this.bridge.extensionId)}`
      if (
        url.pathname !== basePath &&
        !url.pathname.startsWith(`${basePath}/`)
      ) {
        throw new Error('Extension route must stay inside this extension.')
      }
      return `${url.pathname}${url.search}${url.hash}`
    },
    replaceExtensionRoute(message) {
      return this.$router.replace(this.extensionRoute(message.path))
    },
    newTabUrl(rawUrl) {
      const raw = String(rawUrl || '').trim()
      if (!raw) {
        throw new Error('Open link needs a URL.')
      }

      let url
      try {
        url = new URL(raw, window.location.href)
      } catch (_error) {
        throw new Error('Invalid open link URL.')
      }

      if (!['http:', 'https:'].includes(url.protocol)) {
        throw new Error('Only HTTP and HTTPS links can be opened.')
      }
      if (url.username || url.password) {
        throw new Error('Links with embedded credentials cannot be opened.')
      }

      return {
        external: url.origin !== window.location.origin,
        url: url.href
      }
    },
    openNewTab(message) {
      return this.promptNewTabOpen(this.newTabUrl(message.url || message.href))
    },
    promptNewTabOpen(link) {
      if (this.newTabPrompt.show) {
        throw new Error('Open link prompt is already open.')
      }

      return new Promise((resolve, reject) => {
        this.newTabPrompt = {
          extensionName:
            this.extensionName || this.bridge.extensionId || 'This extension',
          external: link.external,
          reject,
          resolve,
          show: true,
          url: link.url
        }
      })
    },
    resolveNewTabPrompt(approved) {
      const prompt = this.newTabPrompt
      if (!prompt.show) return
      this.newTabPrompt = this.emptyNewTabPrompt()

      if (!approved) {
        prompt.reject?.(new Error('Open link denied by user.'))
        return
      }

      try {
        window.open(prompt.url, '_blank', 'noopener,noreferrer')
        prompt.resolve?.({
          external: prompt.external,
          opened: true,
          url: prompt.url
        })
      } catch (error) {
        prompt.reject?.(error)
      }
    },
    rejectNewTabPrompt(message) {
      const reject = this.newTabPrompt.reject
      this.newTabPrompt = this.emptyNewTabPrompt()
      reject?.(new Error(message))
    },
    async copyNewTabLink() {
      const prompt = this.newTabPrompt
      if (!prompt.show || !prompt.url) return

      try {
        await navigator.clipboard.writeText(prompt.url)
        this.notify({
          level: 'positive',
          message: 'Link copied.'
        })
      } catch (_error) {
        this.notify({
          level: 'negative',
          message: 'Could not copy link.'
        })
      }
    },
    bridgeSessionStorageKey(rawKey) {
      const key = String(rawKey || '').trim()
      if (!key || key.length > 128 || !/^[A-Za-z0-9._:-]+$/.test(key)) {
        throw new Error('Invalid extension session key.')
      }
      return `lnbits.ext.session.${this.bridge.extensionId}.${key}`
    },
    getBridgeSessionValue(message) {
      const key = this.bridgeSessionStorageKey(message.key)
      return {value: window.sessionStorage.getItem(key) || ''}
    },
    setBridgeSessionValue(message) {
      const key = this.bridgeSessionStorageKey(message.key)
      const value = String(message.value || '')
      if (value.length > 4096) {
        throw new Error('Extension session value is too large.')
      }
      window.sessionStorage.setItem(key, value)
      return {ok: true}
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
    async requestBackgroundPaymentPermission(message) {
      const response = await this.requestExtensionPermissions({
        permissions: [
          {
            id: 'wallet.pay_invoice_background',
            grant: message?.grant || {}
          }
        ]
      })
      return response.permissions?.[0] || response
    },
    async requestWalletPaymentWatchPermission(message) {
      const response = await this.requestExtensionPermissions({
        permissions: [
          {
            id: 'wallet.payments.watch',
            grant: message?.grant || {}
          }
        ]
      })
      return response.permissions?.[0] || response
    },
    async requestExtensionPermissions(message) {
      if (this.bridge.public) {
        throw new Error('Public pages cannot request permissions.')
      }
      const permissions = Array.isArray(message.permissions)
        ? message.permissions
        : []
      if (!permissions.length) {
        throw new Error('No permissions requested.')
      }

      const requestedPermissions = permissions.map(permission =>
        this.normalizePermissionRequest(permission)
      )
      const checkResult = await this.checkExtensionPermissions(
        requestedPermissions.map(permission => ({
          id: permission.id,
          grant: permission.grant
        }))
      )
      const checks = Array.isArray(checkResult?.permissions)
        ? checkResult.permissions
        : []
      const approvedLabels = []
      const results = []

      for (const [index, permission] of requestedPermissions.entries()) {
        const check = checks[index] || {}
        if (check.id && check.id !== permission.id) {
          throw new Error('Permission check response did not match request.')
        }

        if (check.approved) {
          approvedLabels.push(permission.label)
          results.push({
            id: permission.id,
            approved: true,
            grant: check.grant || permission.grant
          })
          continue
        }

        const granted = await this.promptExtensionPermission(permission)
        results.push({
          id: permission.id,
          approved: true,
          grant: granted?.grant || permission.grant
        })
      }

      this.notifyApprovedPermissionUse(approvedLabels)
      return {permissions: results}
    },
    normalizePermissionRequest(permission) {
      const id = String(permission?.id || '')
      const grant = permission?.grant || {}
      if (id === 'wallet.pay_invoice_background') {
        return this.normalizeBackgroundPaymentPermission(grant)
      }
      if (id === 'wallet.payments.watch') {
        return this.normalizeWalletPaymentWatchPermission(grant)
      }
      throw new Error(`Unsupported permission request: ${id}.`)
    },
    normalizeBackgroundPaymentPermission(grant) {
      if (!this.hasBridgePermission('wallet.pay_invoice_background')) {
        throw new Error('Extension is missing background payment permission.')
      }

      const walletId = String(grant.walletId || grant.wallet_id || '')
      const wallet = this.walletById(walletId)
      if (!wallet) {
        throw new Error('Selected wallet is not available.')
      }
      if (wallet.walletType === 'lightning-shared') {
        throw new Error(
          'Background payments are not allowed from shared wallets.'
        )
      }

      const requestedGrant = {
        wallet_id: walletId,
        max_amount: this.positiveInteger(
          grant.maxAmount || grant.max_amount,
          1000
        ),
        destination_policy: this.backgroundPaymentDestinationPolicy(
          grant.destinationPolicy || grant.destination_policy
        )
      }
      if (!requestedGrant.max_amount) {
        throw new Error('Max payment amount must be greater than zero.')
      }

      return {
        id: 'wallet.pay_invoice_background',
        grant: requestedGrant,
        label: `Background payments from ${wallet.name || walletId}`,
        wallet
      }
    },
    normalizeWalletPaymentWatchPermission(grant) {
      if (!this.hasBridgePermission('wallet.payments.watch')) {
        throw new Error('Extension is missing wallet payment watch permission.')
      }

      const walletId = String(grant.walletId || grant.wallet_id || '')
      const wallet = this.walletById(walletId)
      if (!wallet) {
        throw new Error('Selected wallet is not available.')
      }

      return {
        id: 'wallet.payments.watch',
        grant: {wallet_id: walletId},
        label: `Watch wallet payments for ${wallet.name || walletId}`,
        wallet
      }
    },
    walletById(walletId) {
      return (
        (this.g?.user?.wallets || []).find(wallet => wallet.id === walletId) ||
        null
      )
    },
    async checkExtensionPermissions(permissions) {
      return await this.postExtensionPermission(
        'check',
        {permissions},
        'Could not check extension permissions.'
      )
    },
    promptExtensionPermission(permission) {
      if (permission.id === 'wallet.pay_invoice_background') {
        return this.promptBackgroundPaymentPermission(permission)
      }
      if (permission.id === 'wallet.payments.watch') {
        return this.promptWalletPaymentWatchPermission(permission)
      }
      throw new Error(`Unsupported permission request: ${permission.id}.`)
    },
    promptBackgroundPaymentPermission(permission) {
      if (this.backgroundPaymentPrompt.show) {
        throw new Error('Background payment prompt is already open.')
      }

      return new Promise((resolve, reject) => {
        this.backgroundPaymentPrompt = {
          extensionName:
            this.extensionName || this.bridge.extensionId || 'This extension',
          form: {
            destinationPolicy: permission.grant.destination_policy,
            maxAmount: permission.grant.max_amount
          },
          reject,
          resolve,
          show: true,
          walletId: permission.grant.wallet_id,
          walletName: permission.wallet.name || permission.grant.wallet_id
        }
      })
    },
    async resolveBackgroundPaymentPrompt(approved) {
      const prompt = this.backgroundPaymentPrompt
      if (!prompt.show) return

      if (!approved) {
        this.backgroundPaymentPrompt = this.emptyBackgroundPaymentPrompt()
        prompt.reject?.(new Error('Background payment permission denied.'))
        return
      }

      try {
        const grant = {
          wallet_id: prompt.walletId,
          max_amount: this.positiveInteger(prompt.form.maxAmount, 0),
          destination_policy: this.backgroundPaymentDestinationPolicy(
            prompt.form.destinationPolicy
          )
        }
        if (!grant.max_amount) {
          throw new Error('Max payment amount must be greater than zero.')
        }

        const data = await this.postExtensionPermission(
          'background-payment',
          grant,
          'Could not save permission.'
        )

        this.backgroundPaymentPrompt = this.emptyBackgroundPaymentPrompt()
        prompt.resolve?.(data)
      } catch (error) {
        prompt.reject?.(error)
        this.backgroundPaymentPrompt = this.emptyBackgroundPaymentPrompt()
      }
    },
    rejectBackgroundPaymentPrompt(message) {
      const reject = this.backgroundPaymentPrompt.reject
      this.backgroundPaymentPrompt = this.emptyBackgroundPaymentPrompt()
      reject?.(new Error(message))
    },
    promptWalletPaymentWatchPermission(permission) {
      if (this.walletPaymentWatchPrompt.show) {
        throw new Error('Wallet payment watch prompt is already open.')
      }

      return new Promise((resolve, reject) => {
        this.walletPaymentWatchPrompt = {
          extensionName:
            this.extensionName || this.bridge.extensionId || 'This extension',
          reject,
          resolve,
          show: true,
          walletId: permission.grant.wallet_id,
          walletName: permission.wallet.name || permission.grant.wallet_id
        }
      })
    },
    async resolveWalletPaymentWatchPrompt(approved) {
      const prompt = this.walletPaymentWatchPrompt
      if (!prompt.show) return

      if (!approved) {
        this.walletPaymentWatchPrompt = this.emptyWalletPaymentWatchPrompt()
        prompt.reject?.(new Error('Wallet payment watch permission denied.'))
        return
      }

      try {
        const data = await this.postExtensionPermission(
          'wallet-payments-watch',
          {wallet_id: prompt.walletId},
          'Could not save permission.'
        )

        this.walletPaymentWatchPrompt = this.emptyWalletPaymentWatchPrompt()
        prompt.resolve?.(data)
      } catch (error) {
        prompt.reject?.(error)
        this.walletPaymentWatchPrompt = this.emptyWalletPaymentWatchPrompt()
      }
    },
    rejectWalletPaymentWatchPrompt(message) {
      const reject = this.walletPaymentWatchPrompt.reject
      this.walletPaymentWatchPrompt = this.emptyWalletPaymentWatchPrompt()
      reject?.(new Error(message))
    },
    positiveInteger(value, fallback) {
      const number = Number(value)
      if (!Number.isFinite(number) || number <= 0) return fallback
      return Math.floor(number)
    },
    backgroundPaymentDestinationPolicy(value) {
      return value === 'external_allowed'
        ? 'external_allowed'
        : 'own_wallets_only'
    },
    async postExtensionPermission(path, body, fallbackMessage) {
      const response = await fetch(
        `/api/v1/extension/${encodeURIComponent(
          this.bridge.extensionId
        )}/permissions/${path}`,
        {
          method: 'POST',
          headers: {'content-type': 'application/json'},
          credentials: 'same-origin',
          body: JSON.stringify(body)
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
        throw new Error(data?.detail || fallbackMessage)
      }
      return data
    },
    notifyApprovedPermissionUse(permissions) {
      const permissionList = permissions.filter(Boolean).join(', ')
      if (!permissionList) return
      this.notify({
        level: 'info',
        message: `Using approved permissions: ${permissionList}.`
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
    isWebsocketItemId(value) {
      return (
        typeof value === 'string' &&
        /^[A-Za-z0-9][A-Za-z0-9:_-]{0,127}$/.test(value)
      )
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
    closeWebsocketSubscription(subscriptionId) {
      const subscription = this.websocketSubscriptions.get(subscriptionId)
      if (!subscription) return
      this.websocketSubscriptions.delete(subscriptionId)
      try {
        subscription.socket.close()
      } catch (_error) {}
    },
    closeWebsocketSubscriptions() {
      for (const subscriptionId of Array.from(
        this.websocketSubscriptions.keys()
      )) {
        this.closeWebsocketSubscription(subscriptionId)
      }
    },
    closeBridgePort() {
      this.closePaymentSubscriptions()
      this.closeWebsocketSubscriptions()
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
    subscribeWebsocket(message) {
      if (!this.hasBridgePermission('websocket.subscribe')) {
        throw new Error('Extension is missing websocket subscribe permission.')
      }

      const subscriptionId = String(message.subscriptionId || '')
      const itemId = String(message.itemId || '')

      if (
        !subscriptionId ||
        subscriptionId.length > 128 ||
        !this.isWebsocketItemId(itemId)
      ) {
        throw new Error('Invalid websocket subscription.')
      }

      this.closeWebsocketSubscription(subscriptionId)

      const socket = new WebSocket(
        this.websocketUrl(
          `/api/v1/ext/ws/${encodeURIComponent(
            this.bridge.extensionId
          )}/${encodeURIComponent(itemId)}`
        )
      )
      this.websocketSubscriptions.set(subscriptionId, {itemId, socket})

      socket.addEventListener('message', event => {
        let data = event.data
        try {
          data = JSON.parse(event.data)
        } catch (_error) {}

        this.sendBridgeEvent({
          event: 'websocket.message',
          subscriptionId,
          itemId,
          data
        })
      })
      socket.addEventListener('error', () => {
        this.sendBridgeEvent({
          event: 'websocket.error',
          subscriptionId,
          itemId
        })
        this.closeWebsocketSubscription(subscriptionId)
      })
      socket.addEventListener('close', () => {
        this.websocketSubscriptions.delete(subscriptionId)
      })
    },
    sendWebsocket(message) {
      if (!this.hasBridgePermission('websocket.subscribe')) {
        throw new Error('Extension is missing websocket subscribe permission.')
      }

      const subscriptionId = String(message.subscriptionId || '')
      if (!subscriptionId) {
        throw new Error('Invalid websocket subscription.')
      }

      const subscription = this.websocketSubscriptions.get(subscriptionId)
      if (!subscription) {
        return
      }

      if (subscription.socket.readyState !== WebSocket.OPEN) {
        if (
          subscription.socket.readyState === WebSocket.CLOSING ||
          subscription.socket.readyState === WebSocket.CLOSED
        ) {
          this.closeWebsocketSubscription(subscriptionId)
        }
        return
      }

      const data =
        typeof message.data === 'string'
          ? message.data
          : JSON.stringify(message.data ?? {})
      subscription.socket.send(data)
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

        if (message.action === 'navigation.replace') {
          await this.replaceExtensionRoute(message)
          this.sendResponse(reply, message.id, {
            ok: true,
            data: {ok: true}
          })
          return
        }

        if (message.action === 'navigation.open_new_tab') {
          this.sendResponse(reply, message.id, {
            ok: true,
            data: await this.openNewTab(message)
          })
          return
        }

        if (message.action === 'storage.session.get') {
          this.sendResponse(reply, message.id, {
            ok: true,
            data: this.getBridgeSessionValue(message)
          })
          return
        }

        if (message.action === 'storage.session.set') {
          this.sendResponse(reply, message.id, {
            ok: true,
            data: this.setBridgeSessionValue(message)
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

        if (message.action === 'permissions.request') {
          this.sendResponse(reply, message.id, {
            ok: true,
            data: await this.requestExtensionPermissions(message)
          })
          return
        }

        if (message.action === 'permissions.request_background_payment') {
          this.sendResponse(reply, message.id, {
            ok: true,
            data: await this.requestBackgroundPaymentPermission(message)
          })
          return
        }

        if (message.action === 'permissions.request_wallet_payment_watch') {
          this.sendResponse(reply, message.id, {
            ok: true,
            data: await this.requestWalletPaymentWatchPermission(message)
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

        if (message.action === 'websocket.subscribe') {
          this.subscribeWebsocket(message)
          this.sendResponse(reply, message.id, {
            ok: true,
            data: {ok: true}
          })
          return
        }

        if (message.action === 'websocket.unsubscribe') {
          this.closeWebsocketSubscription(String(message.subscriptionId || ''))
          this.sendResponse(reply, message.id, {
            ok: true,
            data: {ok: true}
          })
          return
        }

        if (message.action === 'websocket.send') {
          this.sendWebsocket(message)
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
