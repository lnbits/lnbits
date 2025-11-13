window.app.component('lnbits-wallet-paylinks', {
  template: '#lnbits-wallet-paylinks',
  mixins: [window.windowMixin],
  data() {
    return {
      storedPaylinks: []
    }
  },
  watch: {
    'g.wallet'(val) {
      this.storedPaylinks = val.storedPaylinks ?? []
    }
  },
  created() {
    this.storedPaylinks = this.g.wallet.storedPaylinks
  },
  methods: {
    dateFromNow(unix) {
      const date = new Date(unix * 1000)
      return moment.utc(date).local().fromNow()
    },
    updatePaylinks() {
      LNbits.api
        .request(
          'PUT',
          `/api/v1/wallet/stored_paylinks/${this.g.wallet.id}`,
          this.g.wallet.adminkey,
          {
            links: this.storedPaylinks
          }
        )
        .then(() => {
          this.$q.notify({
            message: 'Paylinks updated.',
            type: 'positive',
            timeout: 3500
          })
        })
        .catch(err => {
          LNbits.utils.notifyApiError(err)
        })
    },
    sendToPaylink(lnurl) {
      this.$emit('send-lnurl', lnurl)
    },
    editPaylink() {
      this.$nextTick(() => {
        this.updatePaylinks()
      })
    },
    deletePaylink(lnurl) {
      const links = []
      this.storedPaylinks.forEach(link => {
        if (link.lnurl !== lnurl) {
          links.push(link)
        }
      })
      this.storedPaylinks = links
      this.updatePaylinks()
    }
  }
})
