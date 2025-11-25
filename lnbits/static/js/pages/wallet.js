window.PageWallet = {
  template: '#page-wallet',
  mixins: [window.windowMixin],
  data() {
    return {
      parse: {
        show: false,
        invoice: null,
        lnurlpay: null,
        lnurlauth: null,
        data: {
          request: '',
          amount: 0,
          comment: '',
          internalMemo: null,
          unit: 'sat'
        },
        paymentChecker: null,
        copy: {
          show: false
        },
        camera: {
          show: false,
          camera: 'auto'
        }
      },
      receive: {
        show: false,
        status: 'pending',
        paymentReq: null,
        paymentHash: null,
        amountMsat: null,
        minMax: [0, 2100000000000000],
        lnurl: null,
        units: ['sat', ...(this.currencies || [])],
        unit: 'sat',
        fiatProvider: '',
        data: {
          amount: null,
          memo: '',
          internalMemo: null,
          payment_hash: null
        }
      },
      update: {
        name: null,
        currency: null
      },
      hasNfc: false,
      nfcReaderAbortController: null,
      formattedFiatAmount: 0,
      formattedExchange: null,
      paymentFilter: {
        'status[ne]': 'failed'
      },
      chartConfig: Quasar.LocalStorage.getItem(
        'lnbits.wallets.chartConfig'
      ) || {
        showPaymentInOutChart: true,
        showBalanceChart: true,
        showBalanceInOutChart: true
      }
    }
  },
  computed: {
    canPay() {
      if (!this.parse.invoice) return false
      if (this.parse.invoice.expired) {
        Quasar.Notify.create({
          message: 'Invoice has expired',
          color: 'negative'
        })
        return false
      }
      return this.parse.invoice.sat <= this.g.wallet.sat
    },
    formattedAmount() {
      if (this.receive.unit != 'sat' || LNBITS_DENOMINATION != 'sats') {
        return LNbits.utils.formatCurrency(
          Number(this.receive.data.amount).toFixed(2),
          LNBITS_DENOMINATION != 'sats'
            ? LNBITS_DENOMINATION
            : this.receive.unit
        )
      } else {
        return LNbits.utils.formatMsat(this.receive.amountMsat) + ' sat'
      }
    },
    formattedSatAmount() {
      return LNbits.utils.formatMsat(this.receive.amountMsat) + ' sat'
    }
  },
  methods: {
    handleSendLnurl(lnurl) {
      this.parse.data.request = lnurl
      this.parse.show = true
      this.lnurlScan()
    },
    msatoshiFormat(value) {
      return LNbits.utils.formatSat(value / 1000)
    },
    closeCamera() {
      this.parse.camera.show = false
    },
    showCamera() {
      this.parse.camera.show = true
    },
    showReceiveDialog() {
      this.receive.show = true
      this.receive.status = 'pending'
      this.receive.paymentReq = null
      this.receive.paymentHash = null
      this.receive.data.amount = null
      this.receive.data.memo = null
      this.receive.data.internalMemo = null
      this.receive.data.payment_hash = null
      this.receive.unit = this.g.isFiatPriority
        ? this.g.wallet.currency || 'sat'
        : 'sat'
      this.receive.minMax = [0, 2100000000000000]
      this.receive.lnurl = null
    },
    onReceiveDialogHide() {
      if (this.hasNfc) {
        this.nfcReaderAbortController.abort()
      }
    },
    showParseDialog() {
      this.parse.show = true
      this.parse.invoice = null
      this.parse.lnurlpay = null
      this.parse.lnurlauth = null
      this.parse.copy.show =
        window.isSecureContext && navigator.clipboard?.readText !== undefined
      this.parse.data.request = ''
      this.parse.data.comment = ''
      this.parse.data.internalMemo = null
      this.parse.data.paymentChecker = null
      this.parse.camera.show = false
    },
    closeParseDialog() {
      setTimeout(() => {
        clearInterval(this.parse.paymentChecker)
      }, 10000)
    },
    handleBalanceUpdate(value) {
      this.g.wallet.sat = this.g.wallet.sat + value
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
    },
    async onInitQR(promise) {
      try {
        await promise
      } catch (error) {
        const mapping = {
          NotAllowedError: 'ERROR: you need to grant camera access permission',
          NotFoundError: 'ERROR: no camera on this device',
          NotSupportedError:
            'ERROR: secure context required (HTTPS, localhost)',
          NotReadableError: 'ERROR: is the camera already in use?',
          OverconstrainedError: 'ERROR: installed cameras are not suitable',
          StreamApiNotSupportedError:
            'ERROR: Stream API is not supported in this browser',
          InsecureContextError:
            'ERROR: Camera access is only permitted in secure context. Use HTTPS or localhost rather than HTTP.'
        }
        const valid_error = Object.keys(mapping).filter(key => {
          return error.name === key
        })
        const camera_error = valid_error
          ? mapping[valid_error]
          : `ERROR: Camera error (${error.name})`
        this.parse.camera.show = false
        Quasar.Notify.create({
          message: camera_error,
          type: 'negative'
        })
      }
    },
    lnurlScan() {
      LNbits.api
        .request('POST', '/api/v1/lnurlscan', this.g.wallet.adminkey, {
          lnurl: this.parse.data.request
        })
        .then(response => {
          const data = response.data
          if (data.status === 'ERROR') {
            Quasar.Notify.create({
              timeout: 5000,
              type: 'warning',
              message: `lnurl scan failed.`,
              caption: data.reason
            })
            return
          }

          if (data.tag === 'payRequest') {
            this.parse.lnurlpay = Object.freeze(data)
            this.parse.data.amount = data.minSendable / 1000
          } else if (data.tag === 'login') {
            this.parse.lnurlauth = Object.freeze(data)
          } else if (data.tag === 'withdrawRequest') {
            this.parse.show = false
            this.receive.show = true
            this.receive.lnurlWithdraw = Object.freeze(data)
            this.receive.status = 'pending'
            this.receive.paymentReq = null
            this.receive.paymentHash = null
            this.receive.data.amount = data.maxWithdrawable / 1000
            this.receive.data.memo = data.defaultDescription
            this.receive.minMax = [
              data.minWithdrawable / 1000,
              data.maxWithdrawable / 1000
            ]
            const domain = data.callback.split('/')[2]
            this.receive.lnurl = {
              domain: domain,
              callback: data.callback,
              fixed: data.fixed
            }
          }
        })
        .catch(err => {
          LNbits.utils.notifyApiError(err)
        })
    },
    decodeQR(res) {
      this.parse.data.request = res[0].rawValue
      this.decodeRequest()
      this.parse.camera.show = false
    },
    isLnurl(req) {
      return (
        req.toLowerCase().startsWith('lnurl1') ||
        req.startsWith('lnurlp://') ||
        req.startsWith('lnurlw://') ||
        req.startsWith('lnurlauth://') ||
        req.match(/[\w.+-~_]+@[\w.+-~_]/)
      )
    },
    decodeRequest() {
      this.parse.show = true
      this.parse.data.request = this.parse.data.request.trim()
      const req = this.parse.data.request.toLowerCase()
      if (req.startsWith('lightning:')) {
        this.parse.data.request = this.parse.data.request.slice(10)
      } else if (req.startsWith('lnurl:')) {
        this.parse.data.request = this.parse.data.request.slice(6)
      } else if (req.includes('lightning=lnurl1')) {
        this.parse.data.request = this.parse.data.request
          .split('lightning=')[1]
          .split('&')[0]
      }
      if (this.isLnurl(this.parse.data.request)) {
        this.lnurlScan()
        return
      }

      // BIP-21 support
      if (this.parse.data.request.toLowerCase().includes('lightning')) {
        this.parse.data.request = this.parse.data.request.split('lightning=')[1]

        // fail safe to check there's nothing after the lightning= part
        if (this.parse.data.request.includes('&')) {
          this.parse.data.request = this.parse.data.request.split('&')[0]
        }
      }

      let invoice
      try {
        invoice = decode(this.parse.data.request)
      } catch (error) {
        Quasar.Notify.create({
          timeout: 3000,
          type: 'warning',
          message: error + '.',
          caption: '400 BAD REQUEST'
        })
        this.parse.show = false
        return
      }

      let cleanInvoice = {
        msat: invoice.human_readable_part.amount,
        sat: invoice.human_readable_part.amount / 1000,
        fsat: LNbits.utils.formatSat(invoice.human_readable_part.amount / 1000),
        bolt11: this.parse.data.request
      }

      _.each(invoice.data.tags, tag => {
        if (_.isObject(tag) && _.has(tag, 'description')) {
          if (tag.description === 'payment_hash') {
            cleanInvoice.hash = tag.value
          } else if (tag.description === 'description') {
            cleanInvoice.description = tag.value
          } else if (tag.description === 'expiry') {
            const expireDate = new Date(
              (invoice.data.time_stamp + tag.value) * 1000
            )
            const createdDate = new Date(invoice.data.time_stamp * 1000)
            cleanInvoice.expireDate = Quasar.date.formatDate(
              expireDate,
              'YYYY-MM-DDTHH:mm:ss.SSSZ'
            )
            cleanInvoice.createdDate = Quasar.date.formatDate(
              createdDate,
              'YYYY-MM-DDTHH:mm:ss.SSSZ'
            )
            cleanInvoice.expireDateFrom = moment
              .utc(expireDate)
              .local()
              .fromNow()
            cleanInvoice.createdDateFrom = moment
              .utc(createdDate)
              .local()
              .fromNow()

            cleanInvoice.expired = false // TODO
          }
        }
      })

      if (this.g.wallet.currency) {
        cleanInvoice.fiatAmount = LNbits.utils.formatCurrency(
          ((cleanInvoice.sat / 1e8) * this.g.exchangeRate).toFixed(2),
          this.g.wallet.currency
        )
      }

      this.parse.invoice = Object.freeze(cleanInvoice)
    },
    payInvoice() {
      const dismissPaymentMsg = Quasar.Notify.create({
        timeout: 0,
        message: this.$t('payment_processing')
      })

      LNbits.api
        .payInvoice(
          this.g.wallet,
          this.parse.data.request,
          this.parse.data.internalMemo
        )
        .then(response => {
          dismissPaymentMsg()
          this.g.updatePayments = !this.g.updatePayments
          this.parse.show = false
          if (response.data.status == 'success') {
            Quasar.Notify.create({
              type: 'positive',
              message: this.$t('payment_successful')
            })
          }
          if (response.data.status == 'pending') {
            Quasar.Notify.create({
              type: 'info',
              message: this.$t('payment_pending')
            })
          }
        })
        .catch(err => {
          dismissPaymentMsg()
          LNbits.utils.notifyApiError(err)
          this.g.updatePayments = !this.g.updatePayments
          this.parse.show = false
        })
    },
    payLnurl() {
      LNbits.api
        .request('post', '/api/v1/payments/lnurl', this.g.wallet.adminkey, {
          res: this.parse.lnurlpay,
          lnurl: this.parse.data.request,
          unit: this.parse.data.unit,
          amount: this.parse.data.amount * 1000,
          comment: this.parse.data.comment,
          internalMemo: this.parse.data.internalMemo
        })
        .then(response => {
          this.parse.show = false
          if (response.data.extra.success_action) {
            const action = JSON.parse(response.data.extra.success_action)
            switch (action.tag) {
              case 'url':
                Quasar.Notify.create({
                  message: `<a target="_blank" style="color: inherit" href="${action.url}">${action.url}</a>`,
                  caption: action.description,
                  html: true,
                  type: 'positive',
                  timeout: 0,
                  closeBtn: true
                })
                break
              case 'message':
                Quasar.Notify.create({
                  message: action.message,
                  type: 'positive',
                  timeout: 0,
                  closeBtn: true
                })
                break
              case 'aes':
                decryptLnurlPayAES(action, response.data.preimage)
                Quasar.Notify.create({
                  message: value,
                  caption: extra.success_action.description,
                  html: true,
                  type: 'positive',
                  timeout: 0,
                  closeBtn: true
                })
            }
          }
        })
        .catch(LNbits.utils.notifyApiError)
    },
    authLnurl() {
      const dismissAuthMsg = Quasar.Notify.create({
        timeout: 10,
        message: 'Performing authentication...'
      })
      LNbits.api
        .request(
          'post',
          '/api/v1/lnurlauth',
          wallet.adminkey,
          this.parse.lnurlauth
        )
        .then(_ => {
          dismissAuthMsg()
          Quasar.Notify.create({
            message: `Authentication successful.`,
            type: 'positive',
            timeout: 3500
          })
          this.parse.show = false
        })
        .catch(err => {
          if (err.response.data.reason) {
            Quasar.Notify.create({
              message: `Authentication failed. ${this.parse.lnurlauth.callback} says:`,
              caption: err.response.data.reason,
              type: 'warning',
              timeout: 5000
            })
          } else {
            LNbits.utils.notifyApiError(err)
          }
        })
    },
    updateWallet(data) {
      LNbits.api
        .request('PATCH', '/api/v1/wallet', this.g.wallet.adminkey, data)
        .then(response => {
          this.g.wallet = {...this.g.wallet, ...response.data}
          const walletIndex = this.g.user.wallets.findIndex(
            wallet => wallet.id === response.data.id
          )
          if (walletIndex !== -1) {
            this.g.user.wallets[walletIndex] = {
              ...this.g.user.wallets[walletIndex],
              ...response.data
            }
          }
          Quasar.Notify.create({
            message: 'Wallet updated.',
            type: 'positive',
            timeout: 3500
          })
        })
        .catch(err => {
          LNbits.utils.notifyApiError(err)
        })
    },
    pasteToTextArea() {
      this.$refs.textArea.focus()
      navigator.clipboard.readText().then(text => {
        this.parse.data.request = text.trim()
      })
    },
    readNfcTag() {
      try {
        if (typeof NDEFReader == 'undefined') {
          console.debug('NFC not supported on this device or browser.')
          return
        }

        const ndef = new NDEFReader()

        this.nfcReaderAbortController = new AbortController()
        this.nfcReaderAbortController.signal.onabort = event => {
          console.debug('All NFC Read operations have been aborted.')
        }

        this.hasNfc = true
        const dismissNfcTapMsg = Quasar.Notify.create({
          message: 'Tap your NFC tag to pay this invoice with LNURLw.'
        })

        return ndef
          .scan({signal: this.nfcReaderAbortController.signal})
          .then(() => {
            ndef.onreadingerror = () => {
              Quasar.Notify.create({
                type: 'negative',
                message: 'There was an error reading this NFC tag.'
              })
            }

            ndef.onreading = ({message}) => {
              //Decode NDEF data from tag
              const textDecoder = new TextDecoder('utf-8')

              const record = message.records.find(el => {
                const payload = textDecoder.decode(el.data)
                return payload.toUpperCase().indexOf('LNURLW') !== -1
              })

              if (record) {
                dismissNfcTapMsg()
                Quasar.Notify.create({
                  type: 'positive',
                  message: 'NFC tag read successfully.'
                })
                const lnurl = textDecoder.decode(record.data)
                this.payInvoiceWithNfc(lnurl)
              } else {
                Quasar.Notify.create({
                  type: 'warning',
                  message: 'NFC tag does not have LNURLw record.'
                })
              }
            }
          })
      } catch (error) {
        Quasar.Notify.create({
          type: 'negative',
          message: error
            ? error.toString()
            : 'An unexpected error has occurred.'
        })
      }
    },
    payInvoiceWithNfc(lnurl) {
      const dismissPaymentMsg = Quasar.Notify.create({
        timeout: 0,
        spinner: true,
        message: this.$t('processing_payment')
      })

      LNbits.api
        .request(
          'POST',
          `/api/v1/payments/${this.receive.paymentReq}/pay-with-nfc`,
          this.g.wallet.adminkey,
          {lnurl_w: lnurl}
        )
        .then(response => {
          dismissPaymentMsg()
          if (response.data.success) {
            Quasar.Notify.create({
              type: 'positive',
              message: 'Payment successful'
            })
          } else {
            Quasar.Notify.create({
              type: 'negative',
              message: response.data.detail || 'Payment failed'
            })
          }
        })
        .catch(err => {
          dismissPaymentMsg()
          LNbits.utils.notifyApiError(err)
        })
    }
  },
  created() {
    const urlParams = new URLSearchParams(window.location.search)
    if (urlParams.has('lightning') || urlParams.has('lnurl')) {
      this.parse.data.request =
        urlParams.get('lightning') || urlParams.get('lnurl')
      this.decodeRequest()
      this.parse.show = true
    }
    if (urlParams.has('wal')) {
      const wallet = g.user.wallets.find(w => w.id === urlParams.get('wal'))
      if (wallet) {
        this.selectWallet(wallet)
      }
    } else {
      const wallet = g.user.wallets.find(w => w.id === this.g.lastActiveWallet)
      if (wallet) {
        this.selectWallet(wallet)
      } else if (g.user.wallets.length > 0) {
        this.selectWallet(g.user.wallets[0])
      }
    }
  },
  watch: {
    'g.lastActiveWallet'(val) {
      this.$q.localStorage.setItem('lnbits.lastActiveWallet', val)
    },
    'g.updatePayments'() {
      this.parse.show = false
      if (this.receive.paymentHash === this.g.updatePaymentsHash) {
        this.receive.show = false
        this.receive.paymentHash = null
      }
      if (
        this.g.wallet.currency &&
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
    },
    'g.wallet'() {
      if (this.g.wallet.currency) {
        this.g.fiatTracking = true
        this.g.fiatBalance =
          (this.g.exchangeRate / 100000000) * this.g.wallet.sat
      } else {
        this.g.fiatBalance = 0
        this.g.fiatTracking = false
      }
    },
    'g.isFiatPriority'() {
      this.receive.unit = this.g.isFiatPriority ? this.g.wallet.currency : 'sat'
    },
    'g.fiatBalance'() {
      this.formattedFiatAmount = LNbits.utils.formatCurrency(
        this.g.fiatBalance.toFixed(2),
        this.g.wallet.currency
      )
    },
    'g.exchangeRate'() {
      if (this.g.fiatTracking && this.g.wallet.currency) {
        this.g.fiatBalance =
          (this.g.exchangeRate / 100000000) * this.g.wallet.sat
        this.formattedExchange = LNbits.utils.formatCurrency(
          this.g.exchangeRate,
          this.g.wallet.currency
        )
      }
    }
  }
}
