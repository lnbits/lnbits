window.WalletsPageLogic = {
  mixins: [window.windowMixin],
  data() {
    return {
      user: null,
      tab: 'wallets'
    }
  },
  methods: {
    async updateAccount() {
      try {
        const {data} = await LNbits.api.request(
          'PUT',
          '/api/v1/auth/update',
          null,
          {
            user_id: this.user.id,
            username: this.user.username,
            email: this.user.email,
            extra: this.user.extra
          }
        )
        this.user = data
        this.hasUsername = !!data.username
        Quasar.Notify.create({
          type: 'positive',
          message: 'Account updated.'
        })
      } catch (e) {
        LNbits.utils.notifyApiError(e)
      }
    },

    async getApiACLs() {
      try {
        const {data} = await LNbits.api.request('GET', '/api/v1/auth/acl', null)
        this.apiAcl.data = data.access_control_list
      } catch (e) {
        LNbits.utils.notifyApiError(e)
      }
    },

    async addApiACL() {
      if (!this.apiAcl.newAclName) {
        this.$q.notify({
          type: 'warning',
          message: 'Name is required.'
        })
        return
      }

      try {
        const {data} = await LNbits.api.request(
          'PUT',
          '/api/v1/auth/acl',
          null,
          {
            id: this.apiAcl.newAclName,
            name: this.apiAcl.newAclName,
            password: this.apiAcl.password
          }
        )
        this.apiAcl.data = data.access_control_list
        const acl = this.apiAcl.data.find(
          t => t.name === this.apiAcl.newAclName
        )

        this.handleApiACLSelected(acl.id)
        this.apiAcl.showNewAclDialog = false
        this.$q.notify({
          type: 'positive',
          message: 'Access Control List created.'
        })
      } catch (e) {
        LNbits.utils.notifyApiError(e)
      } finally {
        this.apiAcl.name = ''
        this.apiAcl.password = ''
      }

      this.apiAcl.showNewAclDialog = false
    }
  },
  async created() {
    // await this.getApiACLs()
  }
}
