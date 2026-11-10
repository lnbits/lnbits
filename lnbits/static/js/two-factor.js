/* Loaded before the application mounts, in both bundled and development modes. */
axios.interceptors.response.use(
  response => {
    if (response.data?.two_factor_required) {
      window.location.assign('/2fa')
      // The first-factor response must not run the normal post-login handlers.
      return new Promise(() => {})
    }
    return response
  },
  error => {
    if (
      error.response?.headers?.['two-factor-required'] &&
      !window.location.pathname.startsWith('/2fa') &&
      !error.config?.url?.includes('/auth/2fa')
    ) {
      sessionStorage.setItem(
        'lnbits.2fa.return',
        window.location.pathname + window.location.hash
      )
      window.location.assign('/2fa')
    }
    return Promise.reject(error)
  }
)

window.app.component('lnbits-two-factor', {
  template: '#lnbits-two-factor',
  props: {standalone: Boolean},
  data() {
    return {
      status: null,
      setup: null,
      code: '',
      showCode: false,
      codes: [],
      saved: false,
      busy: false,
      error: '',
      actionDialog: {
        show: false,
        action: '',
        code: '',
        showCode: false,
        requiresVerification: false
      }
    }
  },
  methods: {
    async call(method, path, data) {
      this.busy = true
      this.error = ''
      try {
        const response = await axios({
          method,
          url: '/api/v1/auth/2fa' + path,
          data
        })
        return response.data
      } catch (error) {
        if (
          this.actionDialog.show &&
          (path === '' || path === '/recovery') &&
          (error.response?.headers?.['two-factor-required'] ||
            error.response?.headers?.['token-expired'])
        ) {
          this.actionDialog.requiresVerification = true
          return null
        }
        this.error =
          typeof error.response?.data?.detail === 'string'
            ? error.response.data.detail
            : this.$t('two_factor_verification_error')
        return null
      } finally {
        this.busy = false
      }
    },
    async load() {
      this.status = await this.call('GET', '/status')
    },
    async start() {
      this.setup = await this.call('POST', '/setup')
      this.code = ''
      this.showCode = false
    },
    async verify() {
      const result = await this.call(
        'POST',
        this.setup ? '/confirm' : '/verify',
        {code: this.code.trim()}
      )
      this.code = ''
      this.showCode = false
      if (!result) return
      this.setup = null
      this.codes = result.recovery_codes || []
      await this.load()
      if (this.standalone && !this.codes.length) this.finish()
    },
    async acknowledge() {
      if (!this.saved) return
      if (!(await this.call('POST', '/recovery/acknowledge'))) return
      this.codes = []
      this.saved = false
      if (this.standalone) this.finish()
      else await this.load()
    },
    async openAction(action) {
      if (this.busy) return
      await this.load()
      if (!this.status) return
      this.actionDialog = {
        show: true,
        action,
        code: '',
        showCode: false,
        requiresVerification: this.status.verification_required
      }
    },
    async submitAction() {
      if (this.busy) return
      if (this.actionDialog.requiresVerification) {
        const result = await this.call('POST', '/verify', {
          code: this.actionDialog.code.trim()
        })
        this.actionDialog.code = ''
        this.actionDialog.showCode = false
        if (!result) return
        this.actionDialog.requiresVerification = false
      }
      const disabling = this.actionDialog.action === 'disable'
      const result = await this.call(
        disabling ? 'DELETE' : 'POST',
        disabling ? '' : '/recovery'
      )
      if (!result) return
      this.actionDialog.show = false
      if (disabling) await this.load()
      else {
        this.codes = result.recovery_codes
        this.saved = false
      }
    },
    clearActionDialog() {
      this.actionDialog.code = ''
      this.actionDialog.showCode = false
      this.error = ''
    },
    finish() {
      const path = sessionStorage.getItem('lnbits.2fa.return') || '/wallet'
      sessionStorage.removeItem('lnbits.2fa.return')
      window.location.assign(
        /^\/(account|admin|wallet)(\/|#|$)/.test(path) ? path : '/wallet'
      )
    },
    async logout() {
      await axios.post('/api/v1/auth/logout')
      window.location.assign('/')
    }
  },
  async created() {
    const query = new URLSearchParams(window.location.search)
    const usr = this.standalone && query.get('usr')
    if (usr) {
      window.history.replaceState({}, '', '/2fa')
      try {
        await axios.post('/api/v1/auth/usr', {usr})
        this.finish()
      } catch {
        this.error = this.$t('two_factor_sign_in_again_error')
      }
      return
    }
    await this.load()
  }
})
