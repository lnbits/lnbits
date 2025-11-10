window.app.component('lnbits-wallet-details', {
  mixins: [window.windowMixin],
  template: '#lnbits-wallet-details',
  data() {
    return {
      stored_paylinks: [],
      updateWallet: {
        name: null,
        currency: null
      }
    }
  },
  computed: {
    walletTitle() {
      return this.SITE_TITLE + ' Wallet: '
    }
  },
  watch: {
    'g.wallet': {
      handler() {
        this.stored_paylinks = this.g.wallet.stored_paylinks.links
        this.updateWallet.name = this.g.wallet.name
      }
    }
  },
  methods: {
    updatePaylinks() {
      LNbits.api
        .request(
          'PUT',
          `/api/v1/wallet/stored_paylinks/${this.g.wallet.id}`,
          this.g.wallet.adminkey,
          {
            links: this.stored_paylinks
          }
        )
        .then(() => {
          Quasar.Notify.create({
            message: 'Paylinks updated.',
            type: 'positive',
            timeout: 3500
          })
        })
        .catch(err => {
          LNbits.utils.notifyApiError(err)
        })
    },
    editPaylink() {
      this.$nextTick(() => {
        this.updatePaylinks()
      })
    },
    deletePaylink(lnurl) {
      const links = []
      this.stored_paylinks.forEach(link => {
        if (link.lnurl !== lnurl) {
          links.push(link)
        }
      })
      this.stored_paylinks = links
      this.updatePaylinks()
    }
  }
})
