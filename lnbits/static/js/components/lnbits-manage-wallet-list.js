window.app.component('lnbits-manage-wallet-list', {
  template: '#lnbits-manage-wallet-list',
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
  watch: {
    'g.user'(val) {
      console.log('updated user')
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
