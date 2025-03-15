window.PaymentsPageLogic = {
  mixins: [window.windowMixin],
  data() {
    return {
      payments: [],
      dailyChartData: [],
      searchDate: {from: null, to: null},
      searchData: {
        wallet_id: null,
        payment_hash: null,
        status: null,
        memo: null
      },
      chartData: {
        showPaymentStatus: true,
        showPaymentTags: true,
        showBalance: true,
        showWalletsSize: false,
        showBalanceInOut: false,
        showPaymentCountInOut: false
      },
      searchOptions: {
        status: []
        // tag: [] // not used, payments don't have tag, only the extra
      },
      paymentsTable: {
        columns: [
          {
            name: 'status',
            align: 'left',
            label: 'Status',
            field: 'status',
            sortable: false
          },
          {
            name: 'created_at',
            align: 'left',
            label: 'Created At',
            field: 'created_at',
            sortable: true
          },
          {
            name: 'amount',
            align: 'right',
            label: 'Amount',
            field: 'amount',
            sortable: true
          },
          {
            name: 'amountFiat',
            align: 'right',
            label: 'Fiat',
            field: 'amountFiat',
            sortable: false
          },
          {
            name: 'fee',
            align: 'left',
            label: 'Fee',
            field: 'fee',
            sortable: true
          },

          {
            name: 'tag',
            align: 'left',
            label: 'Tag',
            field: 'tag',
            sortable: false
          },
          {
            name: 'memo',
            align: 'left',
            label: 'Memo',
            field: 'memo',
            sortable: false,
            max_length: 20
          },
          {
            name: 'wallet_id',
            align: 'left',
            label: 'Wallet (ID)',
            field: 'wallet_id',
            sortable: false
          },

          {
            name: 'payment_hash',
            align: 'left',
            label: 'Payment Hash',
            field: 'payment_hash',
            sortable: false
          }
        ],
        pagination: {
          sortBy: 'created_at',
          rowsPerPage: 25,
          page: 1,
          descending: true,
          rowsNumber: 10
        },
        search: null,
        hideEmpty: true,
        loading: false
      },
      chartsReady: false,
      showDetails: false,
      paymentDetails: null,
      lnbitsBalance: 0
    }
  },
  async mounted() {
    this.chartsReady = true
    await this.$nextTick()
    this.initCharts()
    await this.fetchPayments()
  },
  computed: {},
  methods: {
    async fetchPayments(props) {
      const filter = Object.entries(this.searchData).reduce(
        (a, [k, v]) => (v ? ((a[k] = v), a) : a),
        {}
      )

      delete filter['time[ge]']
      delete filter['time[le]']
      if (this.searchDate.from) {
        filter['time[ge]'] = this.searchDate.from + 'T00:00:00'
      }
      if (this.searchDate.to) {
        filter['time[le]'] = this.searchDate.to + 'T23:59:59'
      }
      this.paymentsTable.filter = filter

      try {
        const params = LNbits.utils.prepareFilterQuery(
          this.paymentsTable,
          props
        )
        const {data} = await LNbits.api.request(
          'GET',
          `/api/v1/payments/all/paginated?${params}`
        )

        this.paymentsTable.pagination.rowsNumber = data.total
        this.payments = data.data.map(p => {
          if (p.extra && p.extra.tag) {
            p.tag = p.extra.tag
          }
          p.timeFrom = moment(p.created_at).fromNow()
          p.outgoing = p.amount < 0
          p.amount =
            new Intl.NumberFormat(window.LOCALE).format(p.amount / 1000) +
            ' sats'
          if (p.extra?.wallet_fiat_amount) {
            p.amountFiat = this.formatCurrency(
              p.extra.wallet_fiat_amount,
              p.extra.wallet_fiat_currency
            )
          }

          return p
        })
      } catch (error) {
        console.error(error)
        LNbits.utils.notifyApiError(error)
      } finally {
        this.updateCharts(props)
      }
    },
    async searchPaymentsBy(fieldName, fieldValue) {
      if (fieldName) {
        this.searchData[fieldName] = fieldValue
      }
      await this.fetchPayments()
    },
    clearDateSeach() {
      this.searchDate = {from: null, to: null}
      delete this.paymentsTable.filter['time[ge]']
      delete this.paymentsTable.filter['time[le]']
      this.fetchPayments()
    },
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

    showDetailsToggle(payment) {
      this.paymentDetails = payment
      return (this.showDetails = !this.showDetails)
    },
    formatDate(dateString) {
      return LNbits.utils.formatDateString(dateString)
    },
    formatCurrency(amount, currency) {
      try {
        return LNbits.utils.formatCurrency(amount, currency)
      } catch (e) {
        console.error(e)
        return `${amount} ???`
      }
    },
    shortify(value, max_length = 10) {
      valueLength = (value || '').length
      if (valueLength <= max_length) {
        return value
      }
      return `${value.substring(0, 5)}...${value.substring(valueLength - 5, valueLength)}`
    },
    async updateCharts(props) {
      let params = LNbits.utils.prepareFilterQuery(this.paymentsTable, props)

      try {
        const {data} = await LNbits.api.request(
          'GET',
          `/api/v1/payments/stats/count?${params}&count_by=status`
        )
        data.sort((a, b) => a.field - b.field)
        this.searchOptions.status = data
          .map(s => s.field)
          .sort()
          .reverse()
        this.paymentsStatusChart.data.datasets[0].data = data.map(s => s.total)
        this.paymentsStatusChart.data.labels = [...this.searchOptions.status]

        this.paymentsStatusChart.update()
      } catch (error) {
        console.warn(error)
        LNbits.utils.notifyApiError(error)
      }
      try {
        const {data} = await LNbits.api.request(
          'GET',
          `/api/v1/payments/stats/wallets?${params}`
        )

        const counts = data.map(w => w.balance / w.payments_count)

        const min = Math.min(...counts)
        const max = Math.max(...counts)

        const scale = val => {
          return Math.floor(3 + ((val - min) * (25 - 3)) / (max - min))
        }

        const colors = this.randomColors(20)
        const walletsData = data.map((w, i) => {
          return {
            data: [
              {
                x: w.payments_count,
                y: w.balance,
                r: scale(Math.max(w.balance / w.payments_count, 5))
              }
            ],
            label: w.wallet_name,
            wallet_id: w.wallet_id,
            backgroundColor: colors[i % 100],
            hoverOffset: 4
          }
        })
        this.paymentsWalletsChart.data.datasets = walletsData
        this.paymentsWalletsChart.update()
      } catch (error) {
        console.warn(error)
        LNbits.utils.notifyApiError(error)
      }

      try {
        const {data} = await LNbits.api.request(
          'GET',
          `/api/v1/payments/stats/count?${params}&count_by=tag`
        )
        this.searchOptions.tag = data.map(s => s.field)
        this.searchOptions.status.sort()
        this.paymentsTagsChart.data.datasets[0].data = data.map(rm => rm.total)
        this.paymentsTagsChart.data.labels = data.map(rm => rm.field || 'core')
        this.paymentsTagsChart.update()
      } catch (error) {
        console.warn(error)
        LNbits.utils.notifyApiError(error)
      }

      try {
        const filter = Object.entries(this.searchData).reduce(
          (a, [k, v]) => (v ? ((a[k] = v), a) : a),
          {}
        )
        const paymentsTable = {...this.paymentsTable, filter: filter}
        const noTimeParams = LNbits.utils.prepareFilterQuery(
          paymentsTable,
          props
        )
        let {data} = await LNbits.api.request(
          'GET',
          `/api/v1/payments/stats/daily?${noTimeParams}`
        )

        const timeFrom = this.searchDate.from + 'T00:00:00'
        const timeTo = this.searchDate.to + 'T23:59:59'
        this.lnbitsBalance = data.length ? data[data.length - 1].balance : 0
        data = data.filter(p => {
          if (this.searchDate.from && this.searchDate.to) {
            return p.date >= timeFrom && p.date <= timeTo
          }
          if (this.searchDate.from) {
            return p.date >= timeFrom
          }
          if (this.searchDate.to) {
            return p.date <= timeTo
          }
          return true
        })

        this.paymentsDailyChart.data.datasets = [
          {
            label: 'Balance',
            data: data.map(s => s.balance),
            pointStyle: false,
            borderWidth: 2,
            tension: 0.7,
            fill: 1
          },
          {
            label: 'Fees',
            data: data.map(s => s.fee),
            pointStyle: false,
            borderWidth: 1,
            tension: 0.4,
            fill: 1
          }
        ]
        this.paymentsDailyChart.data.labels = data.map(s =>
          s.date.substring(0, 10)
        )
        this.paymentsDailyChart.update()

        this.paymentsBalanceInOutChart.data.datasets = [
          {
            label: 'Incoming Payments Balance',
            data: data.map(s => s.balance_in)
          },
          {
            label: 'Outgoing Payments Balance',
            data: data.map(s => s.balance_out)
          }
        ]
        this.paymentsBalanceInOutChart.data.labels = data.map(s =>
          s.date.substring(0, 10)
        )
        this.paymentsBalanceInOutChart.update()

        this.paymentsCountInOutChart.data.datasets = [
          {
            label: 'Incoming Payments Count',
            data: data.map(s => s.count_in)
          },
          {
            label: 'Outgoing Payments Count',
            data: data.map(s => -s.count_out)
          }
        ]
        this.paymentsCountInOutChart.data.labels = data.map(s =>
          s.date.substring(0, 10)
        )
        this.paymentsCountInOutChart.update()
      } catch (error) {
        console.warn(error)
        LNbits.utils.notifyApiError(error)
      }
    },
    async initCharts() {
      const chartData =
        this.$q.localStorage.getItem('lnbits.payments.chartData') || {}

      this.chartData = {...this.chartData, ...chartData}
      if (!this.chartsReady) {
        console.warn('Charts are not ready yet. Initialization delayed.')
        return
      }
      this.paymentsStatusChart = new Chart(
        this.$refs.paymentsStatusChart.getContext('2d'),
        {
          type: 'doughnut',

          options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
              title: {
                display: false
              }
            },
            onClick: (_, elements, chart) => {
              if (elements[0]) {
                const i = elements[0].index
                this.searchPaymentsBy('status', chart.data.labels[i])
              }
            }
          },
          data: {
            datasets: [
              {
                label: '',
                data: [],
                backgroundColor: [
                  'rgb(0, 205, 86)',
                  'rgb(54, 162, 235)',
                  'rgb(255, 99, 132)',
                  'rgb(255, 5, 86)',
                  'rgb(25, 205, 86)',
                  'rgb(255, 205, 250)'
                ],
                hoverOffset: 4
              }
            ]
          }
        }
      )
      this.paymentsWalletsChart = new Chart(
        this.$refs.paymentsWalletsChart.getContext('2d'),
        {
          type: 'bubble',

          options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
              legend: {
                display: false
              },
              title: {
                display: false
              }
            },
            onClick: (_, elements, chart) => {
              if (elements[0]) {
                const i = elements[0].datasetIndex
                this.searchPaymentsBy(
                  'wallet_id',
                  chart.data.datasets[i].wallet_id
                )
              }
            }
          },
          data: {
            datasets: [
              {
                label: '',
                data: [],
                backgroundColor: this.randomColors(20),
                hoverOffset: 4
              }
            ]
          }
        }
      )
      this.paymentsTagsChart = new Chart(
        this.$refs.paymentsTagsChart.getContext('2d'),
        {
          type: 'pie',

          options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
              title: {
                display: false
              },
              legend: {
                display: false,
                title: {
                  display: false,
                  text: 'Tags'
                }
              }
            },
            onClick: (_, elements, chart) => {
              if (elements[0]) {
                const i = elements[0].index
                this.searchPaymentsBy('tag', chart.data.labels[i])
              }
            }
          },
          data: {
            datasets: [
              {
                label: '',
                data: [],
                backgroundColor: this.randomColors(10),
                hoverOffset: 4
              }
            ]
          }
        }
      )
      this.paymentsDailyChart = new Chart(
        this.$refs.paymentsDailyChart.getContext('2d'),
        {
          type: 'line',

          options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
              title: {
                display: false
              },
              legend: {
                display: true,
                title: {
                  display: false,
                  text: 'Tags'
                }
              }
            }
          },
          data: {
            datasets: [
              {
                label: '',
                data: [],
                backgroundColor: this.randomColors(10),
                hoverOffset: 4
              }
            ]
          }
        }
      )
      this.paymentsBalanceInOutChart = new Chart(
        this.$refs.paymentsBalanceInOutChart.getContext('2d'),
        {
          type: 'bar',

          options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
              title: {
                display: false
              },
              legend: {
                display: true,
                title: {
                  display: false,
                  text: 'Tags'
                }
              }
            },
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
            datasets: [
              {
                label: '',
                data: [],
                backgroundColor: this.randomColors(50),
                hoverOffset: 4
              }
            ]
          }
        }
      )

      this.paymentsCountInOutChart = new Chart(
        this.$refs.paymentsCountInOutChart.getContext('2d'),
        {
          type: 'bar',

          options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
              title: {
                display: false
              },
              legend: {
                display: true,
                title: {
                  display: false,
                  text: ''
                }
              }
            },
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
            datasets: [
              {
                label: '',
                data: [],
                backgroundColor: this.randomColors(80),
                hoverOffset: 4
              }
            ]
          }
        }
      )
    },
    saveChartsPreferences() {
      this.$q.localStorage.set('lnbits.payments.chartData', this.chartData)
    },
    randomColors(seed = 1) {
      const colors = []
      for (let i = 1; i <= 10; i++) {
        for (let j = 1; j <= 10; j++) {
          colors.push(
            `rgb(${(j * seed * 33) % 200}, ${(71 * (i + j + seed)) % 255}, ${(i + seed * 30) % 255})`
          )
        }
      }
      return colors
    }
  }
}
