window.app.component('lnbits-header', {
  template: '#lnbits-header',
  computed: {
    hasServiceFeeMax() {
      return (
        this.g.user &&
        this.LNBITS_SERVICE_FEE_MAX &&
        this.LNBITS_SERVICE_FEE_MAX > 0
      )
    },
    serviceFeeMax() {
      return this.LNBITS_SERVICE_FEE_MAX || 0
    },
    hasServiceFee() {
      return (
        this.g.user && this.LNBITS_SERVICE_FEE && this.LNBITS_SERVICE_FEE > 0
      )
    },
    serviceFee() {
      return this.LNBITS_SERVICE_FEE || 0
    },
    hasCustomBadge() {
      return this.LNBITS_CUSTOM_BADGE && this.LNBITS_CUSTOM_BADGE != ''
    },
    customBadge() {
      return this.LNBITS_CUSTOM_BADGE || ''
    },
    customBadgeColor() {
      return this.LNBITS_CUSTOM_BADGE_COLOR || ''
    },
    showAdmin() {
      return this.g.user && (this.g.user.super_user || this.g.user.admin)
    },
    displayName() {
      return (
        this.g.user?.extra?.display_name ||
        this.g.user.username ||
        this.g.user?.extra?.first_name ||
        'Anon'
      )
    },
    displayRole() {
      if (this.g.user?.super_user) {
        return 'Super User'
      } else if (this.g.user?.admin) {
        return 'Admin'
      } else {
        return 'User'
      }
    }
  },
  methods: {
    async stopImpersonation() {
      try {
        await LNbits.api.stopImpersonation()
        LNbits.utils.restoreLocalStorage('impersonation')
        window.location = '/users'
      } catch (e) {
        console.warn(e)
      }
    },
    async handleLanguageChanged(lang) {
      try {
        await LNbits.api.updateUiCustomization({locale: lang.locale})
        this.$q.notify({
          type: 'positive',
          message: 'Language Updated',
          caption: lang.locale
        })
      } catch (e) {
        LNbits.utils.notifyApiError(e)
      }
    }
  }
})
