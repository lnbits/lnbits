async function sendTo(path) {
  const template = await loadTemplateAsync(path)
  Vue.component('send-to', {
    name: 'send-to',
    template,

    props: [
      'data',
      'tx-size',
      'selected-amount',
      'fee-rate',
      'sats-denominated'
    ],

    computed: {
      dataLocal: {
        get: function () {
          return this.data
        },
        set: function (value) {
          console.log('### computed update data', value)
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
        const feeValue = this.feeRate * this.txSize
        const inputAmount = this.selectedAmount
        const currentAmount = Math.max(0, paymentAddress.amount || 0)
        const payedAmount = this.getTotalPaymentAmount() - currentAmount
        paymentAddress.amount = Math.max(
          0,
          inputAmount - payedAmount - feeValue
        )
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
}
