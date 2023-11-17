new Vue({
  el: '#vue',
  mixins: [windowMixin],
  data: function () {
    return {
      user: null,
      hasUsername: false,
      hasEmai: false
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
        this.$q.notify({
          type: 'positive',
          message: 'Account updated.'
        })
        console.log('### data', data)
      } catch (e) {
        LNbits.utils.notifyApiError(e)
      }
    }
  },
  created: async function () {
    try {
      const {data} = await LNbits.api.getAuthenticatedUser()
      this.user = data
      this.hasUsername = !!data.username
      this.hasEmail = !!data.email
      console.log('### user', this.user)
    } catch (e) {
      LNbits.utils.notifyApiError(e)
    }
  }
})
