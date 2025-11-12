const created = async function () {
  this.$q.dark.set(this.g.darkMode)
  Chart.defaults.color = this.$q.dark.isActive ? '#fff' : '#000'
  this.changeTheme(this.themeChoice)
  this.applyBorder()
  if (this.$q.dark.isActive) {
    this.applyGradient()
  }
  this.applyBackgroundImage()

  if (this.g.user?.extra?.wallet_invite_requests?.length) {
    this.walletTypes.push({
      label: `Lightning Wallet (Share Invite: ${this.g.user.extra.wallet_invite_requests.length})`,
      value: 'lightning-shared'
    })
  }
  await this.checkUsrInUrl()
  this.themeParams()
}

const mounted = async function () {
  if (this.g.user) {
    this.paymentEvents()
  }
}

if (!window.app) {
  // Initialize Vue app if not already initialized
  window.app = Vue.createApp({
    el: '#vue',
    mixins: [window.windowMixin],
    created,
    mounted
  })
} else {
  // Extension create a new Vue app and mix in the created and mounted hooks
  window.app.mixin({created, mounted})
}
