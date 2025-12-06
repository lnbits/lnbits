window.app.component('lnbits-admin-exchange-providers', {
  props: ['form-data'],
  template: '#lnbits-admin-exchange-providers',
  mixins: [window.windowMixin],
  data() {
    return {
      exchangeData: {
        selectedProvider: null,
        showTickerConversion: false,
        convertFromTicker: null,
        convertToTicker: null
      },
      exchangesTable: {
        columns: [
          {
            name: 'name',
            align: 'left',
            label: 'Exchange Name',
            field: 'name',
            sortable: true
          },
          {
            name: 'api_url',
            align: 'left',
            label: 'URL',
            field: 'api_url',
            sortable: false
          },
          {
            name: 'path',
            align: 'left',
            label: 'JSON Path',
            field: 'path',
            sortable: false
          },

          {
            name: 'exclude_to',
            align: 'left',
            label: 'Exclude Currencies',
            field: 'exclude_to',
            sortable: false
          },
          {
            name: 'ticker_conversion',
            align: 'left',
            label: 'Ticker Conversion',
            field: 'ticker_conversion',
            sortable: false
          }
        ],
        pagination: {
          sortBy: 'name',
          rowsPerPage: 100,
          page: 1,
          rowsNumber: 100
        },
        search: null,
        hideEmpty: true
      }
    }
  },
  mounted() {
    this.getExchangeRateHistory()
  },
  created() {
    const hash = window.location.hash.replace('#', '')
    if (hash === 'exchange_providers') {
      this.showExchangeProvidersTab(hash)
    }
  },
  methods: {
    getDefaultSetting(fieldName) {
      LNbits.api.getDefaultSetting(fieldName).then(response => {
        this.formData[fieldName] = response.data.default_value
      })
    },
    getExchangeRateHistory() {
      LNbits.api
        .request('GET', '/api/v1/rate/history', this.g.user.wallets[0].inkey)
        .then(response => {
          this.initExchangeChart(response.data)
        })
        .catch(function (error) {
          LNbits.utils.notifyApiError(error)
        })
    },
    showExchangeProvidersTab(tabName) {
      if (tabName === 'exchange_providers') {
        this.getExchangeRateHistory()
      }
    },
    addExchangeProvider() {
      this.formData.lnbits_exchange_rate_providers = [
        {
          name: '',
          api_url: '',
          path: '',
          exclude_to: []
        },
        ...this.formData.lnbits_exchange_rate_providers
      ]
    },
    removeExchangeProvider(provider) {
      this.formData.lnbits_exchange_rate_providers =
        this.formData.lnbits_exchange_rate_providers.filter(p => p !== provider)
    },
    removeExchangeTickerConversion(provider, ticker) {
      provider.ticker_conversion = provider.ticker_conversion.filter(
        t => t !== ticker
      )
      this.formData.touch = null
    },
    addExchangeTickerConversion() {
      if (!this.exchangeData.selectedProvider) {
        return
      }
      this.exchangeData.selectedProvider.ticker_conversion.push(
        `${this.exchangeData.convertFromTicker}:${this.exchangeData.convertToTicker}`
      )
      this.formData.touch = null
      this.exchangeData.showTickerConversion = false
    },
    showTickerConversionDialog(provider) {
      this.exchangeData.convertFromTicker = null
      this.exchangeData.convertToTicker = null
      this.exchangeData.selectedProvider = provider
      this.exchangeData.showTickerConversion = true
    },
    initExchangeChart(data) {
      const xValues = data.map(d =>
        this.utils.formatTimestamp(d.timestamp, 'HH:mm')
      )
      const exchanges = [
        ...this.formData.lnbits_exchange_rate_providers,
        {name: 'LNbits'}
      ]
      const datasets = exchanges.map(exchange => ({
        label: exchange.name,
        data: data.map(d => d.rates[exchange.name]),
        pointStyle: true,
        borderWidth: exchange.name === 'LNbits' ? 4 : 1,
        tension: 0.4
      }))
      this.exchangeRatesChart = new Chart(
        this.$refs.exchangeRatesChart.getContext('2d'),
        {
          type: 'line',
          options: {
            plugins: {
              legend: {
                display: false
              }
            }
          },
          data: {
            labels: xValues,
            datasets
          }
        }
      )
    }
  }
})
