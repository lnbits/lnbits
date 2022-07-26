async function sendTo(path) {
  const template = await loadTemplateAsync(path)
  Vue.component('send-to', {
    name: 'send-to',
    template,

    props: ['data', 'tx-size', 'total-amount', 'fee-rate', 'sats_denominated'],

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
        amount: 0,
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
        return satOrBtc(val, showUnit, this['sats_denominated'])
      },
      addPaymentAddress: function () {
        this.dataLocal.push({address: '', amount: undefined})
      },
      deletePaymentAddress: function (v) {
        const index = this.dataLocal.indexOf(v)
        if (index !== -1) {
          this.dataLocal.splice(index, 1)
        }
      },
      getTotalPaymentAmount: function () {
        return this.dataLocal.reduce((t, a) => t + (a.amount || 0), 0)
      },
      sendMaxToAddress: function (paymentAddress = {}) {
        this.amount = 0
        // const tx = this.createTx(true)
        // this.payment.txSize = Math.round(txSize(tx))
        const fee = this['fee-rate'] * this['tx-size']
        const inputAmount = this['total-amount']
        const payedAmount = this.getTotalPaymentAmount()
        paymentAddress.amount = Math.max(0, inputAmount - payedAmount - fee)
      }
    },

    created: async function () {}
  })
}
