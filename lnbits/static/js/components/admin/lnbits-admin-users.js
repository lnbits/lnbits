window.app.component('lnbits-admin-users', {
  props: ['form-data', 'is-super-user'],
  template: '#lnbits-admin-users',
  data() {
    return {
      formAddUser: '',
      formAddAdmin: '',
      formAddActivationCode: '',
      showReusableActivationCode: false,
      resettingWalletKeys: false
    }
  },
  methods: {
    resetWalletKeys() {
      if (!this.isSuperUser || this.resettingWalletKeys) return
      LNbits.utils
        .confirmDialog(
          'Reset the admin and invoice keys for ALL wallets, including deleted wallets? ' +
            'Existing keys will stop working. Integrations must be updated with the new keys, ' +
            'and open wallet pages will need to be reloaded.'
        )
        .onOk(async () => {
          if (this.resettingWalletKeys) return
          this.resettingWalletKeys = true
          try {
            const {data} = await LNbits.api.request(
              'POST',
              '/admin/api/v1/wallets/reset-keys'
            )
            Quasar.Notify.create({
              type: 'positive',
              message: `Keys reset for ${data.wallets_updated} wallets.`
            })
            try {
              const response = await LNbits.api.getAuthUser()
              this.g.user = LNbits.map.user(response.data)
              if (this.g.wallet) {
                this.g.wallet = this.g.user.wallets.find(
                  wallet => wallet.id === this.g.wallet.id
                )
              }
            } catch {
              Quasar.Notify.create({
                type: 'warning',
                message:
                  'Wallet keys were reset. Reload this page to refresh your wallets.'
              })
            }
          } catch (error) {
            LNbits.utils.notifyApiError(error)
          } finally {
            this.resettingWalletKeys = false
          }
        })
    },
    addAllowedUser() {
      let addUser = this.formAddUser
      let allowed_users = this.formData.lnbits_allowed_users
      if (addUser && addUser.length && !allowed_users.includes(addUser)) {
        this.formData.lnbits_allowed_users = [...allowed_users, addUser]
        this.formAddUser = ''
      }
    },
    removeAllowedUser(user) {
      let allowed_users = this.formData.lnbits_allowed_users
      this.formData.lnbits_allowed_users = allowed_users.filter(u => u !== user)
    },
    addAdminUser() {
      let addUser = this.formAddAdmin
      let admin_users = this.formData.lnbits_admin_users
      if (addUser && addUser.length && !admin_users.includes(addUser)) {
        this.formData.lnbits_admin_users = [...admin_users, addUser]
        this.formAddAdmin = ''
      }
    },
    removeAdminUser(user) {
      let admin_users = this.formData.lnbits_admin_users
      this.formData.lnbits_admin_users = admin_users.filter(u => u !== user)
    },
    addOneTimeActivationCode() {
      const code = this.formAddActivationCode
      const activationCodes =
        this.formData.lnbits_register_one_time_activation_codes
      if (code?.length && !activationCodes.includes(code)) {
        this.formData.lnbits_register_one_time_activation_codes = [
          ...activationCodes,
          code
        ]
        this.formAddActivationCode = ''
      }
    },
    removeOneTimeActivationCode(code) {
      const codes = this.formData.lnbits_register_one_time_activation_codes
      this.formData.lnbits_register_one_time_activation_codes = codes.filter(
        u => u !== code
      )
    }
  }
})
