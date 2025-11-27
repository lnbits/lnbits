window.app.component('lnbits-wallet-charts', {
  template: '#lnbits-wallet-charts',
  mixins: [window.windowMixin],
  props: ['paymentFilter', 'chartConfig'],
  data() {
    return {
      debounceTimeoutValue: 1337,
      debounceTimeout: null,
      chartData: [],
      chartDataPointCount: 0,
      walletBalanceChart: null,
      walletBalanceInOut: null,
      walletPaymentInOut: null,
      colorPrimary: Quasar.colors.changeAlpha(
        Quasar.colors.getPaletteColor('primary'),
        0.3
      ),
      colorSecondary: Quasar.colors.changeAlpha(
        Quasar.colors.getPaletteColor('secondary'),
        0.3
      ),
      barOptions: {
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
      }
    }
  },
  watch: {
    paymentFilter: {
      deep: true,
      handler() {
        this.changeCharts()
      }
    },
    chartConfig: {
      deep: true,
      handler(val) {
        this.$q.localStorage.setItem('lnbits.wallets.chartConfig', val)
        this.changeCharts()
      }
    }
  },
  methods: {
    // Debounce chart drawing and data fetching, if its called multiple times in quick succession
    // (e.g. when changing filters) chart.js will error because of a race condition trying to
    // destroy and redraw charts at the same time
    changeCharts() {
      if (this.debounceTimeout) {
        clearTimeout(this.debounceTimeout)
      }
      this.debounceTimeout = setTimeout(async () => {
        await this.fetchChartData()
        this.drawCharts()
      }, this.debounceTimeoutValue)
    },
    filterChartData() {
      const timeFrom = this.paymentFilter['time[ge]'] + 'T00:00:00'
      const timeTo = this.paymentFilter['time[le]'] + 'T23:59:59'
      let totalBalance = 0
      let data = this.chartData.map(p => {
        if (this.paymentFilter['amount[ge]'] !== undefined) {
          totalBalance += p.balance_in
          return {...p, balance: totalBalance, balance_out: 0, count_out: 0}
        }
        if (this.paymentFilter['amount[le]'] !== undefined) {
          totalBalance -= p.balance_out
          return {...p, balance: totalBalance, balance_in: 0, count_in: 0}
        }
        return {...p}
      })
      data = data.filter(p => {
        if (this.paymentFilter['time[ge]'] && this.paymentFilter['time[le]']) {
          return p.date >= timeFrom && p.date <= timeTo
        }
        if (this.paymentFilter['time[ge]']) {
          return p.date >= timeFrom
        }
        if (this.paymentFilter['time[le]']) {
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
    drawBalanceInOutChart(data, labels) {
      if (this.walletBalanceInOut) {
        this.walletBalanceInOut.destroy()
      }
      const ref = this.$refs.walletBalanceInOut
      if (!ref) return
      this.walletBalanceInOut = new Chart(ref.getContext('2d'), {
        type: 'bar',
        options: this.barOptions,
        data: {
          labels,
          datasets: [
            {
              label: 'Balance In',
              borderRadius: 5,
              data: data.map(s => s.balance_in),
              backgroundColor: this.colorPrimary
            },
            {
              label: 'Balance Out',
              borderRadius: 5,
              data: data.map(s => s.balance_out),
              backgroundColor: this.colorSecondary
            }
          ]
        }
      })
    },
    drawPaymentInOut(data, labels) {
      if (this.walletPaymentInOut) {
        this.walletPaymentInOut.destroy()
      }
      const ref = this.$refs.walletPaymentInOut
      if (!ref) return
      this.walletPaymentInOut = new Chart(ref.getContext('2d'), {
        type: 'bar',
        options: this.barOptions,
        data: {
          labels,
          datasets: [
            {
              label: 'Payments In',
              data: data.map(s => s.count_in),
              backgroundColor: this.colorPrimary
            },
            {
              label: 'Payments Out',
              data: data.map(s => -s.count_out),
              backgroundColor: this.colorSecondary
            }
          ]
        }
      })
    },
    drawBalanceChart(data, labels) {
      if (this.walletBalanceChart) {
        this.walletBalanceChart.destroy()
      }
      const ref = this.$refs.walletBalanceChart
      if (!ref) return
      this.walletBalanceChart = new Chart(ref.getContext('2d'), {
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
              backgroundColor: this.colorPrimary,
              borderColor: this.colorPrimary,
              borderWidth: 2,
              fill: true,
              tension: 0.7,
              fill: 1
            },
            {
              label: 'Fees',
              data: data.map(s => s.fee),
              pointStyle: false,
              backgroundColor: this.colorSecondary,
              borderColor: this.colorSecondary,
              borderWidth: 1,
              fill: true,
              tension: 0.7,
              fill: 1
            }
          ]
        }
      })
    },
    drawCharts() {
      const {data, labels} = this.filterChartData()
      if (this.chartConfig.showBalanceChart) {
        this.drawBalanceChart(data, labels)
      }
      if (this.chartConfig.showBalanceInOutChart) {
        this.drawBalanceInOutChart(data, labels)
      }
      if (this.chartConfig.showPaymentInOutChart) {
        this.drawPaymentInOut(data, labels)
      }
    },
    async fetchChartData() {
      try {
        const {data} = await LNbits.api.request(
          'GET',
          `/api/v1/payments/stats/daily?wallet_id=${this.g.wallet.id}`
        )
        this.chartData = data
      } catch (error) {
        console.warn(error)
        LNbits.utils.notifyApiError(error)
      }
    }
  },
  async created() {
    await this.fetchChartData()
    this.drawCharts()
  }
})
