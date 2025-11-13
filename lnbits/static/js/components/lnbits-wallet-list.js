window.app.component('lnbits-wallet-list', {
  template: '#lnbits-wallet-list',
  mixins: [window.windowMixin],
  props: ['balance'],
  data() {
    return {
      activeWallet: null,
      balance: 0,
      walletName: '',
      LNBITS_DENOMINATION: LNBITS_DENOMINATION
    }
  },
  methods: {
    createWallet() {
      this.$emit('wallet-action', {action: 'create-wallet'})
    }
  },
  created() {
    document.addEventListener('updateWalletBalance', this.updateWalletBalance)
  }
})
