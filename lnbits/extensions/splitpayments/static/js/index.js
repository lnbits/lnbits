/* globals Quasar, Vue, _, VueQrcode, windowMixin, LNbits, LOCALE */

Vue.component(VueQrcode.name, VueQrcode)

function hashTargets(targets) {
  return targets
    .filter(isTargetComplete)
    .map(({wallet, percent, alias}) => `${wallet}${percent}${alias}`)
    .join('')
}

function isTargetComplete(target) {
  return (
    target.wallet &&
    target.wallet.trim() !== '' &&
    (target.percent > 0 || target.tag != '')
  )
}

new Vue({
  el: '#vue',
  mixins: [windowMixin],
  data() {
    return {
      selectedWallet: null,
      currentHash: '', // a string that must match if the edit data is unchanged
      targets: [
        {
          method: 'split'
        }
      ]
    }
  },
  computed: {
    isDirty() {
      return hashTargets(this.targets) !== this.currentHash
    }
  },
  methods: {
    clearTargets() {
      this.targets = [{}]
      this.$q.notify({
        message:
          'Cleared the form, but not saved. You must click to save manually.',
        timeout: 500
      })
    },
    clearTarget(index) {
      this.targets.splice(index, 1)
      console.log(this.targets)
      this.$q.notify({
        message: 'Removed item. You must click to save manually.',
        timeout: 500
      })
    },
    getTargets() {
      LNbits.api
        .request(
          'GET',
          '/splitpayments/api/v1/targets',
          this.selectedWallet.adminkey
        )
        .catch(err => {
          LNbits.utils.notifyApiError(err)
        })
        .then(response => {
          this.currentHash = hashTargets(response.data)
          this.targets = response.data.concat({})
          for (let i = 0; i < this.targets.length; i++) {
            if (this.targets[i].tag.length > 0) {
              this.targets[i].method = 'tag'
            } else if (this.targets[i].percent.length > 0) {
              this.targets[i].method = 'split'
            } else {
              this.targets[i].method = ''
            }
          }
        })
    },
    changedWallet(wallet) {
      this.selectedWallet = wallet
      this.getTargets()
    },
    clearChanged(index) {
      if (this.targets[index].method == 'split') {
        this.targets[index].tag = null
        this.targets[index].method = 'split'
      } else {
        this.targets[index].percent = null
        this.targets[index].method = 'tag'
      }
    },
    targetChanged(index) {
      // fix percent min and max range
      if (this.targets[index].percent) {
        if (this.targets[index].percent > 100) this.targets[index].percent = 100
        if (this.targets[index].percent < 0) this.targets[index].percent = 0
        this.targets[index].tag = ''
      }

      // not percentage
      if (!this.targets[index].percent) {
        this.targets[index].percent = 0
      }

      // remove empty lines (except last)
      if (this.targets.length >= 2) {
        for (let i = this.targets.length - 2; i >= 0; i--) {
          let target = this.targets[i]
          if (
            (!target.wallet || target.wallet.trim() === '') &&
            (!target.alias || target.alias.trim() === '') &&
            (!target.tag || target.tag.trim() === '') &&
            !target.percent
          ) {
            this.targets.splice(i, 1)
          }
        }
      }

      // add a line at the end if the last one is filled
      let last = this.targets[this.targets.length - 1]
      if (last.wallet && last.wallet.trim() !== '') {
        this.targets.push({})
      }

      // sum of all percents
      let currentTotal = this.targets.reduce(
        (acc, target) => acc + (target.percent || 0),
        0
      )

      // remove last (unfilled) line if the percent is already 100
      if (currentTotal >= 100) {
        let last = this.targets[this.targets.length - 1]
        if (
          (!last.wallet || last.wallet.trim() === '') &&
          (!last.alias || last.alias.trim() === '') &&
          !last.percent
        ) {
          this.targets = this.targets.slice(0, -1)
        }
      }

      // adjust percents of other lines (not this one)
      if (currentTotal > 100 && isPercent) {
        let diff = (currentTotal - 100) / (100 - this.targets[index].percent)
        this.targets.forEach((target, t) => {
          if (t !== index) target.percent -= +(diff * target.percent).toFixed(2)
        })
      }
      // overwrite so changes appear
      this.targets = this.targets
    },
    saveTargets() {
      for (let i = 0; i < this.targets.length; i++) {
        if (this.targets[i].tag != '') {
          this.targets[i].percent = 0
        } else {
          this.targets[i].tag = ''
        }
      }
      LNbits.api
        .request(
          'PUT',
          '/splitpayments/api/v1/targets',
          this.selectedWallet.adminkey,
          {
            targets: this.targets
              .filter(isTargetComplete)
              .map(({wallet, percent, tag, alias}) => ({
                wallet,
                percent,
                tag,
                alias
              }))
          }
        )
        .then(response => {
          this.$q.notify({
            message: 'Split payments targets set.',
            timeout: 700
          })
          this.getTargets()
        })
        .catch(err => {
          LNbits.utils.notifyApiError(err)
        })
    }
  },
  created() {
    this.selectedWallet = this.g.user.wallets[0]
    this.getTargets()
  }
})
