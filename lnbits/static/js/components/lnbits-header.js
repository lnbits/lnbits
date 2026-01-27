window.app.component('lnbits-header', {
  template: '#lnbits-header',
  computed: {
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
