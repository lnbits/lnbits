import {satOrBtc} from '../js/utils.js'
window.app.component('onchain-wallet-config', {
  name: 'onchain-wallet-config',
  template: '#onchain-wallet-config',

  props: ['total', 'config-data', 'adminkey', 'busy'],
  emits: ['update:config-data'],
  data: function () {
    return {
      networkOptions: [
        {label: 'Mainnet', value: 'Mainnet'},
        {label: 'Testnet4', value: 'Testnet4'},
        {label: 'Testnet3', value: 'Testnet'}
      ],
      internalConfig: {},
      loadError: false,
      show: false
    }
  },

  computed: {
    explorerOptions() {
      const available =
        this.config.lnbits_explorer_network === this.config.network
      return [
        {
          label: available
            ? 'LNbits block explorer'
            : 'LNbits block explorer (unavailable for this network)',
          value: 'lnbits',
          disable: !available
        },
        {label: 'Mempool', value: 'mempool'}
      ]
    },
    config: {
      get() {
        return this.internalConfig
      },
      set(value) {
        value.isLoaded = true
        this.internalConfig = JSON.parse(JSON.stringify(value))
        this.$emit(
          'update:config-data',
          JSON.parse(JSON.stringify(this.internalConfig))
        )
      }
    }
  },

  watch: {
    'internalConfig.network'(network) {
      if (
        this.config.explorer_provider === 'lnbits' &&
        this.config.lnbits_explorer_network !== network
      ) {
        this.internalConfig.explorer_provider = 'mempool'
      }
    }
  },

  methods: {
    openSettings() {
      this.internalConfig = JSON.parse(JSON.stringify(this.configData))
      this.show = true
    },
    satBtc(val, showUnit = true) {
      return satOrBtc(val, showUnit, this.config.sats_denominated)
    },
    updateConfig: async function () {
      try {
        const {data} = await LNbits.api.request(
          'PUT',
          '/onchain/api/v1/config',
          this.adminkey,
          this.config
        )
        this.show = false
        this.config = data
      } catch (error) {
        LNbits.utils.notifyApiError(error)
      }
    },
    getConfig: async function () {
      this.loadError = false
      try {
        const {data} = await LNbits.api.request(
          'GET',
          '/onchain/api/v1/config',
          this.adminkey
        )
        this.config = data
      } catch (error) {
        this.loadError = true
        LNbits.utils.notifyApiError(error)
      }
    }
  },
  created: async function () {
    await this.getConfig()
  }
})
