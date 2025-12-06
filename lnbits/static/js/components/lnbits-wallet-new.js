window.app.component('lnbits-wallet-new', {
  template: '#lnbits-wallet-new',
  mixins: [window.windowMixin],
  data() {
    return {
      walletTypes: [{label: 'Lightning Wallet', value: 'lightning'}],
      wallet: {name: '', sharedWalletId: ''},
      showNewWalletDialog: false
    }
  },
  watch: {
    'g.newWalletType'(val) {
      if (val === null) return
      this.showNewWalletDialog = true
    },
    showNewWalletDialog(val) {
      if (val === true) return
      this.reset()
    }
  },
  computed: {
    isLightning() {
      return this.g.newWalletType === 'lightning'
    },
    isLightningShared() {
      return this.g.newWalletType === 'lightning-shared'
    },
    inviteWalletOptions() {
      return (this.g.user?.extra?.wallet_invite_requests || []).map(i => ({
        label: `${i.to_wallet_name} (from ${i.from_user_name})`,
        value: i.to_wallet_id
      }))
    }
  },
  methods: {
    reset() {
      this.showNewWalletDialog = false
      this.g.newWalletType = null
      this.wallet = {name: '', sharedWalletId: ''}
    },
    async submitRejectWalletInvitation() {
      try {
        const inviteRequests = this.g.user.extra.wallet_invite_requests || []
        const invite = inviteRequests.find(
          invite => invite.to_wallet_id === this.wallet.sharedWalletId
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
    submitAddWallet() {
      const data = this.wallet
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
      LNbits.api
        .createWallet(data.name, this.g.newWalletType, {
          shared_wallet_id: data.sharedWalletId
        })
        .then(res => {
          this.$q.notify({
            message: 'Wallet created successfully',
            color: 'positive'
          })
          this.reset()
          this.g.user.wallets.push(LNbits.map.wallet(res.data))
          this.g.lastWalletId = res.data.id
          this.$router.push(`/wallet/${res.data.id}`)
        })
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
