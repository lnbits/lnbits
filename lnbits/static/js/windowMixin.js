window.windowMixin = {
  data() {
    return {
      g: window.g,
      ...WINDOW_SETTINGS
    }
  },
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
      console.log('ws message', data.payment.wallet_id, data)

      // update sidebar wallet balances
      this.g.user.wallets.forEach(w => {
        if (w.id === data.payment.wallet_id) {
          w.sat = data.wallet_balance
        }
      })

      // if current wallet, update balance and payments
      if (this.g.wallet.id === data.payment.wallet_id) {
        this.g.wallet.sat = data.wallet_balance
        this.g.updatePayments = !this.g.updatePayments
      }

      // NOTE: react only on incoming payments for now
      if (data.payment.amount > 0) {
        eventReaction(data.wallet_balance * 1000)
      }
    },
    paymentEvents() {
      this.g.user.wallets.forEach(wallet => {
        if (!this.g.walletEventListeners.includes(wallet.id)) {
          this.g.walletEventListeners.push(wallet.id)
          const ws = new WebSocket(`${websocketUrl}/${wallet.inkey}`)
          ws.onmessage = this.onWebsocketMessage
          ws.onclose = ev => {
            if (!ev.wasClean) console.log('ws uncleanly closed', ev)
          }
          ws.onerror = ev => {
            console.error('ws error', ev)
            this.g.walletEventListeners = this.g.walletEventListeners.filter(
              id => id !== wallet.id
            )
          }
        }
      })
    },
    selectWallet(wallet) {
      this.g.wallet = wallet
      this.g.lastActiveWallet = wallet.id
      this.g.updatePayments = !this.g.updatePayments
      this.balance = parseInt(wallet.balance_msat / 1000)
      const currentPath = this.$route.path
      if (currentPath !== '/wallet') {
        this.$router.push({
          path: '/wallet',
          query: {wal: this.g.wallet.id}
        })
      } else {
        this.$router.replace({
          path: '/wallet',
          query: {wal: this.g.wallet.id}
        })
      }
    },
    refreshRoute() {
      const path = window.location.pathname
      console.log(path)

      this.$router.push('/temp').then(() => {
        this.$router.replace({path})
      })
    }
  },
  async created() {
    if (window.user) {
      this.g.user = Vue.reactive(window.LNbits.map.user(window.user))
      this.paymentEvents()
    }
    if (window.wallet) {
      this.g.wallet = Vue.reactive(window.LNbits.map.wallet(window.wallet))
    }
    if (window.extensions) {
      this.g.extensions = Vue.reactive(window.extensions)
    }
  }
}
