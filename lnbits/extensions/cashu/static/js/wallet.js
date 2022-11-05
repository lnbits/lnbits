var currentDateStr = function () {
  return Quasar.utils.date.formatDate(new Date(), 'YYYY-MM-DD HH:mm')
}
var mapMint = function (obj) {
  obj.date = Quasar.utils.date.formatDate(
    new Date(obj.time * 1000),
    'YYYY-MM-DD HH:mm'
  )
  obj.fsat = new Intl.NumberFormat(LOCALE).format(obj.amount)
  obj.cashu = ['/cashu/', obj.id].join('')
  return obj
}

Vue.component(VueQrcode.name, VueQrcode)

new Vue({
  el: '#vue',
  mixins: [windowMixin],
  data: function () {
    return {
      tickershort: '',
      name: '',

      mintId: '',
      mintName: '',
      keys: '',
      invoicesCashu: [],
      invoiceData: {
        amount: 0,
        memo: '',
        bolt11: '',
        hash: ''
      },
      invoiceCheckListener: () => {},
      payInvoiceData: {
        // invoice: '',
        bolt11: '',
        // camera: {
        //   show: false,
        //   camera: 'auto'
        // }
        show: false,
        invoice: null,
        lnurlpay: null,
        lnurlauth: null,
        data: {
          request: '',
          amount: 0,
          comment: ''
        },
        paymentChecker: null,
        camera: {
          show: false,
          camera: 'auto'
        }
      },
      sendData: {
        amount: 0,
        memo: '',
        tokens: '',
        tokensBase64: ''
      },
      receiveData: {
        tokensBase64: ''
      },
      showInvoiceDetails: false,
      showPayInvoice: false,
      showSendTokens: false,
      showReceiveTokens: false,
      promises: [],
      tokens: [],
      tab: 'tokens',

      receive: {
        show: false,
        status: 'pending',
        paymentReq: null,
        paymentHash: null,
        minMax: [0, 2100000000000000],
        lnurl: null,
        units: ['sat'],
        unit: 'sat',
        data: {
          amount: null,
          memo: ''
        }
      },
      parse: {
        show: false,
        invoice: null,
        lnurlpay: null,
        lnurlauth: null,
        data: {
          request: '',
          amount: 0,
          comment: ''
        },
        paymentChecker: null,
        camera: {
          show: false,
          camera: 'auto'
        }
      },
      payments: [],
      invoicesTable: {
        columns: [
          {
            name: 'status',
            align: 'left',
            label: '',
            field: 'status'
          },
          {
            name: 'amount',
            align: 'left',
            label: 'Amount',
            field: 'amount'
          },
          {
            name: 'memo',
            align: 'left',
            label: 'Memo',
            field: 'memo',
            sortable: true
          },
          {
            name: 'date',
            align: 'left',
            label: 'Date',
            field: 'date',
            sortable: true
          },
          {
            name: 'hash',
            align: 'right',
            label: 'Hash',
            field: 'hash',
            sortable: true
          }
        ],
        pagination: {
          sortBy: 'date',
          descending: true,
          rowsPerPage: 5
        },
        filter: null
      },

      tokensTable: {
        columns: [
          {
            name: 'value',
            align: 'left',
            label: 'Value ({{LNBITS_DENOMINATION}})',
            field: 'value',
            sortable: true
          },
          {
            name: 'count',
            align: 'left',
            label: 'Count',
            field: 'count',
            sortable: true
          },
          {
            name: 'sum',
            align: 'left',
            label: 'Sum ({{LNBITS_DENOMINATION}})',
            field: 'sum',
            sortable: true
          }
          // {
          //   name: 'memo',
          //   align: 'left',
          //   label: 'Memo',
          //   field: 'memo',
          //   sortable: true
          // }
        ],
        pagination: {
          rowsPerPage: 5
        },
        filter: null
      },

      paymentsChart: {
        show: false
      },
      disclaimerDialog: {
        show: false,
        location: window.location
      },

      credit: 0,
      newName: ''
    }
  },
  computed: {
    formattedBalance: function () {
      return this.balance / 100
    },

    canPay: function () {
      if (!this.payInvoiceData.invoice) return false
      return this.payInvoiceData.invoice.sat <= this.balance
    },
    pendingPaymentsExist: function () {
      return this.payments.findIndex(payment => payment.pending) !== -1
    },

    balance: function () {
      return this.proofs
        .map(t => t)
        .flat()
        .reduce((sum, el) => (sum += el.amount), 0)
    }
  },
  filters: {
    msatoshiFormat: function (value) {
      return LNbits.utils.formatSat(value / 1000)
    }
  },
  methods: {
    getBalance: function () {
      return this.proofs
        .map(t => t)
        .flat()
        .reduce((sum, el) => (sum += el.amount), 0)
    },
    getTokenList: function () {
      const x = this.proofs
        .map(t => t.amount)
        .reduce((acc, amount) => {
          acc[amount] = acc[amount] + amount || 1
          return acc
        }, {})
      return Object.keys(x).map(k => ({
        value: k,
        count: x[k],
        sum: k * x[k]
      }))
    },

    paymentTableRowKey: function (row) {
      return row.payment_hash + row.amount
    },
    closeCamera: function () {
      this.payInvoiceData.camera.show = false
    },
    showCamera: function () {
      this.payInvoiceData.camera.show = true
    },
    showChart: function () {
      this.paymentsChart.show = true
      this.$nextTick(() => {
        generateChart(this.$refs.canvas, this.payments)
      })
    },
    focusInput(el) {
      this.$nextTick(() => this.$refs[el].focus())
    },
    showReceiveDialog: function () {
      this.receive.show = true
      this.receive.status = 'pending'
      this.receive.paymentReq = null
      this.receive.paymentHash = null
      this.receive.data.amount = null
      this.receive.data.memo = null
      this.receive.unit = 'sat'
      this.receive.paymentChecker = null
      this.receive.minMax = [0, 2100000000000000]
      this.receive.lnurl = null
      this.focusInput('setAmount')
    },
    showParseDialog: function () {
      this.payInvoiceData.show = true
      this.payInvoiceData.invoice = null
      this.payInvoiceData.lnurlpay = null
      this.payInvoiceData.lnurlauth = null
      this.payInvoiceData.data.request = ''
      this.payInvoiceData.data.comment = ''
      this.payInvoiceData.data.paymentChecker = null
      this.payInvoiceData.camera.show = false
      this.focusInput('pasteInput')
    },
    showDisclaimerDialog: function () {
      this.disclaimerDialog.show = true
    },

    closeReceiveDialog: function () {
      setTimeout(() => {
        clearInterval(this.receive.paymentChecker)
      }, 10000)
    },
    closeParseDialog: function () {
      setTimeout(() => {
        clearInterval(this.payInvoiceData.paymentChecker)
      }, 10000)
    },
    onPaymentReceived: function (paymentHash) {
      this.fetchPayments()
      this.fetchBalance()

      if (this.receive.paymentHash === paymentHash) {
        this.receive.show = false
        this.receive.paymentHash = null
        clearInterval(this.receive.paymentChecker)
      }
    },
    createInvoice: function () {
      this.receive.status = 'loading'
      if (LNBITS_DENOMINATION != 'sats') {
        this.receive.data.amount = this.receive.data.amount * 100
      }
      LNbits.api
        .createInvoice(
          this.receive.data.amount,
          this.receive.data.memo,
          this.receive.unit,
          this.receive.lnurl && this.receive.lnurl.callback
        )
        .then(response => {
          this.receive.status = 'success'
          this.receive.paymentReq = response.data.payment_request
          this.receive.paymentHash = response.data.payment_hash

          if (response.data.lnurl_response !== null) {
            if (response.data.lnurl_response === false) {
              response.data.lnurl_response = `Unable to connect`
            }

            if (typeof response.data.lnurl_response === 'string') {
              // failure
              this.$q.notify({
                timeout: 5000,
                type: 'warning',
                message: `${this.receive.lnurl.domain} lnurl-withdraw call failed.`,
                caption: response.data.lnurl_response
              })
              return
            } else if (response.data.lnurl_response === true) {
              // success
              this.$q.notify({
                timeout: 5000,
                message: `Invoice sent to ${this.receive.lnurl.domain}!`,
                spinner: true
              })
            }
          }

          clearInterval(this.receive.paymentChecker)
          setTimeout(() => {
            clearInterval(this.receive.paymentChecker)
          }, 40000)
        })
        .catch(err => {
          LNbits.utils.notifyApiError(err)
          this.receive.status = 'pending'
        })
    },
    decodeQR: function (res) {
      this.payInvoiceData.data.request = res
      this.decodeRequest()
      this.payInvoiceData.camera.show = false
    },
    decodeRequest: function () {
      this.payInvoiceData.show = true
      let req = this.payInvoiceData.data.request.toLowerCase()
      if (
        this.payInvoiceData.data.request.toLowerCase().startsWith('lightning:')
      ) {
        this.payInvoiceData.data.request = this.payInvoiceData.data.request.slice(
          10
        )
      } else if (
        this.payInvoiceData.data.request.toLowerCase().startsWith('lnurl:')
      ) {
        this.payInvoiceData.data.request = this.payInvoiceData.data.request.slice(
          6
        )
      } else if (req.indexOf('lightning=lnurl1') !== -1) {
        this.payInvoiceData.data.request = this.payInvoiceData.data.request
          .split('lightning=')[1]
          .split('&')[0]
      }

      if (
        this.payInvoiceData.data.request.toLowerCase().startsWith('lnurl1') ||
        this.payInvoiceData.data.request.match(/[\w.+-~_]+@[\w.+-~_]/)
      ) {
        return
      }

      let invoice
      try {
        invoice = decode(this.payInvoiceData.data.request)
      } catch (error) {
        this.$q.notify({
          timeout: 3000,
          type: 'warning',
          message: error + '.',
          caption: '400 BAD REQUEST'
        })
        this.payInvoiceData.show = false
        throw error
        return
      }

      let cleanInvoice = {
        msat: invoice.human_readable_part.amount,
        sat: invoice.human_readable_part.amount / 1000,
        fsat: LNbits.utils.formatSat(invoice.human_readable_part.amount / 1000)
      }

      _.each(invoice.data.tags, tag => {
        if (_.isObject(tag) && _.has(tag, 'description')) {
          if (tag.description === 'payment_hash') {
            cleanInvoice.hash = tag.value
          } else if (tag.description === 'description') {
            cleanInvoice.description = tag.value
          } else if (tag.description === 'expiry') {
            var expireDate = new Date(
              (invoice.data.time_stamp + tag.value) * 1000
            )
            cleanInvoice.expireDate = Quasar.utils.date.formatDate(
              expireDate,
              'YYYY-MM-DDTHH:mm:ss.SSSZ'
            )
            cleanInvoice.expired = false // TODO
          }
        }
      })

      this.payInvoiceData.invoice = Object.freeze(cleanInvoice)
    },
    payInvoice: function () {
      let dismissPaymentMsg = this.$q.notify({
        timeout: 0,
        message: 'Processing payment...'
      })
    },
    payLnurl: function () {
      let dismissPaymentMsg = this.$q.notify({
        timeout: 0,
        message: 'Processing payment...'
      })
    },
    authLnurl: function () {
      let dismissAuthMsg = this.$q.notify({
        timeout: 10,
        message: 'Performing authentication...'
      })
    },

    deleteWallet: function (walletId, user) {
      LNbits.utils
        .confirmDialog('Are you sure you want to delete this wallet?')
        .onOk(() => {
          LNbits.href.deleteWallet(walletId, user)
        })
    },
    fetchPayments: function () {
      return
    },
    fetchBalance: function () {},
    exportCSV: function () {
      // status is important for export but it is not in paymentsTable
      // because it is manually added with payment detail link and icons
      // and would cause duplication in the list
      let columns = this.paymentsTable.columns
      columns.unshift({
        name: 'pending',
        align: 'left',
        label: 'Pending',
        field: 'pending'
      })
      LNbits.utils.exportCSV(columns, this.payments)
    },

    /////////////////////////////////// WALLET ///////////////////////////////////
    showInvoicesDialog: async function () {
      console.log('##### showInvoicesDialog')
      this.invoiceData.amount = 0
      this.invoiceData.bolt11 = ''
      this.invoiceData.hash = ''
      this.invoiceData.memo = ''
      this.showInvoiceDetails = true
    },

    showInvoiceDialog: function (data) {
      console.log('##### showInvoiceDialog')
      this.invoiceData = _.clone(data)
      this.showInvoiceDetails = true
    },

    showPayInvoiceDialog: function () {
      console.log('### showPayInvoiceDialog')
      this.payInvoiceData.invoice = ''
      this.payInvoiceData.data.request = ''
      this.showPayInvoice = true
      this.payInvoiceData.camera.show = false
    },

    showSendTokensDialog: function () {
      this.sendData.tokens = ''
      this.sendData.tokensBase64 = ''
      this.sendData.amount = 0
      this.sendData.memo = ''
      this.showSendTokens = true
    },

    showReceiveTokensDialog: function () {
      this.receiveData.tokensBase64 = ''
      this.showReceiveTokens = true
    },

    //////////////////////// MINT //////////////////////////////////////////
    requestMintButton: async function () {
      await this.requestMint()
      console.log('this is your invoice BEFORE')
      console.log(this.invoiceData)
      this.invoiceCheckListener = setInterval(async () => {
        try {
          console.log('this is your invoice AFTER')
          console.log(this.invoiceData)
          await this.recheckInvoice(this.invoiceData.hash, false)
          clearInterval(this.invoiceCheckListener)
          this.invoiceData.bolt11 = ''
          this.showInvoiceDetails = false
          navigator.vibrate(200)
          this.$q.notify({
            timeout: 5000,
            type: 'positive',
            message: 'Payment received'
          })
        } catch (error) {
          console.log('not paid yet')
        }
      }, 3000)
    },

    requestMint: async function () {
      // gets an invoice from the mint to get new tokens
      try {
        const {data} = await LNbits.api.request(
          'GET',
          `/cashu/api/v1/${this.mintId}/mint?amount=${this.invoiceData.amount}`
        )
        console.log('### data', data)

        this.invoiceData.bolt11 = data.pr
        this.invoiceData.hash = data.hash
        this.invoicesCashu.push({
          ..._.clone(this.invoiceData),
          date: currentDateStr(),
          status: 'pending'
        })
        this.storeinvoicesCashu()
        this.tab = 'invoices'
        return data
      } catch (error) {
        console.error(error)
        LNbits.utils.notifyApiError(error)
        throw error
      }
    },
    mintApi: async function (amounts, payment_hash, verbose = true) {
      console.log('### promises', payment_hash)
      try {
        let secrets = await this.generateSecrets(amounts)
        let {blindedMessages, rs} = await this.constructOutputs(
          amounts,
          secrets
        )
        const promises = await LNbits.api.request(
          'POST',
          `/cashu/api/v1/${this.mintId}/mint?payment_hash=${payment_hash}`,
          '',
          {
            blinded_messages: blindedMessages
          }
        )
        console.log('### promises data', promises.data)
        let proofs = await this.constructProofs(promises.data, secrets, rs)
        return proofs
      } catch (error) {
        console.error(error)
        if (verbose) {
          LNbits.utils.notifyApiError(error)
        }
        throw error
      }
    },
    mint: async function (amount, payment_hash, verbose = true) {
      try {
        const split = splitAmount(amount)
        const proofs = await this.mintApi(split, payment_hash, verbose)
        if (!proofs.length) {
          throw 'could not mint'
        }
        this.proofs = this.proofs.concat(proofs)
        this.storeProofs()
        await this.setInvoicePaid(payment_hash)
        return proofs
      } catch (error) {
        console.error(error)
        if (verbose) {
          LNbits.utils.notifyApiError(error)
        }
        throw error
      }
    },
    setInvoicePaid: async function (payment_hash) {
      const invoice = this.invoicesCashu.find(i => i.hash === payment_hash)
      invoice.status = 'paid'
      this.storeinvoicesCashu()
    },
    recheckInvoice: async function (payment_hash, verbose = true) {
      console.log('### recheckInvoice.hash', payment_hash)
      const invoice = this.invoicesCashu.find(i => i.hash === payment_hash)
      try {
        proofs = await this.mint(invoice.amount, invoice.hash, verbose)
        return proofs
      } catch (error) {
        console.log('Invoice still pending')
        throw error
      }
    },

    generateSecrets: async function (amounts) {
      const secrets = []
      for (let i = 0; i < amounts.length; i++) {
        const secret = nobleSecp256k1.utils.randomBytes(32)
        secrets.push(secret)
      }
      return secrets
    },

    constructOutputs: async function (amounts, secrets) {
      const blindedMessages = []
      const rs = []
      for (let i = 0; i < amounts.length; i++) {
        const {B_, r} = await step1Alice(secrets[i])
        blindedMessages.push({amount: amounts[i], B_: B_})
        rs.push(r)
      }
      return {
        blindedMessages,
        rs
      }
    },

    constructProofs: function (promises, secrets, rs) {
      const proofs = []
      for (let i = 0; i < promises.length; i++) {
        const encodedSecret = uint8ToBase64.encode(secrets[i])
        let {id, amount, C, secret} = this.promiseToProof(
          promises[i].id,
          promises[i].amount,
          promises[i]['C_'],
          encodedSecret,
          rs[i]
        )
        proofs.push({id, amount, C, secret})
      }
      return proofs
    },

    promiseToProof: function (id, amount, C_hex, secret, r) {
      const C_ = nobleSecp256k1.Point.fromHex(C_hex)
      const A = this.keys[amount]
      const C = step3Alice(
        C_,
        nobleSecp256k1.utils.hexToBytes(r),
        nobleSecp256k1.Point.fromHex(A)
      )
      return {
        id,
        amount,
        C: C.toHex(true),
        secret
      }
    },

    sumProofs: function (proofs) {
      return proofs.reduce((s, t) => (s += t.amount), 0)
    },
    splitToSend: async function (proofs, amount, invlalidate = false) {
      // splits proofs so the user can keep firstProofs, send scndProofs
      try {
        const spendableProofs = proofs.filter(p => !p.reserved)
        if (this.sumProofs(spendableProofs) < amount) {
          throw new Error('balance too low.')
        }
        let {fristProofs, scndProofs} = await this.split(
          spendableProofs,
          amount
        )

        // set scndProofs in this.proofs as reserved
        const usedSecrets = proofs.map(p => p.secret)
        for (let i = 0; i < this.proofs.length; i++) {
          if (usedSecrets.includes(this.proofs[i].secret)) {
            this.proofs[i].reserved = true
          }
        }
        if (invlalidate) {
          // delete tokens from db
          this.proofs = fristProofs
          // add new fristProofs, scndProofs to this.proofs
          this.storeProofs()
        }

        return {fristProofs, scndProofs}
      } catch (error) {
        console.error(error)
        LNbits.utils.notifyApiError(error)
        throw error
      }
    },

    split: async function (proofs, amount) {
      try {
        if (proofs.length == 0) {
          throw new Error('no proofs provided.')
        }
        let {fristProofs, scndProofs} = await this.splitApi(proofs, amount)
        // delete proofs from this.proofs
        const usedSecrets = proofs.map(p => p.secret)
        this.proofs = this.proofs.filter(p => !usedSecrets.includes(p.secret))
        // add new fristProofs, scndProofs to this.proofs
        this.proofs = this.proofs.concat(fristProofs).concat(scndProofs)
        this.storeProofs()
        return {fristProofs, scndProofs}
      } catch (error) {
        console.error(error)
        LNbits.utils.notifyApiError(error)
        throw error
      }
    },
    splitApi: async function (proofs, amount) {
      try {
        const total = this.sumProofs(proofs)
        const frst_amount = total - amount
        const scnd_amount = amount
        const frst_amounts = splitAmount(frst_amount)
        const scnd_amounts = splitAmount(scnd_amount)
        const amounts = _.clone(frst_amounts)
        amounts.push(...scnd_amounts)
        let secrets = await this.generateSecrets(amounts)
        if (secrets.length != amounts.length) {
          throw new Error('number of secrets does not match number of outputs.')
        }
        let {blindedMessages, rs} = await this.constructOutputs(
          amounts,
          secrets
        )
        const payload = {
          amount,
          proofs,
          outputs: {
            blinded_messages: blindedMessages
          }
        }

        console.log('payload', JSON.stringify(payload))

        const {data} = await LNbits.api.request(
          'POST',
          `/cashu/api/v1/${this.mintId}/split`,
          '',
          payload
        )
        const frst_rs = rs.slice(0, frst_amounts.length)
        const frst_secrets = secrets.slice(0, frst_amounts.length)
        const scnd_rs = rs.slice(frst_amounts.length)
        const scnd_secrets = secrets.slice(frst_amounts.length)
        const fristProofs = this.constructProofs(
          data.fst,
          frst_secrets,
          frst_rs
        )
        const scndProofs = this.constructProofs(data.snd, scnd_secrets, scnd_rs)

        return {fristProofs, scndProofs}
      } catch (error) {
        console.error(error)
        LNbits.utils.notifyApiError(error)
        throw error
      }
    },

    redeem: async function () {
      this.showReceiveTokens = false
      console.log('### receive tokens', this.receiveData.tokensBase64)
      try {
        if (this.receiveData.tokensBase64.length == 0) {
          throw new Error('no tokens provided.')
        }
        const tokensJson = atob(this.receiveData.tokensBase64)
        const proofs = JSON.parse(tokensJson)
        const amount = proofs.reduce((s, t) => (s += t.amount), 0)
        let {fristProofs, scndProofs} = await this.split(proofs, amount)
        // HACK: we need to do this so the balance updates
        this.proofs = this.proofs.concat([])
        navigator.vibrate(200)
        this.$q.notify({
          timeout: 5000,
          type: 'positive',
          message: 'Tokens received'
        })
      } catch (error) {
        console.error(error)
        LNbits.utils.notifyApiError(error)
        throw error
      }
      // }
    },

    sendTokens: async function () {
      // keep firstProofs, send scndProofs
      let {fristProofs, scndProofs} = await this.splitToSend(
        this.proofs,
        this.sendData.amount,
        true
      )
      this.sendData.tokens = ''
      this.sendData.tokensBase64 = ''
      this.sendData.tokens = scndProofs
      console.log('### this.sendData.tokens', this.sendData.tokens)
      this.sendData.tokensBase64 = btoa(JSON.stringify(this.sendData.tokens))
      navigator.vibrate(200)
    },
    checkFees: async function (payment_request) {
      const payload = {
        pr: payment_request
      }
      console.log('#### payload', JSON.stringify(payload))
      try {
        const {data} = await LNbits.api.request(
          'POST',
          `/cashu/api/v1/${this.mintId}/checkfees`,
          '',
          payload
        )
        console.log('#### checkFees', payment_request, data.fee)
        return data.fee
      } catch (error) {
        console.error(error)
        LNbits.utils.notifyApiError(error)
        throw error
      }
    },
    melt: async function () {
      // todo: get fees from server and add to inputs
      console.log('#### pay lightning')
      const amount_invoice = this.payInvoiceData.invoice.sat
      const amount =
        amount_invoice +
        (await this.checkFees(this.payInvoiceData.data.request))
      console.log(
        '#### amount invoice',
        amount_invoice,
        'amount with fees',
        amount
      )
      // if (amount > balance()) {
      //   LNbits.utils.notifyApiError('Balance too low')
      //   return
      // }
      let {fristProofs, scndProofs} = await this.splitToSend(
        this.proofs,
        amount
      )
      const payload = {
        proofs: scndProofs.flat(),
        amount,
        invoice: this.payInvoiceData.data.request
      }
      console.log('#### payload', JSON.stringify(payload))
      try {
        const {data} = await LNbits.api.request(
          'POST',
          `/cashu/api/v1/${this.mintId}/melt`,
          '',
          payload
        )
        navigator.vibrate(200)
        this.$q.notify({
          timeout: 5000,
          type: 'positive',
          message: 'Invoice paid'
        })
        // delete tokens from db
        this.proofs = fristProofs
        // add new fristProofs, scndProofs to this.proofs
        this.storeProofs()
        console.log({
          amount: -amount,
          bolt11: this.payInvoiceData.data.request,
          hash: this.payInvoiceData.data.hash,
          memo: this.payInvoiceData.data.memo
        })
        this.invoicesCashu.push({
          amount: -amount,
          bolt11: this.payInvoiceData.data.request,
          hash: this.payInvoiceData.data.hash,
          memo: this.payInvoiceData.data.memo,
          date: currentDateStr(),
          status: 'paid'
        })
        this.storeinvoicesCashu()
        this.tab = 'invoices'

        this.payInvoiceData.invoice = false
        this.payInvoiceData.show = false
      } catch (error) {
        console.error(error)
        LNbits.utils.notifyApiError(error)
        throw error
      }
    },

    recheckPendingInvoices: async function () {
      for (const invoice of this.invoicesCashu) {
        if (invoice.status === 'pending' && invoice.sat > 0) {
          this.recheckInvoice(invoice.hash, false)
        }
      }
    },

    fetchMintKeys: async function () {
      const {data} = await LNbits.api.request(
        'GET',
        `/cashu/api/v1/${this.mintId}/keys`
      )
      this.keys = data
      localStorage.setItem(
        this.mintKey(this.mintId, 'keys'),
        JSON.stringify(data)
      )
    },

    ////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
    ////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
    ////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
    ////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////

    findTokenForAmount: function (amount) {
      for (const token of this.proofs) {
        const index = token.promises?.findIndex(p => p.amount === amount)
        if (index >= 0) {
          return {
            promise: token.promises[index],
            secret: token.secrets[index],
            r: token.rs[index]
          }
        }
      }
    },

    checkInvoice: function () {
      console.log('#### checkInvoice')
      try {
        const invoice = decode(this.payInvoiceData.data.request)

        const cleanInvoice = {
          msat: invoice.human_readable_part.amount,
          sat: invoice.human_readable_part.amount / 1000,
          fsat: LNbits.utils.formatSat(
            invoice.human_readable_part.amount / 1000
          )
        }

        _.each(invoice.data.tags, tag => {
          if (_.isObject(tag) && _.has(tag, 'description')) {
            if (tag.description === 'payment_hash') {
              cleanInvoice.hash = tag.value
            } else if (tag.description === 'description') {
              cleanInvoice.description = tag.value
            } else if (tag.description === 'expiry') {
              var expireDate = new Date(
                (invoice.data.time_stamp + tag.value) * 1000
              )
              cleanInvoice.expireDate = Quasar.utils.date.formatDate(
                expireDate,
                'YYYY-MM-DDTHH:mm:ss.SSSZ'
              )
              cleanInvoice.expired = false // TODO
            }
          }

          this.payInvoiceData.invoice = cleanInvoice
        })

        console.log(
          '#### this.payInvoiceData.invoice',
          this.payInvoiceData.invoice
        )
      } catch (error) {
        this.$q.notify({
          timeout: 5000,
          type: 'warning',
          message: 'Could not decode invoice',
          caption: error + ''
        })
        throw error
      }
    },

    storeinvoicesCashu: function () {
      localStorage.setItem(
        this.mintKey(this.mintId, 'invoicesCashu'),
        JSON.stringify(this.invoicesCashu)
      )
    },
    storeProofs: function () {
      localStorage.setItem(
        this.mintKey(this.mintId, 'proofs'),
        JSON.stringify(this.proofs, bigIntStringify)
      )
    },

    mintKey: function (mintId, key) {
      // returns a key for the local storage
      // depending on the current mint
      return 'cashu.' + mintId + '.' + key
    }
  },
  watch: {
    payments: function () {
      this.balance()
    }
  },

  created: function () {
    let params = new URL(document.location).searchParams

    // get mint
    if (params.get('mint_id')) {
      this.mintId = params.get('mint_id')
      this.$q.localStorage.set('cashu.mint', params.get('mint_id'))
    } else if (this.$q.localStorage.getItem('cashu.mint')) {
      this.mintId = this.$q.localStorage.getItem('cashu.mint')
    } else {
      this.$q.notify({
        color: 'red',
        message: 'No mint set!'
      })
    }

    // get name
    if (params.get('mint_name')) {
      this.mintName = params.get('mint_name')
      this.$q.localStorage.set(
        this.mintKey(this.mintId, 'mintName'),
        this.mintName
      )
    } else if (this.$q.localStorage.getItem('cashu.name')) {
      this.mintName = this.$q.localStorage.getItem('cashu.name')
    }

    // get ticker
    if (
      !params.get('tsh') &&
      !this.$q.localStorage.getItem(this.mintKey(this.mintId, 'tickershort'))
    ) {
      this.$q.localStorage.set(this.mintKey(this.mintId, 'tickershort'), 'sats')
      this.tickershort = 'sats'
    } else if (params.get('tsh')) {
      this.$q.localStorage.set(
        this.mintKey(this.mintId, 'tickershort'),
        params.get('tsh')
      )
      this.tickershort = params.get('tsh')
    } else if (
      this.$q.localStorage.getItem(this.mintKey(this.mintId, 'tickershort'))
    ) {
      this.tickershort = this.$q.localStorage.getItem(
        this.mintKey(this.mintId, 'tickershort')
      )
    }

    const keysJson = localStorage.getItem(this.mintKey(this.mintId, 'keys'))
    if (!keysJson) {
      this.fetchMintKeys()
    } else {
      this.keys = JSON.parse(keysJson)
    }

    this.invoicesCashu = JSON.parse(
      localStorage.getItem(this.mintKey(this.mintId, 'invoicesCashu')) || '[]'
    )
    this.proofs = JSON.parse(
      localStorage.getItem(this.mintKey(this.mintId, 'proofs')) || '[]'
    )
    console.log('### invoicesCashu', this.invoicesCashu)
    console.table('### tokens', this.proofs)
    console.log('#### this.mintId', this.mintId)
    console.log('#### this.mintName', this.mintName)

    this.recheckPendingInvoices()
  }
})
