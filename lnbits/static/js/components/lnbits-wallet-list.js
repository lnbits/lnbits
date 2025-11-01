window.app.component('lnbits-wallet-list', {
  mixins: [window.windowMixin],
  template: '#lnbits-wallet-list',
  data() {
    return {
      activeWallet: null,
      wallets: [],
      balance: 0,
      walletName: ''
    }
  },
  watch: {
    'g.user': {
      handler() {
        this.wallets = this.g.user.wallets.slice(
          0,
          this.g.user.extra.visible_wallet_count || 10
        )
      }
    }
  },
  methods: {
    createWallet() {
      this.$emit('wallet-action', {action: 'create-wallet'})
    }
  }
})
