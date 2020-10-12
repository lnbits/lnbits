/* globals windowMixin, decode, Vue, VueQrcodeReader, VueQrcode, Quasar, LNbits, _, EventHub, Chart */

Vue.component(VueQrcode.name, VueQrcode)
Vue.use(VueQrcodeReader)

function generateChart(canvas, payments) {
  var txs = []
  var n = 0
  var data = {
    labels: [],
    income: [],
    outcome: [],
    cumulative: []
  }

  _.each(
    payments.filter(p => !p.pending).sort((a, b) => a.time - b.time),
    tx => {
      txs.push({
        hour: Quasar.utils.date.formatDate(tx.date, 'YYYY-MM-DDTHH:00'),
        sat: tx.sat
      })
    }
  )

  _.each(_.groupBy(txs, 'hour'), (value, day) => {
    var income = _.reduce(
      value,
      (memo, tx) => (tx.sat >= 0 ? memo + tx.sat : memo),
      0
    )
    var outcome = _.reduce(
      value,
      (memo, tx) => (tx.sat < 0 ? memo + Math.abs(tx.sat) : memo),
      0
    )
    n = n + income - outcome
    data.labels.push(day)
    data.income.push(income)
    data.outcome.push(outcome)
    data.cumulative.push(n)
  })

  new Chart(canvas.getContext('2d'), {
    type: 'bar',
    data: {
      labels: data.labels,
      datasets: [
        {
          data: data.cumulative,
          type: 'line',
          label: 'balance',
          backgroundColor: '#673ab7', // deep-purple
          borderColor: '#673ab7',
          borderWidth: 4,
          pointRadius: 3,
          fill: false
        },
        {
          data: data.income,
          type: 'bar',
          label: 'in',
          barPercentage: 0.75,
          backgroundColor: window.Color('rgb(76,175,80)').alpha(0.5).rgbString() // green
        },
        {
          data: data.outcome,
          type: 'bar',
          label: 'out',
          barPercentage: 0.75,
          backgroundColor: window.Color('rgb(233,30,99)').alpha(0.5).rgbString() // pink
        }
      ]
    },
    options: {
      title: {
        text: 'Chart.js Combo Time Scale'
      },
      tooltips: {
        mode: 'index',
        intersect: false
      },
      scales: {
        xAxes: [
          {
            type: 'time',
            display: true,
            offset: true,
            time: {
              minUnit: 'hour',
              stepSize: 3
            }
          }
        ]
      },
      // performance tweaks
      animation: {
        duration: 0
      },
      elements: {
        line: {
          tension: 0
        }
      }
    }
  })
}

new Vue({
  el: '#vue',
  mixins: [windowMixin],
  data: function () {
    return {
      user: LNbits.map.user(window.user),
      receive: {
        show: false,
        status: 'pending',
        paymentReq: null,
        minMax: [0, 2100000000000000],
        lnurl: null,
        data: {
          amount: null,
          memo: ''
        }
      },
      parse: {
        show: false,
        invoice: null,
        lnurlpay: null,
        data: {
          request: '',
          amount: 0
        },
        paymentChecker: null,
        camera: {
          show: false,
          camera: 'auto'
        }
      },
      payments: [],
      paymentsTable: {
        columns: [
          {
            name: 'memo',
            align: 'left',
            label: 'Memo',
            field: 'memo'
          },
          {
            name: 'date',
            align: 'left',
            label: 'Date',
            field: 'date',
            sortable: true
          },
          {
            name: 'sat',
            align: 'right',
            label: 'Amount (sat)',
            field: 'sat',
            sortable: true
          },
          {
            name: 'fee',
            align: 'right',
            label: 'Fee (msat)',
            field: 'fee'
          }
        ],
        pagination: {
          rowsPerPage: 10
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
      balance: 0
    }
  },
  computed: {
    formattedBalance: function () {
      return LNbits.utils.formatSat(this.balance || this.g.wallet.sat)
    },
    filteredPayments: function () {
      var q = this.paymentsTable.filter
      if (!q || q === '') return this.payments

      return LNbits.utils.search(this.payments, q)
    },
    canPay: function () {
      if (!this.parse.invoice) return false
      return this.parse.invoice.sat <= this.balance
    },
    pendingPaymentsExist: function () {
      return this.payments
        ? _.where(this.payments, {pending: 1}).length > 0
        : false
    }
  },
  filters: {
    msatoshiFormat: function (value) {
      return LNbits.utils.formatSat(value / 1000)
    }
  },
  methods: {
    closeCamera: function () {
      this.parse.camera.show = false
    },
    showCamera: function () {
      this.parse.camera.show = true
    },
    showChart: function () {
      this.paymentsChart.show = true
      this.$nextTick(() => {
        generateChart(this.$refs.canvas, this.payments)
      })
    },
    showReceiveDialog: function () {
      this.receive.show = true
      this.receive.status = 'pending'
      this.receive.paymentReq = null
      this.receive.data.amount = null
      this.receive.data.memo = null
      this.receive.paymentChecker = null
      this.receive.minMax = [0, 2100000000000000]
      this.receive.lnurl = null
    },
    showParseDialog: function () {
      this.parse.show = true
      this.parse.invoice = null
      this.parse.lnurlpay = null
      this.parse.data.request = ''
      this.parse.data.paymentChecker = null
      this.parse.camera.show = false
    },
    closeReceiveDialog: function () {
      var checker = this.receive.paymentChecker
      setTimeout(() => {
        clearInterval(checker)
      }, 10000)
    },
    closeParseDialog: function () {
      var checker = this.parse.paymentChecker
      setTimeout(() => {
        clearInterval(checker)
      }, 1000)
    },
    createInvoice: function () {
      this.receive.status = 'loading'
      LNbits.api
        .createInvoice(
          this.g.wallet,
          this.receive.data.amount,
          this.receive.data.memo
        )
        .then(response => {
          this.receive.status = 'success'
          this.receive.paymentReq = response.data.payment_request

          if (this.receive.lnurl) {
            // send invoice to lnurl callback
            console.log('sending', this.receive.lnurl)
            LNbits.api.sendInvoiceToLnurlWithdraw(this.receive.paymentReq)
          }

          this.receive.paymentChecker = setInterval(() => {
            LNbits.api
              .getPayment(this.g.wallet, response.data.payment_hash)
              .then(response => {
                if (response.data.paid) {
                  this.fetchPayments()
                  this.receive.show = false
                  clearInterval(this.receive.paymentChecker)
                }
              })
          }, 2000)
        })
        .catch(err => {
          LNbits.utils.notifyApiError(err)
          this.receive.status = 'pending'
        })
    },
    decodeQR: function (res) {
      this.parse.data.request = res
      this.decodeRequest()
      this.parse.camera.show = false
    },
    decodeRequest: function () {
      this.parse.show = true

      if (this.parse.data.request.startsWith('lightning:')) {
        this.parse.data.request = this.parse.data.request.slice(10)
      }
      if (this.parse.data.request.startsWith('lnurl:')) {
        this.parse.data.request = this.parse.data.request.slice(6)
      }

      if (this.parse.data.request.toLowerCase().startsWith('lnurl1')) {
        LNbits.api
          .request(
            'GET',
            '/api/v1/lnurlscan/' + this.parse.data.request,
            this.g.user.wallets[0].adminkey
          )
          .catch(err => {
            LNbits.utils.notifyApiError(err)
          })
          .then(response => {
            let data = response.data

            if (data.status === 'ERROR') {
              Quasar.plugins.Notify.create({
                timeout: 5000,
                type: 'warning',
                message: data.reason,
                caption: `${data.domain} returned an error to the lnurl call.`,
                icon: null
              })
              return
            }

            if (data.kind === 'pay') {
              this.parse.lnurlpay = Object.freeze(data)
              this.parse.data.amount = data.minSendable / 1000
            } else if (data.kind === 'withdraw') {
              this.parse.show = false
              this.receive.show = true
              this.receive.status = 'pending'
              this.receive.data.amount = data.maxWithdrawable
              this.receive.data.memo = data.defaultDescription
              this.receive.minMax = [data.minWithdrawable, data.maxWithdrawable]
              this.receive.lnurl = {
                domain: data.domain,
                callback: data.callback,
                k1: data.k1,
                fixed: data.fixed
              }
            }
          })
        return
      }

      let invoice
      try {
        invoice = decode(this.parse.data.bolt11)
      } catch (error) {
        this.$q.notify({
          timeout: 3000,
          type: 'warning',
          message: error + '.',
          caption: '400 BAD REQUEST',
          icon: null
        })
        this.parse.show = false
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

      this.parse.invoice = Object.freeze(cleanInvoice)
    },
    payInvoice: function () {
      let dismissPaymentMsg = this.$q.notify({
        timeout: 0,
        message: 'Processing payment...',
        icon: null
      })

      LNbits.api
        .payInvoice(this.g.wallet, this.parse.data.bolt11)
        .then(response => {
          this.parse.paymentChecker = setInterval(() => {
            LNbits.api
              .getPayment(this.g.wallet, response.data.payment_hash)
              .then(res => {
                if (res.data.paid) {
                  this.parse.show = false
                  clearInterval(this.parse.paymentChecker)
                  dismissPaymentMsg()
                  this.fetchPayments()
                }
              })
          }, 2000)
        })
        .catch(err => {
          dismissPaymentMsg()
          LNbits.utils.notifyApiError(err)
        })
    },
    payLnurl: function () {
      let dismissPaymentMsg = this.$q.notify({
        timeout: 0,
        message: 'Processing payment...',
        icon: null
      })

      LNbits.api
        .payInvoice(this.g.wallet, this.parse.data.bolt11)
        .then(response => {
          this.parse.paymentChecker = setInterval(() => {
            LNbits.api
              .getPayment(this.g.wallet, response.data.payment_hash)
              .then(res => {
                if (res.data.paid) {
                  this.parse.show = false
                  clearInterval(this.parse.paymentChecker)
                  dismissPaymentMsg()
                  this.fetchPayments()
                }
              })
          }, 2000)
        })
        .catch(err => {
          dismissPaymentMsg()
          LNbits.utils.notifyApiError(err)
        })
    },
    deleteWallet: function (walletId, user) {
      LNbits.utils
        .confirmDialog('Are you sure you want to delete this wallet?')
        .onOk(() => {
          LNbits.href.deleteWallet(walletId, user)
        })
    },
    fetchPayments: function (checkPending) {
      return LNbits.api
        .getPayments(this.g.wallet, checkPending)
        .then(response => {
          this.payments = response.data
            .map(obj => {
              return LNbits.map.payment(obj)
            })
            .sort((a, b) => {
              return b.time - a.time
            })
        })
    },
    fetchBalance: function () {
      LNbits.api.getWallet(this.g.wallet).then(response => {
        this.balance = Math.round(response.data.balance / 1000)
        EventHub.$emit('update-wallet-balance', [
          this.g.wallet.id,
          this.balance
        ])
      })
    },
    checkPendingPayments: function () {
      var dismissMsg = this.$q.notify({
        timeout: 0,
        message: 'Checking pending transactions...',
        icon: null
      })

      this.fetchPayments(true).then(() => {
        dismissMsg()
      })
    },
    exportCSV: function () {
      LNbits.utils.exportCSV(this.paymentsTable.columns, this.payments)
    }
  },
  watch: {
    payments: function () {
      this.fetchBalance()
    }
  },
  created: function () {
    this.fetchBalance()
    this.fetchPayments()
    setTimeout(this.checkPendingPayments(), 1200)
  },
  mounted: function () {
    if (
      this.$refs.disclaimer &&
      !this.$q.localStorage.getItem('lnbits.disclaimerShown')
    ) {
      this.disclaimerDialog.show = true
      this.$q.localStorage.set('lnbits.disclaimerShown', true)
    }
  }
})
