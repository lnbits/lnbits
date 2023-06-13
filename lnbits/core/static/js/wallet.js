/* globals windowMixin, decode, Vue, VueQrcodeReader, VueQrcode, Quasar, LNbits, _, EventHub, Chart, decryptLnurlPayAES */

Vue.component(VueQrcode.name, VueQrcode)
Vue.use(VueQrcodeReader)

function generateChart(canvas, rawData) {
  const data = rawData.reduce(
    (previous, current) => {
      previous.labels.push(current.date)
      previous.income.push(current.income)
      previous.spending.push(current.spending)
      previous.cumulative.push(current.balance)
      return previous
    },
    {
      labels: [],
      income: [],
      spending: [],
      cumulative: []
    }
  )

  return new Chart(canvas.getContext('2d'), {
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
          data: data.spending,
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
            //offset: true,
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
      paymentsTable: {
        columns: [
          {
            name: 'time',
            align: 'left',
            label: this.$t('memo') + '/' + this.$t('date'),
            field: 'date',
            sortable: true
          },
          {
            name: 'amount',
            align: 'right',
            label: this.$t('amount') + ' (' + LNBITS_DENOMINATION + ')',
            field: 'sat',
            sortable: true
          }
        ],
        pagination: {
          rowsPerPage: 10,
          page: 1,
          sortBy: 'time',
          descending: true,
          rowsNumber: 10
        },
        filter: null,
        loading: false
      },
      paymentsCSV: {
        columns: [
          {
            name: 'memo',
            align: 'left',
            label: this.$t('memo'),
            field: 'memo'
          },
          {
            name: 'time',
            align: 'left',
            label: this.$t('date'),
            field: 'date',
            sortable: true
          },
          {
            name: 'amount',
            align: 'right',
            label: this.$t('amount') + ' (' + LNBITS_DENOMINATION + ')',
            field: 'sat',
            sortable: true
          },
          {
            name: 'fee',
            align: 'right',
            label: this.$t('fee') + ' (m' + LNBITS_DENOMINATION + ')',
            field: 'fee'
          },
          {
            name: 'tag',
            align: 'right',
            label: this.$t('tag'),
            field: 'tag'
          },
          {
            name: 'payment_hash',
            align: 'right',
            label: this.$t('payment_hash'),
            field: 'payment_hash'
          },
          {
            name: 'payment_proof',
            align: 'right',
            label: this.$t('payment_proof'),
            field: 'payment_proof'
          },
          {
            name: 'webhook',
            align: 'right',
            label: this.$t('webhook'),
            field: 'webhook'
          }
        ],
        filter: null,
        loading: false
      },
      paymentsChart: {
        show: false,
        group: {value: 'hour', label: 'Hour'},
        groupOptions: [
          {value: 'day', label: 'Day'},
          {value: 'hour', label: 'Hour'}
        ],
        instance: null
      },
      disclaimerDialog: {
        show: false,
        location: window.location
      },
      balance: 0,
      credit: 0,
      newName: ''
    }
  },
  computed: {
    formattedBalance: function () {
      if (LNBITS_DENOMINATION != 'sats') {
        return this.balance / 100
      } else {
        return LNbits.utils.formatSat(this.balance || this.g.wallet.sat)
      }
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
      return this.payments.findIndex(payment => payment.pending) !== -1
    }
  },
  filters: {
    msatoshiFormat: function (value) {
      return LNbits.utils.formatSat(value / 1000)
    }
  },
  methods: {
    paymentTableRowKey: function (row) {
      return row.payment_hash + row.amount
    },
    closeCamera: function () {
      this.parse.camera.show = false
    },
    showCamera: function () {
      this.parse.camera.show = true
    },
    showChart: function () {
      this.paymentsChart.show = true
      LNbits.api
        .request(
          'GET',
          '/api/v1/payments/history?group=' + this.paymentsChart.group.value,
          this.g.wallet.adminkey
        )
        .then(response => {
          this.$nextTick(() => {
            if (this.paymentsChart.instance) {
              this.paymentsChart.instance.destroy()
            }
            this.paymentsChart.instance = generateChart(
              this.$refs.canvas,
              response.data
            )
          })
        })
        .catch(err => {
          LNbits.utils.notifyApiError(err)
          this.paymentsChart.show = false
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
      this.parse.show = true
      this.parse.invoice = null
      this.parse.lnurlpay = null
      this.parse.lnurlauth = null
      this.parse.data.request = ''
      this.parse.data.comment = ''
      this.parse.data.paymentChecker = null
      this.parse.camera.show = false
    },
    updateBalance: function (credit) {
      LNbits.api
        .request(
          'PUT',
          '/admin/api/v1/topup/?usr=' + this.g.user.id,
          this.g.user.wallets[0].adminkey,
          {
            amount: credit,
            id: this.g.wallet.id
          }
        )
        .then(response => {
          this.$q.notify({
            type: 'positive',
            message:
              'Success! Added ' +
              credit +
              ' sats to ' +
              this.g.user.wallets[0].id,
            icon: null
          })
          this.balance += parseInt(credit)
        })
        .catch(function (error) {
          LNbits.utils.notifyApiError(error)
        })
    },
    closeReceiveDialog: function () {
      setTimeout(() => {
        clearInterval(this.receive.paymentChecker)
      }, 10000)
    },
    closeParseDialog: function () {
      setTimeout(() => {
        clearInterval(this.parse.paymentChecker)
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
          this.g.wallet,
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
          this.receive.paymentChecker = setInterval(() => {
            let hash = response.data.payment_hash

            LNbits.api.getPayment(this.g.wallet, hash).then(response => {
              if (response.data.paid) {
                this.onPaymentReceived(hash)
              }
            })
          }, 5000)
        })
        .catch(err => {
          LNbits.utils.notifyApiError(err)
          this.receive.status = 'pending'
        })
    },
    onInitQR: async function (promise) {
      try {
        await promise
      } catch (error) {
        let mapping = {
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
        let valid_error = Object.keys(mapping).filter(key => {
          return error.name === key
        })
        let camera_error = valid_error
          ? mapping[valid_error]
          : `ERROR: Camera error (${error.name})`
        this.parse.camera.show = false
        this.$q.notify({
          message: camera_error,
          type: 'negative'
        })
      }
    },
    decodeQR: function (res) {
      this.parse.data.request = res
      this.decodeRequest()
      this.parse.camera.show = false
    },
    decodeRequest: function () {
      this.parse.show = true
      let req = this.parse.data.request.toLowerCase()
      if (this.parse.data.request.toLowerCase().startsWith('lightning:')) {
        this.parse.data.request = this.parse.data.request.slice(10)
      } else if (this.parse.data.request.toLowerCase().startsWith('lnurl:')) {
        this.parse.data.request = this.parse.data.request.slice(6)
      } else if (req.indexOf('lightning=lnurl1') !== -1) {
        this.parse.data.request = this.parse.data.request
          .split('lightning=')[1]
          .split('&')[0]
      }

      if (
        this.parse.data.request.toLowerCase().startsWith('lnurl1') ||
        this.parse.data.request.match(/[\w.+-~_]+@[\w.+-~_]/)
      ) {
        LNbits.api
          .request(
            'GET',
            '/api/v1/lnurlscan/' + this.parse.data.request,
            this.g.wallet.adminkey
          )
          .catch(err => {
            LNbits.utils.notifyApiError(err)
          })
          .then(response => {
            let data = response.data

            if (data.status === 'ERROR') {
              this.$q.notify({
                timeout: 5000,
                type: 'warning',
                message: `${data.domain} lnurl call failed.`,
                caption: data.reason
              })
              return
            }

            if (data.kind === 'pay') {
              this.parse.lnurlpay = Object.freeze(data)
              this.parse.data.amount = data.minSendable / 1000
            } else if (data.kind === 'auth') {
              this.parse.lnurlauth = Object.freeze(data)
            } else if (data.kind === 'withdraw') {
              this.parse.show = false
              this.receive.show = true
              this.receive.status = 'pending'
              this.receive.paymentReq = null
              this.receive.paymentHash = null
              this.receive.data.amount = data.maxWithdrawable / 1000
              this.receive.data.memo = data.defaultDescription
              this.receive.minMax = [
                data.minWithdrawable / 1000,
                data.maxWithdrawable / 1000
              ]
              this.receive.lnurl = {
                domain: data.domain,
                callback: data.callback,
                fixed: data.fixed
              }
            }
          })
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
        this.$q.notify({
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
        message: this.$t('processing_payment')
      })

      LNbits.api
        .payInvoice(this.g.wallet, this.parse.data.request)
        .then(response => {
          clearInterval(this.parse.paymentChecker)
          setTimeout(() => {
            clearInterval(this.parse.paymentChecker)
          }, 40000)
          this.parse.paymentChecker = setInterval(() => {
            LNbits.api
              .getPayment(this.g.wallet, response.data.payment_hash)
              .then(res => {
                if (res.data.paid) {
                  this.parse.show = false
                  clearInterval(this.parse.paymentChecker)
                  dismissPaymentMsg()
                  this.fetchPayments()
                  this.fetchBalance()
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
        message: 'Processing payment...'
      })

      LNbits.api
        .payLnurl(
          this.g.wallet,
          this.parse.lnurlpay.callback,
          this.parse.lnurlpay.description_hash,
          this.parse.data.amount * 1000,
          this.parse.lnurlpay.description.slice(0, 120),
          this.parse.data.comment
        )
        .then(response => {
          this.parse.show = false

          clearInterval(this.parse.paymentChecker)
          setTimeout(() => {
            clearInterval(this.parse.paymentChecker)
          }, 40000)
          this.parse.paymentChecker = setInterval(() => {
            LNbits.api
              .getPayment(this.g.wallet, response.data.payment_hash)
              .then(res => {
                if (res.data.paid) {
                  dismissPaymentMsg()
                  clearInterval(this.parse.paymentChecker)
                  this.fetchPayments()
                  this.fetchBalance()

                  // show lnurlpay success action
                  if (response.data.success_action) {
                    switch (response.data.success_action.tag) {
                      case 'url':
                        this.$q.notify({
                          message: `<a target='_blank' style='color: inherit' href='${response.data.success_action.url}'>${response.data.success_action.url}</a>`,
                          caption: response.data.success_action.description,
                          html: true,
                          type: 'positive',
                          timeout: 0,
                          closeBtn: true
                        })
                        break
                      case 'message':
                        this.$q.notify({
                          message: response.data.success_action.message,
                          type: 'positive',
                          timeout: 0,
                          closeBtn: true
                        })
                        break
                      case 'aes':
                        LNbits.api
                          .getPayment(this.g.wallet, response.data.payment_hash)
                          .then(({data: payment}) =>
                            decryptLnurlPayAES(
                              response.data.success_action,
                              payment.preimage
                            )
                          )
                          .then(value => {
                            this.$q.notify({
                              message: value,
                              caption: response.data.success_action.description,
                              html: true,
                              type: 'positive',
                              timeout: 0,
                              closeBtn: true
                            })
                          })
                        break
                    }
                  }
                }
              })
          }, 2000)
        })
        .catch(err => {
          dismissPaymentMsg()
          LNbits.utils.notifyApiError(err)
        })
    },
    authLnurl: function () {
      let dismissAuthMsg = this.$q.notify({
        timeout: 10,
        message: 'Performing authentication...'
      })

      LNbits.api
        .authLnurl(this.g.wallet, this.parse.lnurlauth.callback)
        .then(response => {
          dismissAuthMsg()
          this.$q.notify({
            message: `Authentication successful.`,
            type: 'positive',
            timeout: 3500
          })
          this.parse.show = false
        })
        .catch(err => {
          dismissAuthMsg()
          if (err.response.data.reason) {
            this.$q.notify({
              message: `Authentication failed. ${this.parse.lnurlauth.domain} says:`,
              caption: err.response.data.reason,
              type: 'warning',
              timeout: 5000
            })
          } else {
            LNbits.utils.notifyApiError(err)
          }
        })
    },
    updateWalletName: function () {
      let newName = this.newName
      let adminkey = this.g.wallet.adminkey
      if (!newName || !newName.length) return
      LNbits.api
        .request('PUT', '/api/v1/wallet/' + newName, adminkey, {})
        .then(res => {
          this.newName = ''
          this.$q.notify({
            message: `Wallet named updated.`,
            type: 'positive',
            timeout: 3500
          })
          LNbits.href.updateWallet(
            res.data.name,
            this.user.id,
            this.g.wallet.id
          )
        })
        .catch(err => {
          this.newName = ''
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
    fetchPayments: function (props) {
      // Props are passed by qasar when pagination or sorting changes
      if (props) {
        this.paymentsTable.pagination = props.pagination
      }
      let pagination = this.paymentsTable.pagination
      this.paymentsTable.loading = true
      const query = {
        limit: pagination.rowsPerPage,
        offset: (pagination.page - 1) * pagination.rowsPerPage,
        sortby: pagination.sortBy ?? 'time',
        direction: pagination.descending ? 'desc' : 'asc'
      }
      if (this.paymentsTable.filter) {
        query.search = this.paymentsTable.filter
      }
      return LNbits.api
        .getPayments(this.g.wallet, query)
        .then(response => {
          this.paymentsTable.loading = false
          this.paymentsTable.pagination.rowsNumber = response.data.total
          this.payments = response.data.data.map(obj => {
            return LNbits.map.payment(obj)
          })
        })
        .catch(err => {
          this.paymentsTable.loading = false
          LNbits.utils.notifyApiError(err)
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
    exportCSV: function () {
      // a bit of a hack to make the browser download the file
      window.location.href =
        '/api/v1/payments.csv?api-key=' + this.g.wallet.adminkey
    }
  },
  watch: {
    payments: function () {
      this.fetchBalance()
    },
    'paymentsChart.group': function () {
      this.showChart()
    }
  },
  created: function () {
    this.fetchBalance()
    this.fetchPayments()

    LNbits.api
      .request('GET', '/api/v1/currencies')
      .then(response => {
        this.receive.units = ['sat', ...response.data]
      })
      .catch(err => {
        LNbits.utils.notifyApiError(err)
      })
  },
  mounted: function () {
    // show disclaimer
    if (!this.$q.localStorage.getItem('lnbits.disclaimerShown')) {
      this.disclaimerDialog.show = true
      this.$q.localStorage.set('lnbits.disclaimerShown', true)
    }

    // listen to incoming payments
    LNbits.events.onInvoicePaid(this.g.wallet, payment =>
      this.onPaymentReceived(payment.payment_hash)
    )
  }
})

if (navigator.serviceWorker != null) {
  navigator.serviceWorker
    .register('/service-worker.js')
    .then(function (registration) {
      console.log('Registered events at scope: ', registration.scope)
    })
}
