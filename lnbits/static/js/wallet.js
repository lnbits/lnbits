window.WalletPageLogic = {
  mixins: [window.windowMixin],
  data() {
    return {
      origin: window.location.origin,
      baseUrl: `${window.location.protocol}//${window.location.host}/`,
      websocketUrl: `${'http:' ? 'ws://' : 'wss://'}${window.location.host}/api/v1/ws`,
      stored_paylinks: [],
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
        units: ['sat'],
        unit: 'sat',
        fiatProvider: '',
        data: {
          amount: null,
          memo: '',
          internalMemo: null,
          payment_hash: null
        }
      },
      disclaimerDialog: {
        show: false,
        location: window.location
      },
      icon: {
        show: false,
        data: {},
        colorOptions: [
          'primary',
          'purple',
          'orange',
          'green',
          'brown',
          'blue',
          'red',
          'pink'
        ],
        options: [
          'home',
          'star',
          'bolt',
          'paid',
          'savings',
          'store',
          'videocam',
          'music_note',
          'flight',
          'train',
          'directions_car',
          'school',
          'construction',
          'science',
          'sports_esports',
          'sports_tennis',
          'theaters',
          'water',
          'headset_mic',
          'videogame_asset',
          'person',
          'group',
          'pets',
          'sunny',
          'elderly',
          'verified',
          'snooze',
          'mail',
          'forum',
          'shopping_cart',
          'shopping_bag',
          'attach_money',
          'print_connect',
          'dark_mode',
          'light_mode',
          'android',
          'network_wifi',
          'shield',
          'fitness_center',
          'lunch_dining'
        ]
      },
      update: {
        name: null,
        currency: null
      },
      walletBalanceChart: null,
      inkeyHidden: true,
      adminkeyHidden: true,
      walletIdHidden: true,
      hasNfc: false,
      nfcReaderAbortController: null,
      isFiatPriority: false,
      formattedFiatAmount: 0,
      formattedExchange: null,
      chartData: [],
      chartDataPointCount: 0,
      chartConfig: {
        showBalance: true,
        showBalanceInOut: true,
        showPaymentCountInOut: true
      },
      paymentsFilter: {}
    }
  },
  computed: {
    formattedBalance() {
      if (LNBITS_DENOMINATION != 'sats') {
        return LNbits.utils.formatCurrency(
          this.g.wallet.sat / 100,
          LNBITS_DENOMINATION
        )
      } else {
        return LNbits.utils.formatSat(this.g.wallet.sat)
      }
    },
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
    },
    wallet() {
      return this.g.wallet
    },
    hasChartActive() {
      return (
        this.chartConfig.showBalance ||
        this.chartConfig.showBalanceInOut ||
        this.chartConfig.showPaymentCountInOut
      )
    }
  },
  methods: {
    dateFromNow(unix) {
      const date = new Date(unix * 1000)
      return moment.utc(date).local().fromNow()
    },
    formatFiatAmount(amount, currency) {
      this.update.currency = currency
      this.formattedFiatAmount = LNbits.utils.formatCurrency(
        amount.toFixed(2),
        currency
      )
      this.formattedExchange = LNbits.utils.formatCurrency(
        this.g.exchangeRate,
        currency
      )
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
    focusInput(el) {
      this.$nextTick(() => this.$refs[el].focus())
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
      this.receive.unit = this.isFiatPriority
        ? this.g.wallet.currency || 'sat'
        : 'sat'
      this.receive.minMax = [0, 2100000000000000]
      this.receive.lnurl = null
      this.focusInput('setAmount')
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
      this.focusInput('textArea')
    },
    closeParseDialog() {
      setTimeout(() => {
        clearInterval(this.parse.paymentChecker)
      }, 10000)
    },
    handleBalanceUpdate(value) {
      this.g.wallet.sat = this.g.wallet.sat + value
    },
    setSelectedIcon(selectedIcon) {
      this.icon.data.icon = selectedIcon
    },
    setSelectedColor(selectedColor) {
      this.icon.data.color = selectedColor
    },
    setIcon() {
      this.updateWallet(this.icon.data)
      this.icon.show = false
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
          this.updatePayments = !this.updatePayments
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
    updateFiatBalance(currency) {
      // set rate from local storage to avoid clunky api calls
      if (this.$q.localStorage.getItem('lnbits.exchangeRate.' + currency)) {
        this.g.exchangeRate = this.$q.localStorage.getItem(
          'lnbits.exchangeRate.' + currency
        )
        this.g.fiatBalance =
          (this.g.exchangeRate / 100000000) * this.g.wallet.sat
        this.formatFiatAmount(this.g.fiatBalance, currency)
      }
      if (currency && this.g.wallet.currency == currency) {
        LNbits.api
          .request('GET', `/api/v1/rate/` + currency, null)
          .then(response => {
            this.g.fiatBalance =
              (response.data.price / 100000000) * this.g.wallet.sat
            this.g.exchangeRate = response.data.price.toFixed(2)
            this.g.fiatTracking = true
            this.formatFiatAmount(this.g.fiatBalance, this.g.wallet.currency)
            this.$q.localStorage.set(
              'lnbits.exchangeRate.' + currency,
              this.g.exchangeRate
            )
          })
          .catch(e => console.error(e))
      }
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
    },
    swapBalancePriority() {
      this.isFiatPriority = !this.isFiatPriority
      this.receive.unit = this.isFiatPriority
        ? this.g.wallet.currency || 'sat'
        : 'sat'
      this.$q.localStorage.setItem('lnbits.isFiatPriority', this.isFiatPriority)
    },
    handleFiatTracking() {
      this.g.fiatTracking = !this.g.fiatTracking
      if (!this.g.fiatTracking) {
        this.$q.localStorage.setItem('lnbits.isFiatPriority', false)
        this.isFiatPriority = false
        this.update.currency = ''
        this.g.wallet.currency = ''
        this.updateWallet({currency: ''})
      } else {
        this.g.wallet.currency = this.update.currency
        this.updateWallet({currency: this.update.currency})
        this.updateFiatBalance(this.update.currency)
      }
    },
    createdTasks() {
      this.update.name = this.g.wallet.name
      this.receive.units = ['sat', ...(window.currencies || [])]
      if (this.g.wallet.currency != '' && LNBITS_DENOMINATION == 'sats') {
        this.g.fiatTracking = true
        this.updateFiatBalance(this.g.wallet.currency)
      } else {
        this.update.currency = ''
        this.g.fiatTracking = false
      }
    },
    walletFormatBalance(amount) {
      if (LNBITS_DENOMINATION != 'sats') {
        return LNbits.utils.formatCurrency(amount / 100, LNBITS_DENOMINATION)
      } else {
        return LNbits.utils.formatSat(amount) + ' sats'
      }
    },
    handleFilterChange(value = {}) {
      if (
        this.paymentsFilter['time[ge]'] !== value['time[ge]'] ||
        this.paymentsFilter['time[le]'] !== value['time[le]'] ||
        this.paymentsFilter['amount[ge]'] !== value['amount[ge]'] ||
        this.paymentsFilter['amount[le]'] !== value['amount[le]']
      ) {
        this.refreshCharts()
      }
      this.paymentsFilter = value
    },
    async fetchChartData() {
      if (this.g.mobileSimple) {
        this.chartConfig = {}
        return
      }
      if (!this.hasChartActive) {
        return
      }

      try {
        const {data} = await LNbits.api.request(
          'GET',
          `/api/v1/payments/stats/daily?wallet_id=${this.g.wallet.id}`
        )
        this.chartData = data
        this.refreshCharts()
      } catch (error) {
        console.warn(error)
        LNbits.utils.notifyApiError(error)
      }
    },
    filterChartData(data) {
      const timeFrom = this.paymentsFilter['time[ge]'] + 'T00:00:00'
      const timeTo = this.paymentsFilter['time[le]'] + 'T23:59:59'

      let totalBalance = 0
      data = data.map(p => {
        if (this.paymentsFilter['amount[ge]'] !== undefined) {
          totalBalance += p.balance_in
          return {...p, balance: totalBalance, balance_out: 0, count_out: 0}
        }
        if (this.paymentsFilter['amount[le]'] !== undefined) {
          totalBalance -= p.balance_out
          return {...p, balance: totalBalance, balance_in: 0, count_in: 0}
        }
        return {...p}
      })
      data = data.filter(p => {
        if (
          this.paymentsFilter['time[ge]'] &&
          this.paymentsFilter['time[le]']
        ) {
          return p.date >= timeFrom && p.date <= timeTo
        }
        if (this.paymentsFilter['time[ge]']) {
          return p.date >= timeFrom
        }
        if (this.paymentsFilter['time[le]']) {
          return p.date <= timeTo
        }
        return true
      })

      const labels = data.map(s =>
        new Date(s.date).toLocaleString('default', {
          month: 'short',
          day: 'numeric'
        })
      )
      this.chartDataPointCount = data.length
      return {data, labels}
    },
    refreshCharts() {
      const originalChartConfig = this.chartConfig || {}
      this.chartConfig = {}
      setTimeout(() => {
        const chartConfig =
          this.$q.localStorage.getItem('lnbits.wallets.chartConfig') ||
          originalChartConfig
        this.chartConfig = {...originalChartConfig, ...chartConfig}
      }, 10)
      setTimeout(() => {
        this.drawCharts(this.chartData)
      }, 100)
    },
    drawCharts(allData) {
      try {
        const {data, labels} = this.filterChartData(allData)
        if (this.chartConfig.showBalance) {
          if (this.walletBalanceChart) {
            this.walletBalanceChart.destroy()
          }

          this.walletBalanceChart = new Chart(
            this.$refs.walletBalanceChart.getContext('2d'),
            {
              type: 'line',
              options: {
                responsive: true,
                maintainAspectRatio: false
              },
              data: {
                labels,
                datasets: [
                  {
                    label: 'Balance',
                    data: data.map(s => s.balance),
                    pointStyle: false,
                    backgroundColor: Quasar.colors.changeAlpha(
                      Quasar.colors.getPaletteColor('primary'),
                      0.3
                    ),
                    borderColor: Quasar.colors.getPaletteColor('primary'),
                    borderWidth: 2,
                    fill: true,
                    tension: 0.7,
                    fill: 1
                  },
                  {
                    label: 'Fees',
                    data: data.map(s => s.fee),
                    pointStyle: false,
                    backgroundColor: Quasar.colors.changeAlpha(
                      Quasar.colors.getPaletteColor('secondary'),
                      0.3
                    ),
                    borderColor: Quasar.colors.getPaletteColor('secondary'),
                    borderWidth: 1,
                    fill: true,
                    tension: 0.7,
                    fill: 1
                  }
                ]
              }
            }
          )
        }

        if (this.chartConfig.showBalanceInOut) {
          if (this.walletBalanceInOut) {
            this.walletBalanceInOut.destroy()
          }

          this.walletBalanceInOut = new Chart(
            this.$refs.walletBalanceInOut.getContext('2d'),
            {
              type: 'bar',

              options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                  x: {
                    stacked: true
                  },
                  y: {
                    stacked: true
                  }
                }
              },
              data: {
                labels,
                datasets: [
                  {
                    label: 'Balance In',
                    borderRadius: 5,
                    data: data.map(s => s.balance_in),
                    backgroundColor: Quasar.colors.changeAlpha(
                      Quasar.colors.getPaletteColor('primary'),
                      0.3
                    )
                  },
                  {
                    label: 'Balance Out',
                    borderRadius: 5,
                    data: data.map(s => s.balance_out),
                    backgroundColor: Quasar.colors.changeAlpha(
                      Quasar.colors.getPaletteColor('secondary'),
                      0.3
                    )
                  }
                ]
              }
            }
          )
        }

        if (this.chartConfig.showPaymentCountInOut) {
          if (this.walletPaymentsInOut) {
            this.walletPaymentsInOut.destroy()
          }

          this.walletPaymentsInOut = new Chart(
            this.$refs.walletPaymentsInOut.getContext('2d'),
            {
              type: 'bar',

              options: {
                responsive: true,
                maintainAspectRatio: false,

                scales: {
                  x: {
                    stacked: true
                  },
                  y: {
                    stacked: true
                  }
                }
              },
              data: {
                labels,
                datasets: [
                  {
                    label: 'Payments In',
                    data: data.map(s => s.count_in),
                    backgroundColor: Quasar.colors.changeAlpha(
                      Quasar.colors.getPaletteColor('primary'),
                      0.3
                    )
                  },
                  {
                    label: 'Payments Out',
                    data: data.map(s => -s.count_out),
                    backgroundColor: Quasar.colors.changeAlpha(
                      Quasar.colors.getPaletteColor('secondary'),
                      0.3
                    )
                  }
                ]
              }
            }
          )
        }
      } catch (error) {
        console.warn(error)
      }
    },
    saveChartsPreferences() {
      this.$q.localStorage.set('lnbits.wallets.chartConfig', this.chartConfig)
      this.refreshCharts()
    },
    updatePaylinks() {
      LNbits.api
        .request(
          'PUT',
          `/api/v1/wallet/stored_paylinks/${this.g.wallet.id}`,
          this.g.wallet.adminkey,
          {
            links: this.stored_paylinks
          }
        )
        .then(() => {
          Quasar.Notify.create({
            message: 'Paylinks updated.',
            type: 'positive',
            timeout: 3500
          })
        })
        .catch(err => {
          LNbits.utils.notifyApiError(err)
        })
    },
    sendToPaylink(lnurl) {
      this.parse.data.request = lnurl
      this.parse.show = true
      this.lnurlScan()
    },
    editPaylink() {
      this.$nextTick(() => {
        this.updatePaylinks()
      })
    },
    deletePaylink(lnurl) {
      const links = []
      this.stored_paylinks.forEach(link => {
        if (link.lnurl !== lnurl) {
          links.push(link)
        }
      })
      this.stored_paylinks = links
      this.updatePaylinks()
    }
  },
  created() {
    this.stored_paylinks = wallet.stored_paylinks.links
    const urlParams = new URLSearchParams(window.location.search)
    if (urlParams.has('lightning') || urlParams.has('lnurl')) {
      this.parse.data.request =
        urlParams.get('lightning') || urlParams.get('lnurl')
      this.decodeRequest()
      this.parse.show = true
    }
    this.createdTasks()
    try {
      this.fetchChartData()
    } catch (error) {
      console.warn(`Chart creation failed: ${error}`)
    }
  },
  watch: {
    'g.updatePayments'(newVal, oldVal) {
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
        this.formatFiatAmount(this.g.fiatBalance, this.g.wallet.currency)
      }
    },
    'g.wallet': {
      handler() {
        try {
          this.createdTasks()
        } catch (error) {
          console.warn(`Chart creation failed: ${error}`)
        }
      },
      deep: true
    }
  },
  async mounted() {
    if (!Quasar.LocalStorage.getItem('lnbits.disclaimerShown')) {
      this.disclaimerDialog.show = true
      Quasar.LocalStorage.setItem('lnbits.disclaimerShown', true)
      Quasar.LocalStorage.setItem('lnbits.reactions', 'confettiTop')
    }
    if (Quasar.LocalStorage.getItem('lnbits.isFiatPriority')) {
      this.isFiatPriority = Quasar.LocalStorage.getItem('lnbits.isFiatPriority')
    } else {
      this.isFiatPriority = false
      Quasar.LocalStorage.setItem('lnbits.isFiatPriority', false)
    }
  }
}

if (navigator.serviceWorker != null) {
  navigator.serviceWorker.register('/service-worker.js').then(registration => {
    console.log('Registered events at scope: ', registration.scope)
  })
}
