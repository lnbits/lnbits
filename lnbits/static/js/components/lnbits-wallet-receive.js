window.app.component('lnbits-wallet-receive', {
  mixins: [window.windowMixin],
  template: '#lnbits-wallet-receive',
  data() {
    return {
      receive: {
        show: false,
        status: 'pending',
        paymentReq: null,
        paymentHash: null,
        amountMsat: null,
        minMax: [0, 2100000000000000],
        lnurl: null,
        unit: 'sat',
        fiatProvider: '',
        data: {
          amount: null,
          memo: '',
          internalMemo: null,
          payment_hash: null
        }
      }
    }
  },
  mounted() {
    console.log('lnbits-wallet-receive component created')
    this.showReceiveDialog()
  },
  methods: {
    showReceiveDialog() {
      console.log(this.$refs)
      this.receive.show = true
      this.receive.status = 'pending'
      this.receive.paymentReq = null
      this.receive.paymentHash = null
      this.receive.data.amount = null
      this.receive.data.memo = null
      this.receive.data.internalMemo = null
      this.receive.data.payment_hash = null
      this.receive.unit = this.g.wallet.currency || 'sats'
      this.receive.minMax = [0, 2100000000000000]
      this.receive.lnurl = null
      this.$nextTick(() => this.$refs['setAmount'].focus())
    },
    createInvoice() {
      this.receive.status = 'loading'
      if (LNBITS_DENOMINATION != 'sats') {
        this.receive.data.amount = this.receive.data.amount * 100
      }

      LNbits.api
        .createInvoice(
          this.g.wallet,
          this.receive.data.amount,
          this.receive.data.memo,
          this.receive.unit,
          this.receive.lnurlWithdraw,
          this.receive.fiatProvider,
          this.receive.data.internalMemo,
          this.receive.data.payment_hash
        )
        .then(response => {
          this.g.updatePayments = !this.g.updatePayments
          this.receive.status = 'success'
          this.receive.paymentReq = response.data.bolt11
          this.receive.fiatPaymentReq =
            response.data.extra?.fiat_payment_request
          this.receive.amountMsat = response.data.amount
          this.receive.paymentHash = response.data.payment_hash
          if (!this.receive.lnurl) {
            this.readNfcTag()
          }
          // WITHDRAW
          if (
            this.receive.lnurl &&
            response.data.extra?.lnurl_response !== null
          ) {
            if (response.data.extra.lnurl_response === false) {
              response.data.extra.lnurl_response = `Unable to connect`
            }
            const domain = this.receive.lnurl.callback.split('/')[2]
            if (typeof response.data.extra.lnurl_response === 'string') {
              // failure
              Quasar.Notify.create({
                timeout: 5000,
                type: 'warning',
                message: `${domain} lnurl-withdraw call failed.`,
                caption: response.data.extra.lnurl_response
              })
              return
            } else if (response.data.extra.lnurl_response === true) {
              // success
              Quasar.Notify.create({
                timeout: 3000,
                message: `Invoice sent to ${domain}!`,
                spinner: true
              })
            }
          }
        })
        .catch(err => {
          LNbits.utils.notifyApiError(err)
          this.receive.status = 'pending'
        })
    }
  }
})
