window.app.component('lnbits-wallet-api-docs', {
  template: '#lnbits-wallet-api-docs',
  mixins: [window.windowMixin],
  methods: {
    resetKeys() {
      LNbits.utils
        .confirmDialog('Are you sure you want to reset your API keys?')
        .onOk(() => {
          LNbits.api
            .resetWalletKeys(this.g.wallet)
            .then(response => {
              const {id, adminkey, inkey} = response
              this.g.wallet = {
                ...this.g.wallet,
                inkey,
                adminkey
              }
              const walletIndex = this.g.user.wallets.findIndex(
                wallet => wallet.id === id
              )
              if (walletIndex !== -1) {
                this.g.user.wallets[walletIndex] = {
                  ...this.g.user.wallets[walletIndex],
                  inkey,
                  adminkey
                }
              }
              Quasar.Notify.create({
                timeout: 3500,
                type: 'positive',
                message: 'API keys reset!'
              })
            })
            .catch(err => {
              LNbits.utils.notifyApiError(err)
            })
        })
    }
  },
  data() {
    return {
      inkeyHidden: true,
      adminkeyHidden: true,
      walletIdHidden: true
    }
  }
})
