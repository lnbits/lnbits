window.app.component('lnbits-payment-list', {
  template: '#lnbits-payment-list',
  props: ['wallet', 'paymentFilter'],
  mixins: [window.windowMixin],
  data() {
    return {
      denomination: LNBITS_DENOMINATION,
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
        search: '',
        loading: false
      },
      searchDate: {from: null, to: null},
      searchStatus: {
        success: true,
        pending: true,
        failed: false,
        incoming: true,
        outgoing: true
      },
      exportTagName: '',
      exportPaymentTagList: [],
      paymentsCSV: {
        columns: [
          {
            name: 'pending',
            align: 'left',
            label: 'Pending',
            field: 'pending'
          },
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
          },
          {
            name: 'fiat_currency',
            align: 'right',
            label: 'Fiat Currency',
            field: row => row.extra.wallet_fiat_currency
          },
          {
            name: 'fiat_amount',
            align: 'right',
            label: 'Fiat Amount',
            field: row => row.extra.wallet_fiat_amount
          }
        ],
        preimage: null,
        loading: false
      },
      hodlInvoice: {
        show: false,
        payment: null,
        preimage: null
      },
      selectedPayment: null,
      filterLabels: []
    }
  },
  computed: {
    currentWallet() {
      return this.wallet || this.g.wallet
    },
    filteredPayments() {
      const q = this.paymentsTable.search
      if (!q || q === '') return this.payments

      return LNbits.utils.search(this.payments, q)
    },
    paymentsOmitter() {
      if (this.$q.screen.lt.md && this.g.mobileSimple) {
        return this.payments.length > 0 ? [this.payments[0]] : []
      }
      return this.payments
    },
    pendingPaymentsExist() {
      return this.payments.findIndex(payment => payment.pending) !== -1
    }
  },
  methods: {
    searchByDate() {
      if (typeof this.searchDate === 'string') {
        this.searchDate = {
          from: this.searchDate,
          to: this.searchDate
        }
      }
      if (this.searchDate.from) {
        this.paymentFilter['time[ge]'] = this.searchDate.from + 'T00:00:00'
      }
      if (this.searchDate.to) {
        this.paymentFilter['time[le]'] = this.searchDate.to + 'T23:59:59'
      }

      this.fetchPayments()
    },
    searchByLabels(labels) {
      if (!labels || labels.length === 0) {
        this.clearLabelSeach()
        return
      }
      this.filterLabels = labels
      this.paymentsTable.filter['labels[every]'] = labels
      this.fetchPayments()
    },
    clearDateSeach() {
      this.searchDate = {from: null, to: null}
      delete this.paymentFilter['time[ge]']
      delete this.paymentFilter['time[le]']
      this.fetchPayments()
    },
    clearLabelSeach() {
      this.filterLabels = []
      delete this.paymentsTable.filter['labels[every]']
      this.fetchPayments()
    },
    fetchPayments(props) {
      const params = LNbits.utils.prepareFilterQuery(
        this.paymentsTable,
        props,
        this.paymentFilter
      )
      this.paymentsTable.loading = true
      return LNbits.api
        .getPayments(this.currentWallet, params)
        .then(response => {
          this.paymentsTable.loading = false
          this.paymentsTable.pagination.rowsNumber = response.data.total
          this.payments = response.data.data.map(obj => {
            return LNbits.map.payment(obj)
          })
          this.recheckPendingPayments()
        })
        .catch(err => {
          this.paymentsTable.loading = false
          if (g.user.admin) {
            this.fetchPaymentsAsAdmin(this.currentWallet.id, params)
          } else {
            LNbits.utils.notifyApiError(err)
          }
        })
    },
    fetchPaymentsAsAdmin(walletId, params) {
      params = (params || '') + '&wallet_id=' + walletId
      return LNbits.api
        .request('GET', '/api/v1/payments/all/paginated?' + params)
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
    checkPayment(payment_hash) {
      LNbits.api
        .getPayment(this.g.wallet, payment_hash)
        .then(res => {
          this.update = !this.update
          if (res.data.status == 'success') {
            Quasar.Notify.create({
              type: 'positive',
              message: this.$t('payment_successful')
            })
          }
          if (res.data.status == 'pending') {
            Quasar.Notify.create({
              type: 'info',
              message: this.$t('payment_pending')
            })
          }
        })
        .catch(LNbits.utils.notifyApiError)
    },
    recheckPendingPayments() {
      const pendingPayments = this.payments.filter(p => p.status === 'pending')
      if (pendingPayments.length === 0) return

      const params = [
        'recheck_pending=true',
        'checking_id[in]=' + pendingPayments.map(p => p.checking_id).join(',')
      ].join('&')

      LNbits.api
        .getPayments(this.currentWallet, params)
        .then(response => {
          let updatedPayments = 0
          response.data.data.forEach(updatedPayment => {
            if (updatedPayment.status !== 'pending') {
              const index = this.payments.findIndex(
                p => p.checking_id === updatedPayment.checking_id
              )
              if (index !== -1) {
                this.payments.splice(
                  index,
                  1,
                  LNbits.map.payment(updatedPayment)
                )
                updatedPayments += 1
              }
            }
          })
          if (updatedPayments > 0) {
            Quasar.Notify.create({
              type: 'positive',
              message: this.$t('payment_successful')
            })
          }
        })
        .catch(err => {
          console.warn(err)
        })
    },
    showHoldInvoiceDialog(payment) {
      this.hodlInvoice.show = true
      this.hodlInvoice.preimage = ''
      this.hodlInvoice.payment = payment
    },
    cancelHoldInvoice(payment_hash) {
      LNbits.api
        .cancelInvoice(this.g.wallet, payment_hash)
        .then(() => {
          this.update = !this.update
          Quasar.Notify.create({
            type: 'positive',
            message: this.$t('invoice_cancelled')
          })
        })
        .catch(LNbits.utils.notifyApiError)
    },
    settleHoldInvoice(preimage) {
      LNbits.api
        .settleInvoice(this.g.wallet, preimage)
        .then(() => {
          this.update = !this.update
          Quasar.Notify.create({
            type: 'positive',
            message: this.$t('invoice_settled')
          })
        })
        .catch(LNbits.utils.notifyApiError)
    },
    paymentTableRowKey(row) {
      return row.payment_hash + row.amount
    },
    exportCSV(detailed = false) {
      // status is important for export but it is not in paymentsTable
      // because it is manually added with payment detail link and icons
      // and would cause duplication in the list
      const pagination = this.paymentsTable.pagination
      const query = {
        sortby: pagination.sortBy ?? 'time',
        direction: pagination.descending ? 'desc' : 'asc'
      }
      const params = new URLSearchParams(query)
      LNbits.api.getPayments(this.g.wallet, params).then(response => {
        let payments = response.data.data.map(LNbits.map.payment)
        let columns = this.paymentsCSV.columns

        if (detailed) {
          if (this.exportPaymentTagList.length) {
            payments = payments.filter(p =>
              this.exportPaymentTagList.includes(p.tag)
            )
          }
          const extraColumns = Object.keys(
            payments.reduce((e, p) => ({...e, ...p.details}), {})
          ).map(col => ({
            name: col,
            align: 'right',
            label:
              col.charAt(0).toUpperCase() +
              col.slice(1).replace(/([A-Z])/g, ' $1'),
            field: row => row.details[col],
            format: data =>
              typeof data === 'object' ? JSON.stringify(data) : data
          }))
          columns = this.paymentsCSV.columns.concat(extraColumns)
        }

        LNbits.utils.exportCSV(
          columns,
          payments,
          this.g.wallet.name + '-payments'
        )
      })
    },
    addFilterTag() {
      if (!this.exportTagName) return
      const value = this.exportTagName.trim()
      this.exportPaymentTagList = this.exportPaymentTagList.filter(
        v => v !== value
      )
      this.exportPaymentTagList.push(value)
      this.exportTagName = ''
    },
    removeExportTag(value) {
      this.exportPaymentTagList = this.exportPaymentTagList.filter(
        v => v !== value
      )
    },
    formatCurrency(amount, currency) {
      try {
        return LNbits.utils.formatCurrency(amount, currency)
      } catch (e) {
        console.error(e)
        return `${amount} ???`
      }
    },
    handleFilterChanged() {
      const {success, pending, failed, incoming, outgoing} = this.searchStatus
      let paymentFilter = this.paymentFilter || {}
      delete paymentFilter['status[ne]']
      delete paymentFilter['status[eq]']
      if (success && pending && failed) {
        // No status filter
      } else if (success && pending) {
        paymentFilter['status[ne]'] = 'failed'
      } else if (success && failed) {
        paymentFilter['status[ne]'] = 'pending'
      } else if (failed && pending) {
        paymentFilter['status[ne]'] = 'success'
      } else if (success && !pending && !failed) {
        paymentFilter['status[eq]'] = 'success'
      } else if (pending && !success && !failed) {
        paymentFilter['status[eq]'] = 'pending'
      } else if (failed && !success && !pending) {
        paymentFilter['status[eq]'] = 'failed'
      }
      delete paymentFilter['amount[ge]']
      delete paymentFilter['amount[le]']
      if ((incoming && outgoing) || (!incoming && !outgoing)) {
        // do nothing
      } else if (incoming && !outgoing) {
        paymentFilter['amount[ge]'] = 0
      } else if (outgoing && !incoming) {
        paymentFilter['amount[le]'] = 0
      }
      this.paymentFilter = paymentFilter
    },
    async savePaymentLabels(labels) {
      if (!this.selectedPayment) {
        Quasar.Notify.create({
          type: 'warning',
          message: 'No payment selected'
        })
        return
      }
      try {
        await LNbits.api.request(
          'PUT',
          `/api/v1/payments/${this.selectedPayment.payment_hash}/labels`,
          this.g.wallet.adminkey,
          {
            labels: labels
          }
        )

        const payment = this.payments.find(
          p => p.checking_id === this.selectedPayment.checking_id
        )
        if (payment) {
          payment.labels = [...labels]
        }

        Quasar.Notify.create({
          type: 'positive',
          message: this.$t('payment_labels_updated')
        })
      } catch (error) {
        LNbits.utils.notifyApiError(error)
      }
    },
    isLightColor(color) {
      try {
        return Quasar.colors.luminosity(color) > 0.5
      } catch (e) {
        console.warning(e)
        return false
      }
    }
  },
  watch: {
    'paymentsTable.search': {
      handler() {
        const props = {}
        if (this.paymentsTable.search) {
          props['search'] = this.paymentsTable.search
        }
        this.fetchPayments()
      }
    },
    'g.updatePayments'() {
      this.fetchPayments()
    }
  },
  created() {
    this.fetchPayments()
  }
})
