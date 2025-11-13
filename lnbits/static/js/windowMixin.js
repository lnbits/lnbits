window.windowMixin = {
  i18n: window.i18n,
  data() {
    return {
      api: window._lnbitsApi,
      utils: window._lnbitsUtils,
      g: window.g,
      toggleSubs: true,
      addWalletDialog: {show: false, walletType: 'lightning'},
      isSatsDenomination: WINDOW_SETTINGS['LNBITS_DENOMINATION'] == 'sats',
      allowedThemes: WINDOW_SETTINGS['LNBITS_THEME_OPTIONS'],
      walletEventListeners: [],
      ...WINDOW_SETTINGS
    }
  },

  methods: {
    flipWallets(smallScreen) {
      this.g.walletFlip = !this.g.walletFlip
      if (this.g.walletFlip && smallScreen) {
        this.g.visibleDrawer = false
      }
      this.$q.localStorage.set('lnbits.walletFlip', this.g.walletFlip)
    },
    goToWallets() {
      this.$router.push({
        path: '/wallets'
      })
    },
    handleWalletAction(payload) {
      if (payload.action === 'create-wallet') {
        this.showAddNewWalletDialog()
      }
    },
    showAddNewWalletDialog() {
      this.addWalletDialog = {show: true, walletType: 'lightning'}
    },
    paymentEvents() {
      this.g.walletEventListeners = this.g.walletEventListeners || []
      this.g.user.wallets.forEach(wallet => {
        if (!this.g.walletEventListeners.includes(wallet.id)) {
          this.g.walletEventListeners.push(wallet.id)
          LNbits.events.onInvoicePaid(wallet, data => {
            const walletIndex = this.g.user.wallets.findIndex(
              w => w.id === wallet.id
            )
            if (walletIndex !== -1) {
              //needed for balance being deducted
              let satBalance = data.wallet_balance
              if (data.payment.amount < 0) {
                satBalance = data.wallet_balance += data.payment.amount / 1000
              }
              //update the wallet
              Object.assign(this.g.user.wallets[walletIndex], {
                sat: satBalance,
                msat: data.wallet_balance * 1000,
                fsat: data.wallet_balance.toLocaleString()
              })
              //update the current wallet
              if (this.g.wallet.id === data.payment.wallet_id) {
                Object.assign(this.g.wallet, this.g.user.wallets[walletIndex])

                //if on the wallet page and payment is incoming trigger the eventReaction
                if (
                  data.payment.amount > 0 &&
                  window.location.pathname === '/wallet'
                ) {
                  eventReaction(data.wallet_balance * 1000)
                }
              }
            }
            this.g.updatePaymentsHash = data.payment.payment_hash
            this.g.updatePayments = !this.g.updatePayments
          })
        }
      })
    },
    selectWallet(wallet) {
      Object.assign(this.g.wallet, wallet)
      // this.wallet = this.g.wallet
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
    formatDate(date) {
      return moment
        .utc(date * 1000)
        .local()
        .fromNow()
    },
    formatBalance(amount) {
      if (LNBITS_DENOMINATION != 'sats') {
        return LNbits.utils.formatCurrency(amount / 100, LNBITS_DENOMINATION)
      } else {
        return LNbits.utils.formatSat(amount) + ' sats'
      }
    },
    copyText(text, message, position) {
      Quasar.copyToClipboard(text).then(() => {
        Quasar.Notify.create({
          message: message || 'Copied to clipboard!',
          position: position || 'bottom'
        })
      })
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
    }
    if (window.wallet) {
      this.g.wallet = Vue.reactive(window.LNbits.map.wallet(window.wallet))
    }
    if (window.extensions) {
      this.g.extensions = Vue.reactive(window.extensions)
    }
  },
  mounted() {
    if (this.g.user) {
      this.paymentEvents()
    }
  }
}
