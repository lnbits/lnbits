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
    payments.slice(0).sort(function (a, b) {
      return a.time - b.time
    }),
    function (tx) {
      txs.push({
        hour: Quasar.utils.date.formatDate(tx.date, 'YYYY-MM-DDTHH:00'),
        sat: tx.sat
      })
    }
  )

  _.each(_.groupBy(txs, 'hour'), function (value, day) {
    var income = _.reduce(
      value,
      function (memo, tx) {
        return tx.sat >= 0 ? memo + tx.sat : memo
      },
      0
    )
    var outcome = _.reduce(
      value,
      function (memo, tx) {
        return tx.sat < 0 ? memo + Math.abs(tx.sat) : memo
      },
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
      receive: {
        show: false,
        status: 'pending',
        paymentReq: null,
        data: {
          amount: null,
          memo: ''
        }
      },
      send: {
        show: false,
        invoice: null,
        data: {
          bolt11: ''
        }
      },
      sendCamera: {
        show: false,
        camera: 'auto'
      },
      payments: [],
      paymentsTable: {
        columns: [
          {name: 'memo', align: 'left', label: 'Memo', field: 'memo'},
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
      }
    }
  },
  computed: {
    filteredPayments: function () {
      var q = this.paymentsTable.filter
      if (!q || q == '') return this.payments

      return LNbits.utils.search(this.payments, q)
    },
    balance: function () {
      if (this.payments.length) {
        return (
          _.pluck(this.payments, 'amount').reduce(function (a, b) {
            return a + b
          }, 0) / 1000
        )
      }
      return this.g.wallet.sat
    },
    fbalance: function () {
      return LNbits.utils.formatSat(this.balance)
    },
    canPay: function () {
      if (!this.send.invoice) return false
      return this.send.invoice.sat <= this.balance
    },
    pendingPaymentsExist: function () {
      return this.payments
        ? _.where(this.payments, {pending: 1}).length > 0
        : false
    }
  },
  methods: {
    closeCamera: function () {
      this.sendCamera.show = false
    },
    showCamera: function () {
      this.sendCamera.show = true
    },
    showChart: function () {
      this.paymentsChart.show = true
      this.$nextTick(function () {
        generateChart(this.$refs.canvas, this.payments)
      })
    },
    showReceiveDialog: function () {
      this.receive = {
        show: true,
        status: 'pending',
        paymentReq: null,
        data: {
          amount: null,
          memo: ''
        },
        paymentChecker: null
      }
    },
    showSendDialog: function () {
      this.send = {
        show: true,
        invoice: null,
        data: {
          bolt11: ''
        },
        paymentChecker: null
      }
    },
    closeReceiveDialog: function () {
      var checker = this.receive.paymentChecker
      setTimeout(function () {
        clearInterval(checker)
      }, 10000)
    },
    closeSendDialog: function () {
      this.sendCamera.show = false
      var checker = this.send.paymentChecker
      setTimeout(function () {
        clearInterval(checker)
      }, 1000)
    },
    createInvoice: function () {
      var self = this
      this.receive.status = 'loading'
      LNbits.api
        .createInvoice(
          this.g.wallet,
          this.receive.data.amount,
          this.receive.data.memo
        )
        .then(function (response) {
          self.receive.status = 'success'
          self.receive.paymentReq = response.data.payment_request
          const id = response.data.checking_id
          socket.once(id, data => {
            console.log('ola', data)
            if (data.paid) {
              self.fetchPayments()
              self.receive.show = false
            }
          })
          socket.emit('wait_invoice', { id })

          // self.receive.paymentChecker = setInterval(function () {
          //   LNbits.api
          //     .getPayment(self.g.wallet, response.data.checking_id)
          //     .then(function (response) {
          //       if (response.data.paid) {
          //         self.fetchPayments()
          //         self.receive.show = false
          //         clearInterval(self.receive.paymentChecker)
          //       }
          //     })
          // }, 2000)
        })
        .catch(function (error) {
          LNbits.utils.notifyApiError(error)
          self.receive.status = 'pending'
        })
    },
    decodeQR: function (res) {
      this.send.data.bolt11 = res
      this.decodeInvoice()
      this.sendCamera.show = false
    },
    decodeInvoice: function () {
      if (this.send.data.bolt11.startsWith('lightning:')) {
        this.send.data.bolt11 = this.send.data.bolt11.slice(10)
      }

      let invoice
      try {
        invoice = decode(this.send.data.bolt11)
      } catch (error) {
        this.$q.notify({
          timeout: 3000,
          type: 'warning',
          message: error + '.',
          caption: '400 BAD REQUEST',
          icon: null
        })
        return
      }

      let cleanInvoice = {
        msat: invoice.human_readable_part.amount,
        sat: invoice.human_readable_part.amount / 1000,
        fsat: LNbits.utils.formatSat(invoice.human_readable_part.amount / 1000)
      }

      _.each(invoice.data.tags, function (tag) {
        if (_.isObject(tag) && _.has(tag, 'description')) {
          if (tag.description == 'payment_hash') {
            cleanInvoice.hash = tag.value
          } else if (tag.description == 'description') {
            cleanInvoice.description = tag.value
          } else if (tag.description == 'expiry') {
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

      this.send.invoice = Object.freeze(cleanInvoice)
    },
    payInvoice: function () {
      var self = this

      dismissPaymentMsg = this.$q.notify({
        timeout: 0,
        message: 'Processing payment...',
        icon: null
      })

      LNbits.api
        .payInvoice(this.g.wallet, this.send.data.bolt11)
        .then(function (response) {
          self.send.paymentChecker = setInterval(function () {
            LNbits.api
              .getPayment(self.g.wallet, response.data.checking_id)
              .then(function (res) {
                if (res.data.paid) {
                  self.send.show = false
                  clearInterval(self.send.paymentChecker)
                  dismissPaymentMsg()
                  self.fetchPayments()
                }
              })
          }, 2000)
        })
        .catch(function (error) {
          dismissPaymentMsg()
          LNbits.utils.notifyApiError(error)
        })
    },
    deleteWallet: function (walletId, user) {
      LNbits.utils
        .confirmDialog('Are you sure you want to delete this wallet?')
        .onOk(function () {
          LNbits.href.deleteWallet(walletId, user)
        })
    },
    fetchPayments: function (checkPending) {
      var self = this

      return LNbits.api
        .getPayments(this.g.wallet, checkPending)
        .then(function (response) {
          self.payments = response.data
            .map(function (obj) {
              return LNbits.map.payment(obj)
            })
            .sort(function (a, b) {
              return b.time - a.time
            })
        })
    },
    checkPendingPayments: function () {
      var dismissMsg = this.$q.notify({
        timeout: 0,
        message: 'Checking pending transactions...',
        icon: null
      })

      this.fetchPayments(true).then(function () {
        dismissMsg()
      })
    },
    exportCSV: function () {
      LNbits.utils.exportCSV(this.paymentsTable.columns, this.payments)
    }
  },
  watch: {
    payments: function () {
      EventHub.$emit('update-wallet-balance', [this.g.wallet.id, this.balance])
    }
  },
  created: function () {
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
