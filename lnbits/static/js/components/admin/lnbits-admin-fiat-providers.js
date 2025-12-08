window.app.component('lnbits-admin-fiat-providers', {
  props: ['form-data'],
  template: '#lnbits-admin-fiat-providers',
  mixins: [window.windowMixin],
  data() {
    return {
      formAddStripeUser: '',
      formAddPaypalUser: '',
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
    }
  }
})
