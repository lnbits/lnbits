import {retryWithDelay, satOrBtc} from '../js/utils.js'
import {mempoolJS} from '../js/mempool-client.js'
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
      return satOrBtc(val, showUnit, this.satsDenominated)
    },

    refreshRecommendedFees: async function () {
      if (this.refreshing) return
      this.refreshing = true
      const fn = async () => {
        const {
          bitcoin: {fees: feesAPI}
        } = mempoolJS({
          hostname: this.mempoolEndpoint
        })
        return feesAPI.getFeesRecommended()
      }
      try {
        this.recommededFees = await retryWithDelay(fn)
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
    this.feeRate = this.recommededFees.halfHourFee
  }
})
