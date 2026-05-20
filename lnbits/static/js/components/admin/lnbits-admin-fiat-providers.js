window.app.component('lnbits-admin-fiat-providers', {
  props: ['form-data'],
  template: '#lnbits-admin-fiat-providers',
  data() {
    return {
      formAddStripeUser: '',
      formAddPaypalUser: '',
      formAddSquareUser: '',
      formAddRevolutUser: '',
      creatingRevolutWebhook: false,
      hideInputToggle: true
    }
  },
  computed: {
    stripeWebhookUrl() {
      return (
        this.formData?.stripe_payment_webhook_url ||
        this.calculateWebhookUrl('stripe')
      )
    },
    paypalWebhookUrl() {
      return (
        this.formData?.paypal_payment_webhook_url ||
        this.calculateWebhookUrl('paypal')
      )
    },
    revolutWebhookUrl() {
      return (
        this.formData?.revolut_payment_webhook_url ||
        this.calculateWebhookUrl('revolut')
      )
    }
  },
  watch: {
    formData: {
      handler() {
        this.syncWebhookUrls()
      },
      immediate: true
    }
  },
  methods: {
    basePathFromLocation() {
      if (typeof window === 'undefined') {
        return ''
      }
      const normalizedPath = window.location.pathname.replace(/\/+$/, '')
      const adminIndex = normalizedPath.lastIndexOf('/admin')
      const basePath =
        adminIndex >= 0
          ? normalizedPath.slice(0, adminIndex)
          : normalizedPath || ''
      return basePath || ''
    },
    calculateWebhookUrl(provider) {
      if (typeof window === 'undefined') {
        return ''
      }
      const basePath = this.basePathFromLocation()
      const path = `${basePath}/api/v1/callback/${provider}`.replace(
        /\/+/g,
        '/'
      )
      const withLeadingSlash = path.startsWith('/') ? path : `/${path}`
      return `${window.location.origin}${withLeadingSlash}`
    },
    syncWebhookUrls() {
      this.maybeSetWebhookUrl('stripe_payment_webhook_url', 'stripe')
      this.maybeSetWebhookUrl('paypal_payment_webhook_url', 'paypal')
      this.maybeSetWebhookUrl('square_payment_webhook_url', 'square')
      this.maybeSetWebhookUrl('revolut_payment_webhook_url', 'revolut')
    },
    maybeSetWebhookUrl(fieldName, provider) {
      if (!this.formData) {
        return
      }
      const calculated = this.calculateWebhookUrl(provider)
      const current = this.formData[fieldName]
      const hasPlaceholder =
        !current || current.includes('your-lnbits-domain-here.com')
      if (hasPlaceholder && calculated) {
        this.formData[fieldName] = calculated
      }
    },
    copyWebhookUrl(url) {
      if (!url) {
        return
      }
      this.copyText(url)
    },
    isClearnetWebhookUrl(url) {
      let parsedUrl
      try {
        parsedUrl = new URL(url)
      } catch (e) {
        return false
      }

      const host = parsedUrl.hostname.toLowerCase()
      if (!['http:', 'https:'].includes(parsedUrl.protocol)) {
        return false
      }
      if (
        host === 'localhost' ||
        host.endsWith('.localhost') ||
        host.endsWith('.local') ||
        host.endsWith('.onion')
      ) {
        return false
      }
      if (
        /^127\./.test(host) ||
        /^10\./.test(host) ||
        /^192\.168\./.test(host) ||
        /^169\.254\./.test(host) ||
        /^172\.(1[6-9]|2\d|3[0-1])\./.test(host) ||
        host === '0.0.0.0' ||
        host === '::1'
      ) {
        return false
      }
      return true
    },
    notifyRevolutWebhookWarning(message) {
      Quasar.Notify.create({
        type: 'warning',
        message,
        icon: null,
        closeBtn: true
      })
    },
    addStripeAllowedUser() {
      const addUser = this.formAddStripeUser || ''
      if (
        addUser.length &&
        !this.formData.stripe_limits.allowed_users.includes(addUser)
      ) {
        this.formData.stripe_limits.allowed_users = [
          ...this.formData.stripe_limits.allowed_users,
          addUser
        ]
        this.formAddStripeUser = ''
      }
    },
    removeStripeAllowedUser(user) {
      this.formData.stripe_limits.allowed_users =
        this.formData.stripe_limits.allowed_users.filter(u => u !== user)
    },
    addPaypalAllowedUser() {
      const addUser = this.formAddPaypalUser || ''
      if (
        addUser.length &&
        !this.formData.paypal_limits.allowed_users.includes(addUser)
      ) {
        this.formData.paypal_limits.allowed_users = [
          ...this.formData.paypal_limits.allowed_users,
          addUser
        ]
        this.formAddPaypalUser = ''
      }
    },
    removePaypalAllowedUser(user) {
      this.formData.paypal_limits.allowed_users =
        this.formData.paypal_limits.allowed_users.filter(u => u !== user)
    },
    addSquareAllowedUser() {
      const addUser = this.formAddSquareUser || ''
      if (
        addUser.length &&
        !this.formData.square_limits.allowed_users.includes(addUser)
      ) {
        this.formData.square_limits.allowed_users = [
          ...this.formData.square_limits.allowed_users,
          addUser
        ]
        this.formAddSquareUser = ''
      }
    },
    removeSquareAllowedUser(user) {
      this.formData.square_limits.allowed_users =
        this.formData.square_limits.allowed_users.filter(u => u !== user)
    },
    addRevolutAllowedUser() {
      const addUser = this.formAddRevolutUser || ''
      if (
        addUser.length &&
        !this.formData.revolut_limits.allowed_users.includes(addUser)
      ) {
        this.formData.revolut_limits.allowed_users = [
          ...this.formData.revolut_limits.allowed_users,
          addUser
        ]
        this.formAddRevolutUser = ''
      }
    },
    removeRevolutAllowedUser(user) {
      this.formData.revolut_limits.allowed_users =
        this.formData.revolut_limits.allowed_users.filter(u => u !== user)
    },
    checkFiatProvider(providerName) {
      LNbits.api
        .request('PUT', `/api/v1/fiat/check/${providerName}`)
        .then(response => {
          response
          const data = response.data
          Quasar.Notify.create({
            type: data.success ? 'positive' : 'warning',
            message: data.message,
            icon: null
          })
        })
        .catch(LNbits.utils.notifyApiError)
    },
    createRevolutWebhook() {
      const webhookUrl = this.calculateWebhookUrl('revolut')
      this.formData.revolut_payment_webhook_url = webhookUrl

      if (!this.formData.revolut_api_secret_key) {
        this.notifyRevolutWebhookWarning(
          'Add your Revolut API secret key before creating a webhook.'
        )
        return
      }
      if (!this.isClearnetWebhookUrl(webhookUrl)) {
        this.notifyRevolutWebhookWarning(
          'Revolut webhook URL must be a clearnet URL.'
        )
        return
      }

      this.creatingRevolutWebhook = true
      LNbits.api
        .request('POST', '/api/v1/fiat/revolut/webhook', null, {
          url: webhookUrl,
          endpoint: this.formData.revolut_api_endpoint,
          api_secret_key: this.formData.revolut_api_secret_key,
          api_version: this.formData.revolut_api_version
        })
        .then(response => {
          const data = response.data
          this.formData.revolut_payment_webhook_url = data.url
          this.formData.revolut_webhook_signing_secret = data.signing_secret
          Quasar.Notify.create({
            type: 'positive',
            message: `Revolut webhook ${
              data.already_exists ? 'already exists' : 'created'
            }${data.id ? `: ${data.id}` : ''}.`,
            icon: null
          })
        })
        .catch(LNbits.utils.notifyApiError)
        .finally(() => {
          this.creatingRevolutWebhook = false
        })
    }
  }
})
