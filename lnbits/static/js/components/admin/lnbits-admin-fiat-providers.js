window.app.component('lnbits-admin-fiat-providers', {
  props: ['form-data'],
  template: '#lnbits-admin-fiat-providers',
  mixins: [window.windowMixin],
  data() {
    return {
      formAddStripeUser: '',
      hideInputToggle: true
    }
  },
  methods: {
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
