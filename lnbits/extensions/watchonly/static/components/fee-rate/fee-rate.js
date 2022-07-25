async function feeRate(path) {
  const template = await loadTemplateAsync(path)
  Vue.component('fees', {
    name: 'fees',
    template,

    props: ['totalfee', 'sats_denominated'],
    watch: {
      immediate: true,
      totalfee: function (newVal, oldVal) {
        console.log('### ', newVal, oldVal)
      }
    },

    data: function () {
      return {
        feeRate: 1,
        recommededFees: {
          fastestFee: 1,
          halfHourFee: 1,
          hourFee: 1,
          economyFee: 1,
          minimumFee: 1
        }
      }
    },

    methods: {
      satBtc(val, showUnit = true) {
        return satOrBtc(val, showUnit, this['sats_denominated'])
      },
      feeRateChanged: function (newFeeRate) {
        console.log('### value', newFeeRate)
        this.$emit('update:fee-rate', +newFeeRate)
      },
      refreshRecommendedFees: async function () {
        const {
          bitcoin: {fees: feesAPI}
        } = mempoolJS()

        const fn = async () => feesAPI.getFeesRecommended()
        this.recommededFees = await retryWithDelay(fn)
      },
      getFeeRateLabel: function (feeRate) {
        const fees = this.recommededFees
        if (feeRate >= fees.fastestFee)
          return `High Priority (${feeRate} sat/vB)`
        if (feeRate >= fees.halfHourFee)
          return `Medium Priority (${feeRate} sat/vB)`
        if (feeRate >= fees.hourFee) return `Low Priority (${feeRate} sat/vB)`
        return `No Priority (${feeRate} sat/vB)`
      }
    },

    created: async function () {
      console.log('### created fees ')
      await this.refreshRecommendedFees()
      this.feeRate = this.recommededFees.halfHourFee
      this.feeRateChanged(this.recommededFees.halfHourFee)
    }
  })
}
