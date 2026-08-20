window.app.component('lnbits-wallet-api-docs', {
  template: '#lnbits-wallet-api-docs',
  methods: {
    copyAdminKey() {
      LNbits.utils
        .confirmDialog(this.$t('admin_key_warning'))
        .onOk(() => LNbits.utils.copyText(this.g.wallet.adminkey))
    },
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
    },
    resetWebhookSecret() {
      LNbits.utils
        .confirmDialog(
          'Are you sure you want to reset your webhook signing secret? ' +
            'Receivers verifying webhook signatures will need the new secret.'
        )
        .onOk(() => {
          LNbits.api
            .resetWebhookSecret(this.g.wallet)
            .then(response => {
              const {id, webhook_secret} = response
              this.g.wallet = {
                ...this.g.wallet,
                webhook_secret
              }
              const walletIndex = this.g.user.wallets.findIndex(
                wallet => wallet.id === id
              )
              if (walletIndex !== -1) {
                this.g.user.wallets[walletIndex] = {
                  ...this.g.user.wallets[walletIndex],
                  webhook_secret
                }
              }
              this.webhookSecretHidden = false
              Quasar.Notify.create({
                timeout: 3500,
                type: 'positive',
                message: 'Webhook signing secret reset!'
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
      origin: window.location.origin,
      inkeyHidden: true,
      adminkeyHidden: true,
      walletIdHidden: true,
      webhookSecretHidden: true
    }
  }
})
