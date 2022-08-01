async function feeRate(path) {
  const template = await loadTemplateAsync(path)
  Vue.component('fee-rate', {
    name: 'fee-rate',
    template,

    props: ['rate', 'fee-value', 'sats-denominated', 'mempool-endpoint'],

    computed: {
      feeRate: {
        get: function () {
          return this['rate']
        },
        set: function (value) {
          this.$emit('update:rate', +value)
        }
      }
    },

    data: function () {
      return {
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
        return satOrBtc(val, showUnit, this.satsDenominated)
      },

      refreshRecommendedFees: async function () {
        const fn = async () => {
          const {
            bitcoin: {fees: feesAPI}
          } = mempoolJS({
            hostname: this.mempoolEndpoint
          })
          return feesAPI.getFeesRecommended()
        }
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
      await this.refreshRecommendedFees()
      this.feeRate = this.recommededFees.halfHourFee
    }
  })
}
