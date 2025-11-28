window.app.component('lnbits-manage-wallet-list', {
  template: '#lnbits-manage-wallet-list',
  mixins: [window.windowMixin],
  data() {
    return {
      activeWalletId: null
    }
  },
  watch: {
    $route(to) {
      if (to.path.startsWith('/wallet/')) {
        this.activeWalletId = to.params.id
      } else {
        this.activeWalletId = null
      }
    }
  }
})
