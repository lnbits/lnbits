window.app = Vue.createApp({
  el: '#vue',
  mixins: [window.windowMixin],
  async created() {
    this.$q.dark.set(
      this.$q.localStorage.has('lnbits.darkMode')
        ? this.$q.localStorage.getItem('lnbits.darkMode')
        : true
    )
    Chart.defaults.color = this.$q.dark.isActive ? '#fff' : '#000'
    this.changeTheme(this.themeChoice)
    this.applyBorder()
    if (this.$q.dark.isActive) {
      this.applyGradient()
    }
    this.applyBackgroundImage()

    let locale = this.$q.localStorage.getItem('lnbits.lang')
    if (locale) {
      window.LOCALE = locale
      window.i18n.global.locale = locale
    }

    this.g.langs = window.langs ?? []

    addEventListener('offline', event => {
      console.log('offline', event)
      this.g.offline = true
    })

    addEventListener('online', event => {
      console.log('back online', event)
      this.g.offline = false
    })

    if (window.user) {
      this.g.user = Vue.reactive(window.LNbits.map.user(window.user))
    }
    if (this.g.user?.extra?.wallet_invite_requests?.length) {
      this.walletTypes.push({
        label: `Lightning Wallet (Share Invite: ${this.g.user.extra.wallet_invite_requests.length})`,
        value: 'lightning-shared'
      })
    }
    if (window.wallet) {
      this.g.wallet = Vue.reactive(window.LNbits.map.wallet(window.wallet))
    }
    if (window.extensions) {
      this.g.extensions = Vue.reactive(window.extensions)
    }
    await this.checkUsrInUrl()
    this.themeParams()
    this.walletFlip = this.$q.localStorage.getItem('lnbits.walletFlip')
    if (
      this.$q.screen.gt.sm ||
      this.$q.localStorage.getItem('lnbits.mobileSimple') == false
    ) {
      this.mobileSimple = false
    }
  },
  mounted() {
    if (this.g.user) {
      this.paymentEvents()
    }
  }
})
