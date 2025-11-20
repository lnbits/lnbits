window.windowMixin = {
  methods: {
    openNewWalletDialog(walletType = 'lightning') {
      this.g.newWalletType = walletType
      this.g.showNewWalletDialog = true
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
    paymentEvents() {
      let timeout
      this.g.user.wallets.forEach(wallet => {
        if (!this.g.walletEventListeners.includes(wallet.id)) {
          this.g.walletEventListeners.push(wallet.id)
          const ws = new WebSocket(`${websocketUrl}/${wallet.inkey}`)
          ws.onmessage = this.onWebsocketMessage
          ws.onopen = () => console.log('ws connected for wallet', wallet.id)
          // onclose and onerror can both happen on their own or together,
          // so we add a clearTimeout to avoid multiple reconnections
          ws.onclose = () => {
            console.log('ws closed, reconnecting...', wallet.id)
            this.g.walletEventListeners = this.g.walletEventListeners.filter(
              id => id !== wallet.id
            )
            clearTimeout(timeout)
            timeout = setTimeout(this.paymentEvents, 5000)
          }
          ws.onerror = () => {
            console.warn('ws error, reconnecting...', wallet.id)
            this.g.walletEventListeners = this.g.walletEventListeners.filter(
              id => id !== wallet.id
            )
            clearTimeout(timeout)
            timeout = setTimeout(this.paymentEvents, 5000)
          }
        }
      })
    }
  },
  created() {
    // map jinja variable once on pageload
    if (window.user && !this.g.user) {
      this.g.user = window.LNbits.map.user(window.user)
      this.paymentEvents()
    }
  }
}
