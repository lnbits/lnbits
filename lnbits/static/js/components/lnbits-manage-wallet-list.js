window.app.component('lnbits-manage-wallet-list', {
  template: '#lnbits-manage-wallet-list',
  data() {
    return {
      activeWalletId: null,
      paymentSocket: null,
      paymentSocketKey: null,
      paymentReconnect: null
    }
  },
  computed: {
    maxWallets() {
      return this.g.user?.extra?.visible_wallet_count || 10
    }
  },
  watch: {
    $route: {
      handler(to) {
        this.activeWalletId = to.path.startsWith('/wallet/')
          ? to.params.id
          : null
        this.paymentEvents()
      },
      immediate: true
    },
    'g.user.wallets': {
      handler() {
        this.paymentEvents()
      },
      deep: true,
      immediate: true
    }
  },
  beforeUnmount() {
    this.closePaymentSocket()
  },
  methods: {
    openNewWalletDialog() {
      if (this.g.user.walletInvitesCount) {
        this.g.newWalletType = 'lightning-shared'
      } else {
        this.g.newWalletType = 'lightning'
      }
    },
    onWebsocketMessage(ev) {
      const data = JSON.parse(ev.data)
      if (!data.payment) {
        console.error('ws message no payment', data)
        return
      }
      // update sidebar wallet balances
      this.g.user.wallets.forEach(w => {
        if (w.id === data.payment.wallet_id) {
          w.sat = data.wallet_balance
        }
      })
      // if current wallet, update balance and payments
      if (this.g.wallet.id === data.payment.wallet_id) {
        this.g.wallet.sat = data.wallet_balance
        // lnbits-payment-list is watching
        this.g.updatePayments = !this.g.updatePayments
        this.g.updatePaymentsHash = !this.g.updatePaymentsHash
      }
      // NOTE: react only on incoming payments for now
      if (data.payment.amount > 0) {
        eventReaction(data.wallet_balance * 1000)
      }
    },
    closePaymentSocket() {
      clearTimeout(this.paymentReconnect)
      this.paymentReconnect = null
      const ws = this.paymentSocket
      this.paymentSocket = null
      this.paymentSocketKey = null
      this.g.walletEventListeners = []
      if (ws) {
        ws.onopen = ws.onmessage = ws.onclose = ws.onerror = null
        ws.close()
      }
    },
    paymentEvents() {
      const wallet = this.g.user?.wallets.find(
        w => w.id === this.activeWalletId
      )
      if (wallet && this.paymentSocketKey === wallet.inkey) return
      this.closePaymentSocket()
      if (!wallet) return
      const ws = new WebSocket(`${websocketUrl}/${wallet.inkey}`)
      this.paymentSocket = ws
      this.paymentSocketKey = wallet.inkey
      this.g.walletEventListeners = [wallet.id]
      ws.onmessage = ev => {
        if (this.paymentSocket === ws) this.onWebsocketMessage(ev)
      }
      ws.onopen = () => console.log('ws connected for wallet', wallet.id)
      const reconnect = () => {
        if (this.paymentSocket !== ws) return
        this.closePaymentSocket()
        this.paymentReconnect = setTimeout(this.paymentEvents, 5000)
      }
      ws.onclose = reconnect
      ws.onerror = reconnect
    }
  }
})
