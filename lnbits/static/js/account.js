new Vue({
  el: '#vue',
  mixins: [windowMixin],
  data: function () {
    return {
      user: null,
      hasUsername: false,
      passwordData: {
        show: false,
        oldPassword: null,
        newPassword: null,
        newPasswordRepeat: null
      }
    }
  },
  methods: {
    updateAccount: async function () {
      try {
        const {data} = await LNbits.api.request(
          'PUT',
          '/api/v1/auth/update',
          null,
          {
            user_id: this.user.id,
            username: this.user.username,
            email: this.user.email,
            config: this.user.config
          }
        )
        this.user = data
        this.$q.notify({
          type: 'positive',
          message: 'Account updated.'
        })
      } catch (e) {
        LNbits.utils.notifyApiError(e)
      }
    },
    updatePassword: async function () {
      try {
        const {data} = await LNbits.api.request(
          'PUT',
          '/api/v1/auth/password',
          null,
          {
            user_id: this.user.id,
            password_old: this.passwordData.oldPassword,
            password: this.passwordData.newPassword,
            password_repeat: this.passwordData.newPasswordRepeat
          }
        )
        this.user = data
        this.passwordData.show = false
        this.$q.notify({
          type: 'positive',
          message: 'Password updated.'
        })
      } catch (e) {
        LNbits.utils.notifyApiError(e)
      }
    },
    showChangePassword: function () {
      this.passwordData = {
        show: true,
        oldPassword: null,
        newPassword: null,
        newPasswordRepeat: null
      }
    }
  },
  created: async function () {
    try {
      const {data} = await LNbits.api.getAuthenticatedUser()
      this.user = data
      this.hasUsername = !!data.username
      if (!this.user.config) this.user.config = {}
    } catch (e) {
      LNbits.utils.notifyApiError(e)
    }
  }
})
