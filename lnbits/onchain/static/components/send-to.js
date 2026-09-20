import {satOrBtc, parseBitcoinRequest} from '../js/utils.js'
window.app.component('onchain-send-to', {
  name: 'onchain-send-to',
  template: '#onchain-send-to',

  props: ['data', 'tx-size', 'selected-amount', 'fee-rate', 'sats-denominated'],

  computed: {
    dataLocal: {
      get: function () {
        return this.data
      },
      set: function (value) {
        this.$emit('update:data', value)
      }
    }
  },

  data: function () {
    return {
      DUST_LIMIT: 546,
      paymentTable: {
        columns: [
          {
            name: 'data',
            align: 'left'
          }
        ],
        pagination: {
          rowsPerPage: 10
        },
        filter: ''
      }
    }
  },

  methods: {
    satBtc(val, showUnit = true) {
      return satOrBtc(val, showUnit, this.satsDenominated)
    },
    handleAddressInput(output) {
      try {
        const parsed = parseBitcoinRequest(output.address)
        output.address = parsed.address
        if (parsed.amount !== undefined) output.amount = parsed.amount
        output.error = ''
      } catch (error) {
        output.error = error.message
      }
      this.handleOutputsChange()
    },
    scanAddress(output) {
      this.g.scanner = value => {
        output.address = value
        this.handleAddressInput(output)
      }
    },
    addPaymentAddress: function () {
      this.dataLocal.push({address: '', amount: undefined})
      this.handleOutputsChange()
    },
    deletePaymentAddress: function (v) {
      const index = this.dataLocal.indexOf(v)
      if (index !== -1) {
        this.dataLocal.splice(index, 1)
      }
      this.handleOutputsChange()
    },

    sendMaxToAddress: function (paymentAddress = {}) {
      this.$emit('send-max', paymentAddress)
    },
    handleOutputsChange: function () {
      this.$emit('update:outputs')
    },
    getTotalPaymentAmount: function () {
      return this.dataLocal.reduce((t, a) => t + (a.amount || 0), 0)
    }
  },

  created: async function () {}
})
