window.app.component('lnbits-manage-wallet-list', {
  template: '#lnbits-manage-wallet-list',
  data() {
    return {
      activeWalletId: null,
      walletRefreshTimer: null,
      walletRefreshPromise: null,
      walletRefreshQueued: false
    }
  },
  computed: {
    maxWallets() {
      return this.g.user?.extra?.visible_wallet_count || 10
    }
  },
  watch: {
    'g.offline'(offline) {
      if (!offline) this.scheduleWalletRefresh()
    },
    $route(to) {
      if (to.path.startsWith('/wallet/')) {
        this.activeWalletId = to.params.id
      } else {
        this.activeWalletId = null
      }
    },
    'g.user.wallets': {
      handler() {
        this.paymentEvents()
      },
      deep: true,
      immediate: true
    }
  },
  created() {
    if (this.g.user && this.g.walletEventListeners.length === 0) {
      this.paymentEvents()
    }
  },
  mounted() {
    document.addEventListener('visibilitychange', this.onVisibilityChange)
  },
  beforeUnmount() {
    clearTimeout(this.walletRefreshTimer)
    this.walletRefreshQueued = false
    document.removeEventListener('visibilitychange', this.onVisibilityChange)
  },
  methods: {
    openNewWalletDialog() {
      if (this.g.user.walletInvitesCount) {
        this.g.newWalletType = 'lightning-shared'
      } else {
        this.g.newWalletType = 'lightning'
      }
    },
    onVisibilityChange() {
      if (!document.hidden) this.scheduleWalletRefresh()
    },
    scheduleWalletRefresh() {
      clearTimeout(this.walletRefreshTimer)
      this.walletRefreshTimer = setTimeout(() => this.refreshWallets(), 500)
    },
    async refreshWallets() {
      if (!this.g.user) return
      if (this.walletRefreshPromise) {
        this.walletRefreshQueued = true
        return this.walletRefreshPromise
      }
      this.walletRefreshPromise = LNbits.api
        .getAuthenticatedUser()
        .then(({data}) => {
          const balances = new Map(
            (data.wallets || []).map(wallet => [wallet.id, wallet.balance_msat])
          )
          this.g.user.wallets.forEach(wallet => {
            const balance = balances.get(wallet.id)
            if (balance === undefined) return
            const isActive = this.g.wallet?.id === wallet.id
            wallet.msat = balance
            wallet.sat = Math.floor(balance / 1000)
            if (isActive) {
              this.g.wallet.msat = balance
              this.g.wallet.sat = wallet.sat
            }
          })
          this.g.updatePayments = !this.g.updatePayments
        })
        .catch(err => console.warn('Failed to refresh wallets', err))
        .finally(() => {
          this.walletRefreshPromise = null
          if (this.walletRefreshQueued) {
            this.walletRefreshQueued = false
            this.scheduleWalletRefresh()
          }
        })
      return this.walletRefreshPromise
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
      if (this.g.wallet?.id === data.payment.wallet_id) {
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
      if (!this.g.user) return
      let timeout
      const wallets = this.g.user.wallets.slice(0, this.maxWallets)
      wallets.forEach(wallet => {
        if (!this.g.walletEventListeners.includes(wallet.id)) {
          this.g.walletEventListeners.push(wallet.id)
          const ws = new WebSocket(`${websocketUrl}/${wallet.inkey}`)
          ws.onmessage = this.onWebsocketMessage
          ws.onopen = () => {
            console.log('ws connected for wallet', wallet.id)
            this.scheduleWalletRefresh()
          }
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
  }
})
