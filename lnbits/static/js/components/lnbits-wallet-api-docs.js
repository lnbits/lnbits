window.app.component('lnbits-wallet-api-docs', {
  mixins: [window.windowMixin],
  template: '#lnbits-wallet-api-docs',
  data() {
    return {
      inkeyHidden: true,
      adminkeyHidden: true,
      walletIdHidden: true
    }
  }
})
