window.app.component('lnbits-error', {
  template: '#lnbits-error',
  mixins: [window.windowMixin],
  props: ['dynamic', 'code', 'message'],
  computed: {
    isExtension() {
      if (this.code != 403) return false
      if (this.message.startsWith('Extension ')) return true
    }
  },
  methods: {
    goBack() {
      window.history.back()
    },
    goHome() {
      window.location = '/'
    },
    goToWallet() {
      if (this.dynamic) {
        this.$router.push('/wallet')
        return
      }
      window.location = '/wallet'
    },
    goToExtension() {
      const extension = this.message.match(/'([^']+)'/)[1]
      const url = `/extensions#${extension}`
      if (this.dynamic) {
        this.$router.push(url)
        return
      }
      window.location = url
    },
    async logOut() {
      try {
        await LNbits.api.logout()
        window.location = '/'
      } catch (e) {
        LNbits.utils.notifyApiError(e)
      }
    }
  },
  async created() {
    // check if we have error from error.html
    if (!this.dynamic) {
      if (this.code == 401) {
        console.warn(`Unauthorized: ${this.errorMessage}`)
        this.logOut()
        return
      }
    }
  }
})
