window.PageAdmin = {
  template: '#page-admin',
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
      needsRestart: false,
      isSaving: false,
      settingsLoaded: false,
      settingsSearch: ''
    }
  },
  watch: {
    tab(tab) {
      if (
        ['wasm-runtime', 'wasm-limit-config'].includes(tab) &&
        this.$route.path.startsWith('/admin/extensions/wasm')
      ) {
        return
      }
      const target = this.adminRouteForTab(tab)
      if (this.$route.fullPath !== target) {
        this.$router.push(target)
      }
    },
    $route(to) {
      const tab = this.adminTabFromRoute(to)
      if (this.tab !== tab) {
        this.tab = tab
      }
    }
  },
  async created() {
    this.tab = this.adminTabFromRoute(this.$route)
    await this.getSettings()
  },
  computed: {
    checkChanges() {
      return this.settingsLoaded && !_.isEqual(this.settings, this.formData)
    },
    settingsNavigation() {
      return [
        {
          label: 'settings_money',
          items: [
            {
              value: 'funding',
              label: 'funding',
              icon: 'account_balance_wallet'
            },
            {value: 'server', label: 'payments', icon: 'price_change'},
            {
              value: 'exchange_providers',
              label: 'exchanges',
              icon: 'show_chart'
            },
            {
              value: 'fiat_providers',
              label: 'fiat_providers',
              icon: 'credit_score'
            }
          ]
        },
        {
          label: 'settings_access',
          items: [
            {value: 'security', label: 'security', icon: 'security'},
            {value: 'users', label: 'users', icon: 'group'}
          ]
        },
        {
          label: 'settings_system',
          items: [
            {value: 'extensions', label: 'extensions', icon: 'extension'},
            {
              value: 'notifications',
              label: 'notifications',
              icon: 'notifications'
            },
            {
              value: 'audit',
              label: 'api_watch',
              icon: 'playlist_add_check_circle'
            }
          ]
        },
        {
          label: 'settings_appearance',
          items: [
            {value: 'assets-config', label: 'assets', icon: 'perm_media'},
            {
              value: 'site_customisation',
              label: 'site_customisation',
              icon: 'palette'
            },
            {
              value: 'blockexplorer',
              label: 'block_explorer',
              icon: 'travel_explore'
            }
          ]
        }
      ]
    },
    settingsNavigationItems() {
      return this.settingsNavigation.flatMap(group =>
        group.items.map(item => ({
          ...item,
          label: this.$t(item.label),
          group: this.$t(group.label)
        }))
      )
    },
    settingsSearchIndex() {
      const sections = {
        funding: [
          this.$t('wallets_management'),
          this.$t('funding_sources'),
          this.$t('routing_fee_reserve_calculations'),
          this.$t('payment_timeouts'),
          this.$t('watchdog')
        ],
        server: [
          this.$t('currency_settings'),
          this.$t('payments'),
          this.$t('lightning_addresses'),
          this.$t('wallet_limiter'),
          this.$t('service_fees')
        ],
        exchange_providers: [
          'LNbits Price Aggregator',
          'Bitcoin Price History',
          this.$t('exchange_providers')
        ],
        fiat_providers: [
          this.$t('fiat_providers'),
          this.$t('api'),
          this.$t('webhook'),
          this.$t('service_fees'),
          this.$t('amount_limits')
        ],
        security: [
          this.$t('server_management'),
          this.$t('authentication'),
          'Nostr Auth',
          'Google Auth',
          'GitHub Auth',
          'Keycloak Auth',
          'OIDC Auth',
          this.$t('security_tools'),
          this.$t('ip_blocker'),
          this.$t('rate_limiter'),
          this.$t('callback'),
          this.$t('lnurl')
        ],
        users: [
          this.$t('user_management'),
          this.$t('admin_users'),
          this.$t('allowed_users'),
          this.$t('allow_creation_user')
        ],
        extensions: [
          this.$t('extension_sources'),
          'Wasm Extension',
          this.$t('admin_extensions'),
          this.$t('user_default_extensions'),
          this.$t('extension_builder_manifest_url'),
          this.$t('reviews_url')
        ],
        notifications: [
          this.$t('notifications_configure'),
          this.$t('notifications_nostr_config'),
          this.$t('notifications_telegram_config'),
          this.$t('notifications_email_config'),
          this.$t('notifications')
        ],
        audit: [
          this.$t('audit'),
          this.$t('audit_record_req'),
          this.$t('audit_http_methods_label'),
          this.$t('audit_paths_label')
        ],
        'assets-config': ['Assets', 'Thumbnails', 'Users'],
        site_customisation: [
          this.$t('ui_management'),
          this.$t('ui_custom_badge_title'),
          this.$t('ui_custom_image'),
          this.$t('themes'),
          this.$t('ad_space_section_title')
        ],
        blockexplorer: [
          this.$t('block_explorer'),
          this.$t('electrum_compatible_server')
        ]
      }
      return this.settingsNavigationItems.flatMap(item =>
        (sections[item.value] || [item.label]).map(section => ({
          tab: item.value,
          category: item.label,
          section,
          icon: item.icon,
          searchText: `${item.group} ${item.label} ${section}`.toLowerCase()
        }))
      )
    },
    filteredSettingsSearch() {
      const terms = (this.settingsSearch || '')
        .toLowerCase()
        .split(/\s+/)
        .filter(Boolean)
      if (!terms.length) return []
      return this.settingsSearchIndex
        .filter(item => terms.every(term => item.searchText.includes(term)))
        .slice(0, 12)
    }
  },
  methods: {
    adminTabFromRoute(route) {
      if (route.path.startsWith('/admin/extensions/wasm/limits')) {
        return 'wasm-limit-config'
      }
      if (route.path.startsWith('/admin/extensions/wasm')) {
        return 'wasm-runtime'
      }
      if (route.hash.length > 1) {
        return route.hash.replace('#', '')
      }
      return 'funding'
    },
    adminRouteForTab(tab) {
      if (tab === 'wasm-runtime') {
        return '/admin/extensions/wasm'
      }
      if (tab === 'wasm-limit-config') {
        return '/admin/extensions/wasm/limits'
      }
      return `/admin#${tab}`
    },
    selectSettingsSearchResult(result) {
      this.tab = result.tab
      this.settingsSearch = ''
      this.$nextTick(() => {
        window.setTimeout(() => {
          const headings = document.querySelectorAll(
            '.q-tab-panel--active h6, .q-tab-panel--active strong, .q-tab-panel--active .text-subtitle1'
          )
          const heading = [...headings].find(element =>
            element.textContent
              .trim()
              .toLowerCase()
              .includes(result.section.toLowerCase())
          )
          heading?.scrollIntoView({behavior: 'smooth', block: 'start'})
        }, 350)
      })
    },
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
          this.settingsLoaded = true
        })
        .catch(LNbits.utils.notifyApiError)
    },
    updateSettings() {
      const data = _.omit(this.formData, [
        'is_super_user',
        'lnbits_allowed_funding_sources',
        'touch'
      ])
      this.isSaving = true
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
        .finally(() => {
          this.isSaving = false
        })
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
