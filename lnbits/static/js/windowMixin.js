window.windowMixin = {
  methods: {
    openNewWalletDialog(walletType = 'lightning') {
      this.g.newWalletType = walletType
      this.g.showNewWalletDialog = true
    }
  }
}
