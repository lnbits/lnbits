window.PageAdmin = {
  template: '#page-admin',
  mixins: [windowMixin],
  data() {
    return {
      tab: 'funding',
      settings: {},
      formData: {
        lnbits_exchange_rate_providers: [],
        lnbits_audit_exclude_paths: [],
        lnbits_audit_include_paths: [],
        lnbits_audit_http_response_codes: []
      },
      isSuperUser: false,
      needsRestart: false
    }
  },
  watch: {
    tab(tab) {
      this.$router.push(`/admin#${tab}`)
    },
    $route(to) {
      if (to.hash.length > 1) {
        this.tab = to.hash.replace('#', '')
      }
    }
  },
  async created() {
    if (this.$route.hash.length > 1) {
      this.tab = this.$route.hash.replace('#', '')
    }
    await this.getSettings()
  },
  computed: {
    checkChanges() {
      return !_.isEqual(this.settings, this.formData)
    }
  },
  methods: {
    getDefaultSetting(fieldName) {
      LNbits.api.getDefaultSetting(fieldName).then(response => {
        this.formData[fieldName] = response.data.default_value
      })
    },
    restartServer() {
      LNbits.api
        .request('GET', '/admin/api/v1/restart/')
        .then(response => {
          this.$q.notify({
            type: 'positive',
            message: 'Success! Restarted Server',
            icon: null
          })
          this.needsRestart = false
        })
        .catch(LNbits.utils.notifyApiError)
    },
    async getSettings() {
      await LNbits.api
        .request(
          'GET',
          '/admin/api/v1/settings',
          this.g.user.wallets[0].adminkey
        )
        .then(response => {
          this.isSuperUser = response.data.is_super_user || false
          this.settings = response.data
          this.formData = {...this.settings}
        })
        .catch(LNbits.utils.notifyApiError)
    },
    updateSettings() {
      const data = _.omit(this.formData, [
        'is_super_user',
        'lnbits_allowed_funding_sources',
        'touch'
      ])
      LNbits.api
        .request(
          'PUT',
          '/admin/api/v1/settings',
          this.g.user.wallets[0].adminkey,
          data
        )
        .then(response => {
          this.needsRestart =
            this.settings.lnbits_backend_wallet_class !==
            this.formData.lnbits_backend_wallet_class
          this.settings = this.formData
          this.formData = _.clone(this.settings)
          Quasar.Notify.create({
            type: 'positive',
            message: `Success! Settings changed! ${
              this.needsRestart ? 'Restart required!' : ''
            }`,
            icon: null
          })
        })
        .catch(LNbits.utils.notifyApiError)
    },
    deleteSettings() {
      LNbits.utils
        .confirmDialog('Are you sure you want to restore settings to default?')
        .onOk(() => {
          LNbits.api
            .request('DELETE', '/admin/api/v1/settings')
            .then(response => {
              Quasar.Notify.create({
                type: 'positive',
                message:
                  'Success! Restored settings to defaults. Restarting...',
                icon: null
              })
              this.$q.localStorage.clear()
            })
            .catch(LNbits.utils.notifyApiError)
        })
    },
    downloadBackup() {
      window.open('/admin/api/v1/backup', '_blank')
    }
  }
}
