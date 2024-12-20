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
      borderOptions: ['retro-border', 'hard-border', 'no-border'],
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
        data: [],
        newAclName: '',
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
    toggleDarkMode() {
      this.$q.dark.toggle()
      this.$q.localStorage.set('lnbits.darkMode', this.$q.dark.isActive)
      if (!this.$q.dark.isActive && this.gradientChoice) {
        this.toggleGradient()
      }
    },
    toggleGradient() {
      this.gradientChoice = !this.gradientChoice
      this.applyGradient()
      if (!this.gradientChoice) {
        window.location.reload()
      }
    },
    reactionChoiceFunc() {
      this.$q.localStorage.set('lnbits.reactions', this.reactionChoice)
    },
    changeColor(newValue) {
      document.body.setAttribute('data-theme', newValue)
      this.$q.localStorage.set('lnbits.theme', newValue)
      this.setColors()
      if (this.$q.localStorage.getItem('lnbits.gradientBg')) {
        this.applyGradient()
      }
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
      console.log('### this.apiAcl.data', this.apiAcl.data)
      this.apiAcl.newAclName = null
      this.apiAcl.showNewAclDialog = true
    },
    handleApiACLSelected(aclId) {
      console.log('### handleApiACLSelected', aclId)
      this.selectedApiAcl = {id: null, name: null, endpoints: []}
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
    async addApiACL() {
      console.log('### addApiACL')
      const name = this.apiAcl.newAclName
      if (!name) {
        return
      }
      if (this.apiAcl.data.find(t => t.name === name)) {
        this.apiAcl.showNewAclDialog = false
        return
      }
      try {
        const {data} = await LNbits.api.request(
          'POST',
          '/api/v1/auth/acl',
          null,
          {
            id: name,
            name: name,
            endpoints: []
          }
        )
        console.log('### addApiACL', data)
        this.apiAcl.data.push(data)

        this.handleApiACLSelected(data.id)
      } catch (e) {
        LNbits.utils.notifyApiError(e)
      }

      this.apiAcl.showNewAclDialog = false
    },
    async getApiACLs() {
      try {
        const {data} = await LNbits.api.request(
          'GET',
          '/api/v1/auth/acl',
          null
        )
        console.log('### getApiACLs', data)
        this.apiAcl.data = data.access_control_list
      } catch (e) {
        LNbits.utils.notifyApiError(e)
      }
    },
    async updateApiACLs() {
      try {
        console.log('### his.apiAcl.data', this.apiAcl.data)
        const {data} = await LNbits.api.request(
          'PUT',
          '/api/v1/auth/acl',
          null,
          {
            id: this.user.id,
            access_control_list: this.apiAcl.data
          }
        )
        this.apiAcl.data = data.access_control_list
        console.log('### data', data)
      } catch (e) {
        LNbits.utils.notifyApiError(e)
      }
    },
    deleteApiACL() {
      if (!this.selectedApiAcl.id) {
        return
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
      try {
        const {data} = await LNbits.api.request(
          'POST',
          '/api/v1/auth/acl/token',
          null,
          {
            acl_id: this.selectedApiAcl.id,
            password: 'xxx',
            expiration_time_minutes: 30
          }
        )
        this.selectedApiAcl.apiToken = data.api_token
        console.log('### data', data)
      } catch (e) {
        LNbits.utils.notifyApiError(e)
      }
    }
  },
  async created() {
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
