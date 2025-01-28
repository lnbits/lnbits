window.AccountPageLogic = {
  mixins: [window.windowMixin],
  data() {
    return {
      user: null,
      hasUsername: false,
      showUserId: false,
      reactionOptions: [
        'None',
        'confettiBothSides',
        'confettiFireworks',
        'confettiStars',
        'confettiTop'
      ],
      borderOptions: [
        'retro-border',
        'hard-border',
        'neon-border',
        'no-border'
      ],
      tab: 'user',
      credentialsData: {
        show: false,
        oldPassword: null,
        newPassword: null,
        newPasswordRepeat: null,
        username: null,
        pubkey: null
      },
      apiAcl: {
        showNewAclDialog: false,
        showPasswordDialog: false,
        showNewTokenDialog: false,
        data: [],
        passwordGuardedFunction: null,
        newAclName: '',
        newTokenName: '',
        password: '',
        apiToken: null,
        selectedTokenId: null,
        columns: [
          {
            name: 'Name',
            align: 'left',
            label: this.$t('Name'),
            field: 'Name',
            sortable: false
          },
          {
            name: 'path',
            align: 'left',
            label: this.$t('path'),
            field: 'path',
            sortable: false
          },
          {
            name: 'read',
            align: 'left',
            label: this.$t('read'),
            field: 'read',
            sortable: false
          },
          {
            name: 'write',
            align: 'left',
            label: this.$t('write'),
            field: 'write',
            sortable: false
          }
        ],
        pagination: {
          rowsPerPage: 100,
          page: 1
        }
      },
      selectedApiAcl: {
        id: null,
        name: null,
        endpoints: [],
        token_id_list: [],
        allRead: false,
        allWrite: false
      }
    }
  },
  methods: {
    activeLanguage(lang) {
      return window.i18n.global.locale === lang
    },
    changeLanguage(newValue) {
      window.i18n.global.locale = newValue
      this.$q.localStorage.set('lnbits.lang', newValue)
    },
    toggleGradient() {
      this.gradientSelection = !this.gradientChoice
      this.gradientChoice = this.gradientSelection
      this.$q.localStorage.set('lnbits.backgroundImage', 'none')
      this.applyGradient()
      if (!this.gradientChoice) {
        window.location.reload()
      }
    },
    reactionChoiceFunc() {
      this.$q.localStorage.set('lnbits.reactions', this.reactionSelection)
      this.reactionChoice = this.reactionSelection
    },
    bgimageChoiceFunc() {
      this.$q.localStorage.set('lnbits.backgroundImage', this.bgimageSelection)
      this.bgimageChoice = this.bgimageSelection
      this.applyBackgroundImage()
    },
    themeChoiceFunc(newValue) {
      this.changeTheme(newValue)
      this.setColors()
      if (this.gradientChoice) {
        this.applyGradient()
      }
      if (this.bgimageChoice) {
        this.applyBackgroundImage()
      }
      this.applyBorder()
    },
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
    disableUpdatePassword() {
      return (
        !this.credentialsData.newPassword ||
        !this.credentialsData.newPasswordRepeat ||
        this.credentialsData.newPassword !==
          this.credentialsData.newPasswordRepeat
      )
    },
    async updatePassword() {
      if (!this.credentialsData.username) {
        Quasar.Notify.create({
          type: 'warning',
          message: 'Please set a username.'
        })
        return
      }
      try {
        const {data} = await LNbits.api.request(
          'PUT',
          '/api/v1/auth/password',
          null,
          {
            user_id: this.user.id,
            username: this.credentialsData.username,
            password_old: this.credentialsData.oldPassword,
            password: this.credentialsData.newPassword,
            password_repeat: this.credentialsData.newPasswordRepeat
          }
        )
        this.user = data
        this.hasUsername = !!data.username
        this.credentialsData.show = false
        Quasar.Notify.create({
          type: 'positive',
          message: 'Password updated.'
        })
      } catch (e) {
        LNbits.utils.notifyApiError(e)
      }
    },
    async updatePubkey() {
      try {
        const {data} = await LNbits.api.request(
          'PUT',
          '/api/v1/auth/pubkey',
          null,
          {
            user_id: this.user.id,
            pubkey: this.credentialsData.pubkey
          }
        )
        this.user = data
        this.hasUsername = !!data.username
        this.credentialsData.show = false
        this.$q.notify({
          type: 'positive',
          message: 'Public key updated.'
        })
      } catch (e) {
        LNbits.utils.notifyApiError(e)
      }
    },
    showUpdateCredentials() {
      this.credentialsData = {
        show: true,
        oldPassword: null,
        username: this.user.username,
        pubkey: this.user.pubkey,
        newPassword: null,
        newPasswordRepeat: null
      }
    },
    newApiAclDialog() {
      this.apiAcl.newAclName = null
      this.apiAcl.showNewAclDialog = true
    },
    newTokenAclDialog() {
      this.apiAcl.newTokenName = null
      this.apiAcl.newTokenExpiry = null
      this.apiAcl.showNewTokenDialog = true
    },
    handleApiACLSelected(aclId) {
      this.selectedApiAcl = {
        id: null,
        name: null,
        endpoints: [],
        token_id_list: []
      }
      this.apiAcl.selectedTokenId = null
      if (!aclId) {
        return
      }
      setTimeout(() => {
        const selectedApiAcl = this.apiAcl.data.find(t => t.id === aclId)
        if (!this.selectedApiAcl) {
          return
        }
        this.selectedApiAcl = {...selectedApiAcl}
        this.selectedApiAcl.allRead = this.selectedApiAcl.endpoints.every(
          e => e.read
        )
        this.selectedApiAcl.allWrite = this.selectedApiAcl.endpoints.every(
          e => e.write
        )
      })
    },
    handleAllEndpointsReadAccess() {
      this.selectedApiAcl.endpoints.forEach(
        e => (e.read = this.selectedApiAcl.allRead)
      )
    },
    handleAllEndpointsWriteAccess() {
      this.selectedApiAcl.endpoints.forEach(
        e => (e.write = this.selectedApiAcl.allWrite)
      )
    },
    async getApiACLs() {
      try {
        const {data} = await LNbits.api.request('GET', '/api/v1/auth/acl', null)
        this.apiAcl.data = data.access_control_list
      } catch (e) {
        LNbits.utils.notifyApiError(e)
      }
    },
    askPasswordAndRunFunction(func) {
      this.apiAcl.passwordGuardedFunction = func
      this.apiAcl.showPasswordDialog = true
    },
    runPasswordGuardedFunction() {
      this.apiAcl.showPasswordDialog = false
      const func = this.apiAcl.passwordGuardedFunction
      if (func) {
        this[func]()
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
    },

    async updateApiACLs() {
      try {
        const {data} = await LNbits.api.request(
          'PUT',
          '/api/v1/auth/acl',
          null,
          {
            id: this.user.id,
            password: this.apiAcl.password,
            ...this.selectedApiAcl
          }
        )
        this.apiAcl.data = data.access_control_list
      } catch (e) {
        LNbits.utils.notifyApiError(e)
      } finally {
        this.apiAcl.password = ''
      }
    },
    async deleteApiACL() {
      if (!this.selectedApiAcl.id) {
        return
      }
      try {
        await LNbits.api.request('DELETE', '/api/v1/auth/acl', null, {
          id: this.selectedApiAcl.id,
          password: this.apiAcl.password
        })
        this.$q.notify({
          type: 'positive',
          message: 'Access Control List deleted.'
        })
      } catch (e) {
        LNbits.utils.notifyApiError(e)
      } finally {
        this.apiAcl.password = ''
      }
      this.apiAcl.data = this.apiAcl.data.filter(
        t => t.id !== this.selectedApiAcl.id
      )
      this.handleApiACLSelected(this.apiAcl.data[0]?.id)
    },
    async generateApiToken() {
      if (!this.selectedApiAcl.id) {
        return
      }
      const expirationTimeMilliseconds =
        new Date(this.apiAcl.newTokenExpiry) - new Date()
      try {
        const {data} = await LNbits.api.request(
          'POST',
          '/api/v1/auth/acl/token',
          null,
          {
            acl_id: this.selectedApiAcl.id,
            token_name: this.apiAcl.newTokenName,
            password: this.apiAcl.password,
            expiration_time_minutes: Math.trunc(
              expirationTimeMilliseconds / 60000
            )
          }
        )

        this.apiAcl.apiToken = data.api_token
        this.apiAcl.selectedTokenId = data.id
        Quasar.Notify.create({
          type: 'positive',
          message: 'Token Generated.'
        })

        await this.getApiACLs()
        this.handleApiACLSelected(this.selectedApiAcl.id)
        this.apiAcl.showNewTokenDialog = false
      } catch (e) {
        LNbits.utils.notifyApiError(e)
      } finally {
        this.apiAcl.password = ''
      }
    },
    async deleteToken() {
      if (!this.apiAcl.selectedTokenId) {
        return
      }
      try {
        await LNbits.api.request('DELETE', '/api/v1/auth/acl/token', null, {
          id: this.apiAcl.selectedTokenId,
          acl_id: this.selectedApiAcl.id,
          password: this.apiAcl.password
        })
        this.$q.notify({
          type: 'positive',
          message: 'Token deleted.'
        })

        this.selectedApiAcl.token_id_list =
          this.selectedApiAcl.token_id_list.filter(
            t => t.id !== this.apiAcl.selectedTokenId
          )
        this.apiAcl.selectedTokenId = null
      } catch (e) {
        LNbits.utils.notifyApiError(e)
      } finally {
        this.apiAcl.password = ''
      }
    }
  },
  async created() {
    this.borderSelection = this.borderChoice
    this.reactionSelection = this.reactionChoice
    this.bgimageSelection = this.bgimageChoice
    this.themeSelection = this.themeChoice
    try {
      const {data} = await LNbits.api.getAuthenticatedUser()
      this.user = data
      this.hasUsername = !!data.username
      if (!this.user.extra) this.user.extra = {}
    } catch (e) {
      LNbits.utils.notifyApiError(e)
    }
    const hash = window.location.hash.replace('#', '')
    if (hash) {
      this.tab = hash
    }
    await this.getApiACLs()
  }
}
