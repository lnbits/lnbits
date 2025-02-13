window.AdminPageLogic = {
  mixins: [windowMixin],
  data() {
    return {
      settings: {},
      logs: [],
      serverlogEnabled: false,
      lnbits_theme_options: [
        'classic',
        'bitcoin',
        'flamingo',
        'cyber',
        'freedom',
        'mint',
        'autumn',
        'monochrome',
        'salvador'
      ],
      reactionOptions: [
        'none',
        'confettiBothSides',
        'confettiFireworks',
        'confettiStars',
        'confettiTop'
      ],
      globalBorderOptions: [
        'retro-border',
        'hard-border',
        'neon-border',
        'no-border'
      ],
      auditData: {},
      statusData: {},
      statusDataTable: {
        columns: [
          {
            name: 'date',
            align: 'left',
            label: this.$t('date'),
            field: 'date'
          },
          {
            name: 'message',
            align: 'left',
            label: this.$t('memo'),
            field: 'message'
          }
        ]
      },
      formData: {
        lnbits_exchange_rate_providers: []
      },
      chartReady: false,
      formAddAdmin: '',
      formAddUser: '',
      formAddExtensionsManifest: '',
      nostrNotificationIdentifier: '',
      formAllowedIPs: '',
      formCallbackUrlRule: '',
      formBlockedIPs: '',
      nostrAcceptedUrl: '',
      formAddIncludePath: '',
      formAddExcludePath: '',
      formAddIncludeResponseCode: '',
      isSuperUser: false,
      wallet: {},
      cancel: {},
      colors: [
        'primary',
        'secondary',
        'accent',
        'positive',
        'negative',
        'info',
        'warning',
        'red',
        'yellow',
        'orange'
      ],
      tab: 'funding',
      needsRestart: false,
      exchangesTable: {
        columns: [
          {
            name: 'name',
            align: 'left',
            label: 'Exchange Name',
            field: 'name',
            sortable: true
          },
          {
            name: 'api_url',
            align: 'left',
            label: 'URL',
            field: 'api_url',
            sortable: false
          },
          {
            name: 'path',
            align: 'left',
            label: 'JSON Path',
            field: 'path',
            sortable: false
          },

          {
            name: 'exclude_to',
            align: 'left',
            label: 'Exclude Currencies',
            field: 'exclude_to',
            sortable: false
          },
          {
            name: 'ticker_conversion',
            align: 'left',
            label: 'Ticker Conversion',
            field: 'ticker_conversion',
            sortable: false
          }
        ],
        pagination: {
          sortBy: 'name',
          rowsPerPage: 100,
          page: 1,
          rowsNumber: 100
        },
        search: null,
        hideEmpty: true
      },
      exchangeData: {
        selectedProvider: null,
        showTickerConversion: false,
        convertFromTicker: null,
        convertToTicker: null
      }
    }
  },
  async created() {
    await this.getSettings()
    await this.getAudit()
    this.balance = +'{{ balance|safe }}'
    const hash = window.location.hash.replace('#', '')
    if (hash === 'exchange_providers') {
      this.showExchangeProvidersTab(hash)
    }
    if (hash) {
      this.tab = hash
    }
  },
  computed: {
    lnbitsVersion() {
      return LNBITS_VERSION
    },
    checkChanges() {
      return !_.isEqual(this.settings, this.formData)
    },
    updateAvailable() {
      return LNBITS_VERSION !== this.statusData.version
    }
  },
  methods: {
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
    addIncludePath() {
      if (!this.formAddIncludePath) {
        return
      }
      const paths = this.formData.lnbits_audit_include_paths
      if (!paths.includes(this.formAddIncludePath)) {
        this.formData.lnbits_audit_include_paths = [
          ...paths,
          this.formAddIncludePath
        ]
      }
      this.formAddIncludePath = ''
    },
    removeIncludePath(path) {
      this.formData.lnbits_audit_include_paths =
        this.formData.lnbits_audit_include_paths.filter(p => p !== path)
    },
    addExcludePath() {
      if (!this.formAddExcludePath) {
        return
      }
      const paths = this.formData.lnbits_audit_exclude_paths
      if (!paths.includes(this.formAddExcludePath)) {
        this.formData.lnbits_audit_exclude_paths = [
          ...paths,
          this.formAddExcludePath
        ]
      }
      this.formAddExcludePath = ''
    },

    removeExcludePath(path) {
      this.formData.lnbits_audit_exclude_paths =
        this.formData.lnbits_audit_exclude_paths.filter(p => p !== path)
    },
    addIncludeResponseCode() {
      if (!this.formAddIncludeResponseCode) {
        return
      }
      const codes = this.formData.lnbits_audit_http_response_codes
      if (!codes.includes(this.formAddIncludeResponseCode)) {
        this.formData.lnbits_audit_http_response_codes = [
          ...codes,
          this.formAddIncludeResponseCode
        ]
      }
      this.formAddIncludeResponseCode = ''
    },
    removeIncludeResponseCode(code) {
      this.formData.lnbits_audit_http_response_codes =
        this.formData.lnbits_audit_http_response_codes.filter(c => c !== code)
    },
    addExtensionsManifest() {
      const addManifest = this.formAddExtensionsManifest.trim()
      const manifests = this.formData.lnbits_extensions_manifests
      if (
        addManifest &&
        addManifest.length &&
        !manifests.includes(addManifest)
      ) {
        this.formData.lnbits_extensions_manifests = [...manifests, addManifest]
        this.formAddExtensionsManifest = ''
      }
    },
    removeExtensionsManifest(manifest) {
      const manifests = this.formData.lnbits_extensions_manifests
      this.formData.lnbits_extensions_manifests = manifests.filter(
        m => m !== manifest
      )
    },
    addNostrNotificationIdentifier() {
      const identifer = this.nostrNotificationIdentifier.trim()
      const identifiers = this.formData.lnbits_nostr_notifications_identifiers
      if (identifer && identifer.length && !identifiers.includes(identifer)) {
        this.formData.lnbits_nostr_notifications_identifiers = [
          ...identifiers,
          identifer
        ]
        this.nostrNotificationIdentifier = ''
      }
    },
    removeNostrNotificationIdentifier(identifer) {
      const identifiers = this.formData.lnbits_nostr_notifications_identifiers
      this.formData.lnbits_nostr_notifications_identifiers = identifiers.filter(
        m => m !== identifer
      )
    },
    async toggleServerLog() {
      this.serverlogEnabled = !this.serverlogEnabled
      if (this.serverlogEnabled) {
        const wsProto = location.protocol !== 'http:' ? 'wss://' : 'ws://'
        const digestHex = await LNbits.utils.digestMessage(this.g.user.id)
        const localUrl =
          wsProto +
          document.domain +
          ':' +
          location.port +
          '/api/v1/ws/' +
          digestHex
        this.ws = new WebSocket(localUrl)
        this.ws.addEventListener('message', async ({data}) => {
          this.logs.push(data.toString())
          const scrollArea = this.$refs.logScroll
          if (scrollArea) {
            const scrollTarget = scrollArea.getScrollTarget()
            const duration = 0
            scrollArea.setScrollPosition(scrollTarget.scrollHeight, duration)
          }
        })
      } else {
        this.ws.close()
      }
    },
    addAllowedIPs() {
      const allowedIPs = this.formAllowedIPs.trim()
      const allowed_ips = this.formData.lnbits_allowed_ips
      if (
        allowedIPs &&
        allowedIPs.length &&
        !allowed_ips.includes(allowedIPs)
      ) {
        this.formData.lnbits_allowed_ips = [...allowed_ips, allowedIPs]
        this.formAllowedIPs = ''
      }
    },
    removeAllowedIPs(allowed_ip) {
      const allowed_ips = this.formData.lnbits_allowed_ips
      this.formData.lnbits_allowed_ips = allowed_ips.filter(
        a => a !== allowed_ip
      )
    },
    addBlockedIPs() {
      const blockedIPs = this.formBlockedIPs.trim()
      const blocked_ips = this.formData.lnbits_blocked_ips
      if (
        blockedIPs &&
        blockedIPs.length &&
        !blocked_ips.includes(blockedIPs)
      ) {
        this.formData.lnbits_blocked_ips = [...blocked_ips, blockedIPs]
        this.formBlockedIPs = ''
      }
    },
    removeBlockedIPs(blocked_ip) {
      const blocked_ips = this.formData.lnbits_blocked_ips
      this.formData.lnbits_blocked_ips = blocked_ips.filter(
        b => b !== blocked_ip
      )
    },
    addCallbackUrlRule() {
      const allowedCallback = this.formCallbackUrlRule.trim()
      const allowedCallbacks = this.formData.lnbits_callback_url_rules
      if (
        allowedCallback &&
        allowedCallback.length &&
        !allowedCallbacks.includes(allowedCallback)
      ) {
        this.formData.lnbits_callback_url_rules = [
          ...allowedCallbacks,
          allowedCallback
        ]
        this.formCallbackUrlRule = ''
      }
    },
    removeCallbackUrlRule(allowedCallback) {
      const allowedCallbacks = this.formData.lnbits_callback_url_rules
      this.formData.lnbits_callback_url_rules = allowedCallbacks.filter(
        a => a !== allowedCallback
      )
    },

    addNostrUrl() {
      const url = this.nostrAcceptedUrl.trim()
      this.removeNostrUrl(url)
      this.formData.nostr_absolute_request_urls.push(url)
      this.nostrAcceptedUrl = ''
    },
    removeNostrUrl(url) {
      this.formData.nostr_absolute_request_urls =
        this.formData.nostr_absolute_request_urls.filter(b => b !== url)
    },
    addExchangeProvider() {
      this.formData.lnbits_exchange_rate_providers = [
        {
          name: '',
          api_url: '',
          path: '',
          exclude_to: []
        },
        ...this.formData.lnbits_exchange_rate_providers
      ]
    },
    removeExchangeProvider(provider) {
      this.formData.lnbits_exchange_rate_providers =
        this.formData.lnbits_exchange_rate_providers.filter(p => p !== provider)
    },
    removeExchangeTickerConversion(provider, ticker) {
      provider.ticker_conversion = provider.ticker_conversion.filter(
        t => t !== ticker
      )
      this.touchSettings()
    },
    addExchangeTickerConversion() {
      if (!this.exchangeData.selectedProvider) {
        return
      }
      this.exchangeData.selectedProvider.ticker_conversion.push(
        `${this.exchangeData.convertFromTicker}:${this.exchangeData.convertToTicker}`
      )
      this.touchSettings()
      this.exchangeData.showTickerConversion = false
    },
    showTickerConversionDialog(provider) {
      this.exchangeData.convertFromTicker = null
      this.exchangeData.convertToTicker = null
      this.exchangeData.selectedProvider = provider
      this.exchangeData.showTickerConversion = true
    },

    getDefaultSetting(fieldName) {
      LNbits.api
        .request(
          'GET',
          `/admin/api/v1/settings/default?field_name=${fieldName}`
        )
        .then(response => {
          this.formData[fieldName] = response.data.default_value
        })
        .catch(function (error) {
          LNbits.utils.notifyApiError(error)
        })
    },
    restartServer() {
      LNbits.api
        .request('GET', '/admin/api/v1/restart/')
        .then(response => {
          Quasar.Notify.create({
            type: 'positive',
            message: 'Success! Restarted Server',
            icon: null
          })
          this.needsRestart = false
        })
        .catch(LNbits.utils.notifyApiError)
    },
    formatDate(date) {
      return moment(date * 1000).fromNow()
    },

    getAudit() {
      LNbits.api
        .request('GET', '/admin/api/v1/audit', this.g.user.wallets[0].adminkey)
        .then(response => {
          this.auditData = response.data
        })
        .catch(LNbits.utils.notifyApiError)
    },
    getExchangeRateHistory() {
      LNbits.api
        .request('GET', '/api/v1/rate/history', this.g.user.wallets[0].inkey)
        .then(response => {
          this.initExchangeChart(response.data)
        })
        .catch(function (error) {
          LNbits.utils.notifyApiError(error)
        })
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
                  'Success! Restored settings to defaults, restart required!',
                icon: null
              })
              this.needsRestart = true
            })
            .catch(LNbits.utils.notifyApiError)
        })
    },
    downloadBackup() {
      window.open('/admin/api/v1/backup', '_blank')
    },
    showExchangeProvidersTab(tabName) {
      if (tabName === 'exchange_providers') {
        this.getExchangeRateHistory()
      }
    },
    touchSettings() {
      this.formData.touch = null
    },
    initExchangeChart(data) {
      const xValues = data.map(d =>
        Quasar.date.formatDate(new Date(d.timestamp * 1000), 'HH:mm')
      )
      const exchanges = [
        ...this.formData.lnbits_exchange_rate_providers,
        {name: 'LNbits'}
      ]
      const datasets = exchanges.map(exchange => ({
        label: exchange.name,
        data: data.map(d => d.rates[exchange.name]),
        pointStyle: true,
        borderWidth: exchange.name === 'LNbits' ? 4 : 1,
        tension: 0.4
      }))
      this.exchangeRatesChart = new Chart(
        this.$refs.exchangeRatesChart.getContext('2d'),
        {
          type: 'line',
          options: {
            plugins: {
              legend: {
                display: false
              }
            }
          },
          data: {
            labels: xValues,
            datasets
          }
        }
      )
    }
  }
}
