window.app.component('lnbits-manage-wallet-list', {
  template: '#lnbits-manage-wallet-list',
  mixins: [window.windowMixin],
  data() {
    return {
      walletName: ''
    }
  },
  methods: {
    openNewWalletDialog() {
      this.g.newWalletType = 'lightning'
      this.g.showNewWalletDialog = true
    }
  }
})
