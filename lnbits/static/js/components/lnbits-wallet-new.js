window.app.component('lnbits-wallet-new', {
  template: '#lnbits-wallet-new',
  mixins: [window.windowMixin],
  data() {
    return {
      walletTypes: [{label: 'Lightning Wallet', value: 'lightning'}],
      newWallet: {name: '', sharedWalletId: ''}
    }
  },
  computed: {
    inviteWalletOptions() {
      return (this.g.user?.extra?.wallet_invite_requests || []).map(i => ({
        label: `${i.to_wallet_name} (from ${i.from_user_name})`,
        value: i.to_wallet_id
      }))
    }
  },
  methods: {
    async submitRejectWalletInvitation() {
      try {
        const inviteRequests = this.g.user.extra.wallet_invite_requests || []
        const invite = inviteRequests.find(
          invite => invite.to_wallet_id === this.newWallet.sharedWalletId
        )
        if (!invite) {
          Quasar.Notify.create({
            message: 'Cannot find invitation for the selected wallet.',
            type: 'warning'
          })
          return
        }
        await LNbits.api.request(
          'DELETE',
          `/api/v1/wallet/share/invite/${invite.request_id}`,
          this.g.wallet.adminkey
        )

        Quasar.Notify.create({
          message: 'Invitation rejected.',
          type: 'positive'
        })
        this.g.user.extra.wallet_invite_requests = inviteRequests.filter(
          inv => inv.request_id !== invite.request_id
        )
      } catch (err) {
        LNbits.utils.notifyApiError(err)
      }
    },
    async submitAddWallet() {
      const data = this.newWallet
      if (this.g.newWalletType === 'lightning' && !data.name) {
        this.$q.notify({
          message: 'Please enter a name for the wallet',
          color: 'warning'
        })
        return
      }

      if (this.g.newWalletType === 'lightning-shared' && !data.sharedWalletId) {
        this.$q.notify({
          message: 'Missing a shared wallet ID',
          color: 'warning'
        })
        return
      }
      try {
        await LNbits.api.createWallet(
          this.g.user.wallets[0],
          data.name,
          this.g.newWalletType,
          {
            shared_wallet_id: data.sharedWalletId
          }
        )
      } catch (e) {
        console.warn(e)
        LNbits.utils.notifyApiError(e)
      }
    }
  },
  created() {
    if (this.g.user?.extra?.wallet_invite_requests?.length) {
      this.walletTypes.push({
        label: `Lightning Wallet (Share Invite: ${this.g.user.extra.wallet_invite_requests.length})`,
        value: 'lightning-shared'
      })
    }
  }
})
