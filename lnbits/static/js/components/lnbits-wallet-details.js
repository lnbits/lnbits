window.app.component('lnbits-wallet-details', {
  mixins: [window.windowMixin],
  template: '#lnbits-wallet-details',
  data() {
    return {
      chartData: [],
      chartDataPointCount: 0,
      chartConfig: {
        showBalance: true,
        showBalanceInOut: true,
        showPaymentCountInOut: true
      },
      walletBalanceChart: null,
      stored_paylinks: [],
      updateWallet: {
        name: '',
        currency: null
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
      }
    }
  },
  computed: {
    walletTitle() {
      return this.SITE_TITLE + ' Wallet: '
    }
  },
  watch: {
    'g.wallet': {
      handler() {
        if (this.g.wallet.stored_paylinks) {
          this.stored_paylinks = this.g.wallet.stored_paylinks.links
        }
        this.updateWallet.name = this.g.wallet.name
      }
    }
  },
  methods: {
    handleFiatTracking() {
      this.g.fiatTracking = !this.g.fiatTracking
      if (!this.g.fiatTracking) {
        this.$q.localStorage.setItem('lnbits.isFiatPriority', false)
        this.isFiatPriority = false
        this.g.wallet.currency = ''
        this.updateWallet({currency: ''})
      } else {
        // this.g.wallet.currency = this.update.currency
        // this.updateWallet({currency: this.update.currency})
        // this.updateFiatBalance(this.update.currency)
      }
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
    },
    async fetchChartData() {
      if (this.mobileSimple) {
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
    hasChartActive() {
      return (
        this.chartConfig.showBalance ||
        this.chartConfig.showBalanceInOut ||
        this.chartConfig.showPaymentCountInOut
      )
    }
  },
  created() {
    this.fetchChartData()
  }
})
