window.app.component('onchain-fee-rate', {
  name: 'onchain-fee-rate',
  template: '#onchain-fee-rate',

  props: ['rate', 'fee-value', 'sats-denominated', 'mempool-endpoint'],

  computed: {
    feeRate: {
      get: function () {
        return this['rate']
      },
      set: function (value) {
        this.$emit('update:rate', +value)
      }
    },
    sliderPosition: {
      get() {
        const rate = Number(this.feeRate) || 1
        return Math.log10(Math.min(1000, Math.max(1, rate)))
      },
      set(position) {
        this.feeRate = Math.round(10 ** position)
      }
    }
  },

  data: function () {
    return {
      refreshing: false,
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
      return LNbits.onchain.utils.satOrBtc(val, showUnit, this.satsDenominated)
    },

    refreshRecommendedFees: async function () {
      if (this.refreshing) return
      this.refreshing = true
      const fn = async () => {
        const {
          bitcoin: {fees: feesAPI}
        } = LNbits.onchain.mempoolJS({
          hostname: this.mempoolEndpoint
        })
        return feesAPI.getFeesRecommended()
      }
      try {
        this.recommededFees = await LNbits.onchain.utils.retryWithDelay(fn)
        this.feeRate = this.recommededFees.halfHourFee
      } catch (error) {
        this.$q.notify({
          type: 'warning',
          message: 'Failed to refresh fee rates. Please try again.'
        })
      } finally {
        this.refreshing = false
      }
    },
    getFeeRateLabel: function (feeRate) {
      const fees = this.recommededFees
      if (feeRate >= fees.fastestFee) return `High Priority (${feeRate} sat/vB)`
      if (feeRate >= fees.halfHourFee)
        return `Medium Priority (${feeRate} sat/vB)`
      if (feeRate >= fees.hourFee) return `Low Priority (${feeRate} sat/vB)`
      return `No Priority (${feeRate} sat/vB)`
    }
  },

  created: async function () {
    await this.refreshRecommendedFees()
  }
})
