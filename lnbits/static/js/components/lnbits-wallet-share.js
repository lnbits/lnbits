window.app.component('lnbits-wallet-share', {
  template: '#lnbits-wallet-share',
  mixins: [window.windowMixin],
  computed: {
    walletApprovedShares() {
      return this.g.wallet.extra.shared_with.filter(
        s => s.status === 'approved'
      )
    },
    walletPendingRequests() {
      return this.g.wallet.extra.shared_with.filter(
        s => s.status === 'request_access'
      )
    },
    walletPendingInvites() {
      return this.g.wallet.extra.shared_with.filter(
        s => s.status === 'invite_sent'
      )
    }
  },
  data() {
    return {
      permissionOptions: [
        {label: 'View', value: 'view-payments'},
        {label: 'Receive', value: 'receive-payments'},
        {label: 'Send', value: 'send-payments'}
      ],
      walletShareInvite: {
        unsername: '',
        permissions: []
      }
    }
  },
  methods: {
    async updateSharePermissions(permission) {
      try {
        const {data} = await LNbits.api.request(
          'PUT',
          '/api/v1/wallet/share',
          this.g.wallet.adminkey,
          permission
        )
        Object.assign(permission, data)
        Quasar.Notify.create({
          message: 'Wallet permission updated.',
          type: 'positive'
        })
      } catch (err) {
        LNbits.utils.notifyApiError(err)
      }
    },
    async inviteUserToWallet() {
      try {
        const {data} = await LNbits.api.request(
          'PUT',
          '/api/v1/wallet/share/invite',
          this.g.wallet.adminkey,
          {
            ...this.walletShareInvite,
            status: 'invite_sent',
            wallet_id: this.g.wallet.id
          }
        )

        this.g.wallet.extra.shared_with.push(data)
        this.walletShareInvite = {username: '', permissions: []}
        Quasar.Notify.create({
          message: 'User invited to wallet.',
          type: 'positive'
        })
      } catch (err) {
        LNbits.utils.notifyApiError(err)
      }
    },
    deleteSharePermission(permission) {
      LNbits.utils
        .confirmDialog('Are you sure you want to remove this share permission?')
        .onOk(async () => {
          try {
            await LNbits.api.request(
              'DELETE',
              `/api/v1/wallet/share/${permission.request_id}`,
              this.g.wallet.adminkey
            )
            this.g.wallet.extra.shared_with =
              this.g.wallet.extra.shared_with.filter(
                value => value.wallet_id !== permission.wallet_id
              )
            Quasar.Notify.create({
              message: 'Wallet permission deleted.',
              type: 'positive'
            })
          } catch (err) {
            LNbits.utils.notifyApiError(err)
          }
        })
    }
  }
})
