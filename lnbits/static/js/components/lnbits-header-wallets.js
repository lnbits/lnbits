window.app.component('lnbits-header-wallets', {
  template: '#lnbits-header-wallets',
  mixins: [window.windowMixin],
  methods: {
    openNewWalletDialog() {
      this.g.newWalletType = 'lightning'
      this.g.showNewWalletDialog = true
    },
    openNewWalletInvite() {
      this.g.newWalletType = 'lightning-shared'
      this.g.showNewWalletDialog = true
    }
  }
})
