window.app.component('lnbits-wallet-extra', {
  template: '#lnbits-wallet-extra',
  mixins: [window.windowMixin],
  props: ['chartConfig'],
  data() {
    return {}
  },
  methods: {
    handleSendLnurl(lnurl) {
      this.$emit('send-lnurl', lnurl)
    },
    updateWallet(wallet) {
      this.$emit('update-wallet', wallet)
    },
    handleFiatTracking() {
      this.g.fiatTracking = !this.g.fiatTracking
      if (!this.g.fiatTracking) {
        this.g.isFiatPriority = false
        this.g.wallet.currency = ''
        this.updateWallet({currency: ''})
      } else {
        this.updateWallet({currency: this.g.wallet.currency})
        this.updateFiatBalance()
      }
    },
    deleteWallet() {
      LNbits.utils
        .confirmDialog('Are you sure you want to delete this wallet?')
        .onOk(() => {
          LNbits.api
            .deleteWallet(this.g.wallet)
            .then(_ => {
              Quasar.Notify.create({
                timeout: 3000,
                message: `Wallet deleted!`,
                spinner: true
              })
            })
            .catch(err => {
              LNbits.utils.notifyApiError(err)
            })
        })
    },
    updateFiatBalance() {
      // set rate from local storage to avoid clunky api calls
      if (
        this.$q.localStorage.getItem(
          'lnbits.exchangeRate.' + this.g.wallet.currency
        )
      ) {
        this.g.exchangeRate = this.$q.localStorage.getItem(
          'lnbits.exchangeRate.' + this.g.wallet.currency
        )
        this.g.fiatBalance =
          (this.g.exchangeRate / 100000000) * this.g.wallet.sat
      }
      LNbits.api
        .request('GET', `/api/v1/rate/` + this.g.wallet.currency, null)
        .then(response => {
          this.g.fiatBalance =
            (response.data.price / 100000000) * this.g.wallet.sat
          this.g.exchangeRate = response.data.price.toFixed(2)
          this.g.fiatTracking = true
          this.$q.localStorage.set(
            'lnbits.exchangeRate.' + this.g.wallet.currency,
            this.g.exchangeRate
          )
        })
        .catch(e => console.error(e))
    }
  },
  created() {
    if (this.g.wallet.currency !== '' && this.g.isSatsDenomination) {
      this.g.fiatTracking = true
      this.updateFiatBalance()
    } else {
      this.g.fiatTracking = false
    }
  }
})
