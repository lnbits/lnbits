window.app.component('payment-list', {
  name: 'payment-list',
  template: '#payment-list',
  props: ['update', 'lazy', 'wallet'],
  mixins: [window.windowMixin],
  data() {
    return {
      denomination: LNBITS_DENOMINATION,
      failedPaymentsToggle: false,
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
        filter: {
          'status[ne]': 'failed',
          'amount[ge]': 0
        },
        loading: false
      },
      searchDate: {from: null, to: null},
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
        loading: false
      },
      filters: {
        success: true,
        pending: true,
        failed: false,
        incoming: true,
        outgoing: true
      }
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
      if (this.$q.screen.lt.md && this.mobileSimple) {
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
        this.paymentsTable.filter['time[ge]'] =
          this.searchDate.from + 'T00:00:00'
      }
      if (this.searchDate.to) {
        this.paymentsTable.filter['time[le]'] = this.searchDate.to + 'T23:59:59'
      }

      this.fetchPayments()
    },
    clearDateSeach() {
      this.searchDate = {from: null, to: null}
      delete this.paymentsTable.filter['time[ge]']
      delete this.paymentsTable.filter['time[le]']
      this.fetchPayments()
    },
    fetchPayments(props) {
      this.$emit('filter-changed', {...this.paymentsTable.filter})
      const params = LNbits.utils.prepareFilterQuery(this.paymentsTable, props)
      return LNbits.api
        .getPayments(this.currentWallet, params)
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
    computedFilter() {
      console.log('computedFilter')
      const {success, pending, failed, incoming, outgoing} = this.filters
      // Build the status part:
      const statuses = {success, pending, failed}
      const allowed = Object.keys(statuses).filter(key => statuses[key])
      const allStatuses = Object.keys(statuses)
      let statusFilter = {}
      if (allowed.length === 1) {
        statusFilter = {'status[eq]': allowed[0]}
      } else if (allowed.length === 2) {
        const disallowed = allStatuses.find(key => !statuses[key])
        statusFilter = {'status[ne]': disallowed}
      }
      // If all are true (or if allowed.length === 0, handle as needed) then no status filter.

      // Build the amount part:
      let amountFilter = {}
      if (incoming && !outgoing) {
        // Only incoming: amounts >= 0
        amountFilter = {'amount[ge]': 0}
      } else if (!incoming && outgoing) {
        // Only outgoing: amounts < 0
        amountFilter = {'amount[le]': 0}
      }
      console.log('statusFilter', statusFilter)
      console.log('amountFilter', amountFilter)
      // Both incoming and outgoing: no filter
      const newFilter = {...statusFilter, ...amountFilter}
      if (
        JSON.stringify(this.paymentsTable.filter) !== JSON.stringify(newFilter)
      ) {
        this.paymentsTable.filter = {...newFilter}
        // this.paymentsTable.pagination.page = 1
        // this.fetchPayments()
      }
    }
  },
  watch: {
    // computedFilter: {
    //   handler(newFilter) {
    //     console.log('computedFilter', newFilter)
    //     // Compare new filter with the current one. (You can use a deep comparison method here.)
    //     if (
    //       JSON.stringify(this.paymentsTable.filter) !==
    //       JSON.stringify(newFilter)
    //     ) {
    //       // Replace the filter with a fresh object so it doesn't trigger unwanted deep watching.
    //       this.paymentsTable.filter = {...newFilter}
    //       console.log('computedFilter', this.paymentsTable.filter)
    //       // Optionally reset pagination.
    //       // this.paymentsTable.pagination.page = 1
    //       // Call the API.
    //       debugger
    //       //this.fetchPayments()
    //     }
    //   },
    //   deep: true
    // },
    // failedPaymentsToggle(newVal) {
    //   if (newVal === false) {
    //     this.paymentsTable.filter['status[ne]'] = 'failed'
    //   } else {
    //     delete this.paymentsTable.filter['status[ne]']
    //   }
    //   this.paymentsTable.pagination.page = 1
    //   this.fetchPayments()
    // },
    'paymentsTable.search': {
      handler() {
        const props = {}
        if (this.paymentsTable.search) {
          props['search'] = this.paymentsTable.search
        }
        this.fetchPayments()
      }
    },
    lazy(newVal) {
      if (newVal === true) this.fetchPayments()
    },
    update() {
      this.fetchPayments()
    },
    'g.updatePayments'() {
      this.fetchPayments()
    },
    'g.wallet': {
      handler(newWallet) {
        this.fetchPayments()
      },
      deep: true
    }
  },
  created() {
    console.log(this.paymentsTable.filter)
    if (this.lazy === undefined) this.fetchPayments()
  }
})
