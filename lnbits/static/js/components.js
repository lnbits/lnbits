window.app.component(QrcodeVue)

window.app.component('lnbits-extension-rating', {
  template: '#lnbits-extension-rating',
  name: 'lnbits-extension-rating',
  props: ['rating']
})

window.app.component('lnbits-fsat', {
  template: '<span>{{ fsat }}</span>',
  props: {
    amount: {
      type: Number,
      default: 0
    }
  },
  computed: {
    fsat() {
      return LNbits.utils.formatSat(this.amount)
    }
  }
})

window.app.component('lnbits-wallet-list', {
  mixins: [window.windowMixin],
  template: '#lnbits-wallet-list',
  props: ['balance'],
  data() {
    return {
      activeWallet: null,
      balance: 0,
      showForm: false,
      walletName: '',
      LNBITS_DENOMINATION: LNBITS_DENOMINATION
    }
  },
  methods: {
    createWallet() {
      LNbits.api.createWallet(this.g.user.wallets[0], this.walletName)
    }
  },
  created() {
    document.addEventListener('updateWalletBalance', this.updateWalletBalance)
  }
})

window.app.component('lnbits-extension-list', {
  mixins: [window.windowMixin],
  template: '#lnbits-extension-list',
  data() {
    return {
      extensions: [],
      searchTerm: ''
    }
  },
  watch: {
    'g.user.extensions': {
      handler(newExtensions) {
        this.loadExtensions()
      },
      deep: true
    }
  },
  computed: {
    userExtensions() {
      return this.updateUserExtensions(this.searchTerm)
    }
  },
  methods: {
    async loadExtensions() {
      try {
        const {data} = await LNbits.api.request('GET', '/api/v1/extension')
        this.extensions = data
          .map(extension => LNbits.map.extension(extension))
          .sort((a, b) => a.name.localeCompare(b.name))
      } catch (error) {
        LNbits.utils.notifyApiError(error)
      }
    },
    updateUserExtensions(filterBy) {
      const path = window.location.pathname
      const userExtensions = this.g.user.extensions

      return this.extensions
        .filter(o => userExtensions.includes(o.code))
        .filter(o => {
          if (!filterBy) return true
          return `${o.code} ${o.name} ${o.short_description} ${o.url}`
            .toLocaleLowerCase()
            .includes(filterBy.toLocaleLowerCase())
        })
        .map(obj => {
          obj.isActive = path.startsWith(obj.url)
          return obj
        })
    }
  },
  async created() {
    await this.loadExtensions()
  }
})

window.app.component('lnbits-manage', {
  mixins: [window.windowMixin],
  template: '#lnbits-manage',
  props: [
    'showAdmin',
    'showNode',
    'showExtensions',
    'showUsers',
    'showAudit',
    'showPayments'
  ],
  methods: {
    isActive(path) {
      return window.location.pathname === path
    }
  },
  data() {
    return {
      extensions: []
    }
  }
})

window.app.component('lnbits-payment-details', {
  mixins: [window.windowMixin],
  template: '#lnbits-payment-details',
  props: ['payment'],
  mixins: [window.windowMixin],
  data() {
    return {
      LNBITS_DENOMINATION: LNBITS_DENOMINATION
    }
  },
  computed: {
    hasPreimage() {
      return (
        this.payment.preimage &&
        this.payment.preimage !==
          '0000000000000000000000000000000000000000000000000000000000000000'
      )
    },
    hasExpiry() {
      return !!this.payment.expiry
    },
    hasSuccessAction() {
      return (
        this.hasPreimage &&
        this.payment.extra &&
        this.payment.extra.success_action
      )
    },
    webhookStatusColor() {
      return this.payment.webhook_status >= 300 ||
        this.payment.webhook_status < 0
        ? 'red-10'
        : !this.payment.webhook_status
          ? 'cyan-7'
          : 'green-10'
    },
    webhookStatusText() {
      return this.payment.webhook_status
        ? this.payment.webhook_status
        : 'not sent yet'
    },
    hasTag() {
      return this.payment.extra && !!this.payment.extra.tag
    },
    extras() {
      if (!this.payment.extra) return []
      let extras = _.omit(this.payment.extra, ['tag', 'success_action'])
      return Object.keys(extras).map(key => ({key, value: extras[key]}))
    }
  }
})

window.app.component('lnbits-lnurlpay-success-action', {
  mixins: [window.windowMixin],
  template: '#lnbits-lnurlpay-success-action',
  props: ['payment', 'success_action'],
  data() {
    return {
      decryptedValue: this.success_action.ciphertext
    }
  },
  mounted() {
    if (this.success_action.tag !== 'aes') return null
    decryptLnurlPayAES(this.success_action, this.payment.preimage).then(
      value => {
        this.decryptedValue = value
      }
    )
  }
})

window.app.component('lnbits-qrcode', {
  mixins: [window.windowMixin],
  template: '#lnbits-qrcode',
  components: {
    QrcodeVue
  },
  props: {
    value: {
      type: String,
      required: true
    },
    options: Object
  },
  data() {
    return {
      custom: {
        margin: 1,
        width: 350,
        size: 350,
        logo: LNBITS_QR_LOGO
      }
    }
  },
  created() {
    this.custom = {...this.custom, ...this.options}
  }
})

window.app.component('lnbits-notifications-btn', {
  template: '#lnbits-notifications-btn',
  mixins: [window.windowMixin],
  props: ['pubkey'],
  data() {
    return {
      isSupported: false,
      isSubscribed: false,
      isPermissionGranted: false,
      isPermissionDenied: false
    }
  },
  methods: {
    // converts base64 to Array buffer
    urlB64ToUint8Array(base64String) {
      const padding = '='.repeat((4 - (base64String.length % 4)) % 4)
      const base64 = (base64String + padding)
        .replace(/\-/g, '+')
        .replace(/_/g, '/')
      const rawData = atob(base64)
      const outputArray = new Uint8Array(rawData.length)

      for (let i = 0; i < rawData.length; ++i) {
        outputArray[i] = rawData.charCodeAt(i)
      }

      return outputArray
    },
    toggleNotifications() {
      this.isSubscribed ? this.unsubscribe() : this.subscribe()
    },
    saveUserSubscribed(user) {
      let subscribedUsers =
        JSON.parse(
          this.$q.localStorage.getItem('lnbits.webpush.subscribedUsers')
        ) || []
      if (!subscribedUsers.includes(user)) subscribedUsers.push(user)
      this.$q.localStorage.set(
        'lnbits.webpush.subscribedUsers',
        JSON.stringify(subscribedUsers)
      )
    },
    removeUserSubscribed(user) {
      let subscribedUsers =
        JSON.parse(
          this.$q.localStorage.getItem('lnbits.webpush.subscribedUsers')
        ) || []
      subscribedUsers = subscribedUsers.filter(arr => arr !== user)
      this.$q.localStorage.set(
        'lnbits.webpush.subscribedUsers',
        JSON.stringify(subscribedUsers)
      )
    },
    isUserSubscribed(user) {
      let subscribedUsers =
        JSON.parse(
          this.$q.localStorage.getItem('lnbits.webpush.subscribedUsers')
        ) || []
      return subscribedUsers.includes(user)
    },
    subscribe() {
      // catch clicks from disabled type='a' button (https://github.com/quasarframework/quasar/issues/9258)
      if (!this.isSupported || this.isPermissionDenied) {
        return
      }

      // ask for notification permission
      Notification.requestPermission()
        .then(permission => {
          this.isPermissionGranted = permission === 'granted'
          this.isPermissionDenied = permission === 'denied'
        })
        .catch(console.log)

      // create push subscription
      navigator.serviceWorker.ready.then(registration => {
        navigator.serviceWorker.getRegistration().then(registration => {
          registration.pushManager
            .getSubscription()
            .then(subscription => {
              if (
                subscription === null ||
                !this.isUserSubscribed(this.g.user.id)
              ) {
                const applicationServerKey = this.urlB64ToUint8Array(
                  this.pubkey
                )
                const options = {applicationServerKey, userVisibleOnly: true}

                registration.pushManager
                  .subscribe(options)
                  .then(subscription => {
                    LNbits.api
                      .request('POST', '/api/v1/webpush', null, {
                        subscription: JSON.stringify(subscription)
                      })
                      .then(response => {
                        this.saveUserSubscribed(response.data.user)
                        this.isSubscribed = true
                      })
                      .catch(LNbits.utils.notifyApiError)
                  })
              }
            })
            .catch(console.log)
        })
      })
    },
    unsubscribe() {
      navigator.serviceWorker.ready
        .then(registration => {
          registration.pushManager.getSubscription().then(subscription => {
            if (subscription) {
              LNbits.api
                .request(
                  'DELETE',
                  '/api/v1/webpush?endpoint=' + btoa(subscription.endpoint),
                  null
                )
                .then(() => {
                  this.removeUserSubscribed(this.g.user.id)
                  this.isSubscribed = false
                })
                .catch(LNbits.utils.notifyApiError)
            }
          })
        })
        .catch(console.log)
    },
    checkSupported() {
      let https = window.location.protocol === 'https:'
      let serviceWorkerApi = 'serviceWorker' in navigator
      let notificationApi = 'Notification' in window
      let pushApi = 'PushManager' in window

      this.isSupported = https && serviceWorkerApi && notificationApi && pushApi

      if (!this.isSupported) {
        console.log(
          'Notifications disabled because requirements are not met:',
          {
            HTTPS: https,
            'Service Worker API': serviceWorkerApi,
            'Notification API': notificationApi,
            'Push API': pushApi
          }
        )
      }

      return this.isSupported
    },
    async updateSubscriptionStatus() {
      await navigator.serviceWorker.ready
        .then(registration => {
          registration.pushManager.getSubscription().then(subscription => {
            this.isSubscribed =
              !!subscription && this.isUserSubscribed(this.g.user.id)
          })
        })
        .catch(console.log)
    }
  },
  created() {
    this.isPermissionDenied = Notification.permission === 'denied'

    if (this.checkSupported()) {
      this.updateSubscriptionStatus()
    }
  }
})

window.app.component('lnbits-dynamic-fields', {
  template: '#lnbits-dynamic-fields',
  mixins: [window.windowMixin],
  props: ['options', 'modelValue'],
  data() {
    return {
      formData: null,
      rules: [val => !!val || 'Field is required']
    }
  },
  methods: {
    applyRules(required) {
      return required ? this.rules : []
    },
    buildData(options, data = {}) {
      return options.reduce((d, option) => {
        if (option.options?.length) {
          d[option.name] = this.buildData(option.options, data[option.name])
        } else {
          d[option.name] = data[option.name] ?? option.default
        }
        return d
      }, {})
    },
    handleValueChanged() {
      this.$emit('update:model-value', this.formData)
    }
  },
  created() {
    this.formData = this.buildData(this.options, this.modelValue)
  }
})

window.app.component('lnbits-dynamic-chips', {
  template: '#lnbits-dynamic-chips',
  mixins: [window.windowMixin],
  props: ['modelValue'],
  data() {
    return {
      chip: '',
      chips: []
    }
  },
  methods: {
    addChip() {
      if (!this.chip) return
      this.chips.push(this.chip)
      this.chip = ''
      this.$emit('update:model-value', this.chips.join(','))
    },
    removeChip(index) {
      this.chips.splice(index, 1)
      this.$emit('update:model-value', this.chips.join(','))
    }
  },
  created() {
    if (typeof this.modelValue === 'string') {
      this.chips = this.modelValue.split(',')
    } else {
      this.chips = [...this.modelValue]
    }
  }
})

window.app.component('lnbits-update-balance', {
  template: '#lnbits-update-balance',
  mixins: [window.windowMixin],
  props: ['wallet_id', 'small_btn'],
  computed: {
    denomination() {
      return LNBITS_DENOMINATION
    },
    admin() {
      return user.super_user
    }
  },
  data() {
    return {
      credit: 0
    }
  },
  methods: {
    updateBalance(scope) {
      LNbits.api
        .updateBalance(scope.value, this.wallet_id)
        .then(res => {
          if (res.data.success !== true) {
            throw new Error(res.data)
          }
          credit = parseInt(scope.value)
          Quasar.Notify.create({
            type: 'positive',
            message: this.$t('credit_ok', {
              amount: credit
            }),
            icon: null
          })
          this.credit = 0
          scope.value = 0
          scope.set()
        })
        .catch(LNbits.utils.notifyApiError)
    }
  }
})

window.app.component('user-id-only', {
  template: '#user-id-only',
  mixins: [window.windowMixin],
  props: {
    allowed_new_users: Boolean,
    authAction: String,
    authMethod: String,
    usr: String,
    wallet: String
  },
  data() {
    return {
      user: this.usr,
      walletName: this.wallet
    }
  },
  methods: {
    showLogin(method) {
      this.$emit('show-login', method)
    },
    showRegister(method) {
      this.$emit('show-register', method)
    },
    loginUsr() {
      this.$emit('update:usr', this.user)
      this.$emit('login-usr')
    },
    createWallet() {
      this.$emit('update:wallet', this.walletName)
      this.$emit('create-wallet')
    }
  },
  computed: {
    showInstantLogin() {
      // do not show if authmethod is 'username-password' and authAction is 'register'
      return (
        this.authMethod !== 'username-password' ||
        this.authAction !== 'register'
      )
    }
  },
  created() {}
})

window.app.component('username-password', {
  template: '#username-password',
  mixins: [window.windowMixin],
  props: {
    allowed_new_users: Boolean,
    authMethods: Array,
    authAction: String,
    username: String,
    password_1: String,
    password_2: String,
    resetKey: String
  },
  data() {
    return {
      oauth: [
        'nostr-auth-nip98',
        'google-auth',
        'github-auth',
        'keycloak-auth'
      ],
      username: this.userName,
      password: this.password_1,
      passwordRepeat: this.password_2,
      reset_key: this.resetKey
    }
  },
  methods: {
    login() {
      this.$emit('update:userName', this.username)
      this.$emit('update:password_1', this.password)
      this.$emit('login')
    },
    register() {
      this.$emit('update:userName', this.username)
      this.$emit('update:password_1', this.password)
      this.$emit('update:password_2', this.passwordRepeat)
      this.$emit('register')
    },
    reset() {
      this.$emit('update:resetKey', this.reset_key)
      this.$emit('update:passeord_1', this.password)
      this.$emit('update:password_2', this.passwordRepeat)
      this.$emit('reset')
    },
    validateUsername(val) {
      const usernameRegex = new RegExp(
        '^(?=[a-zA-Z0-9._]{2,20}$)(?!.*[_.]{2})[^_.].*[^_.]$'
      )
      return usernameRegex.test(val)
    },
    async signInWithNostr() {
      try {
        console.log('### signInWithNostr')
        const nostrToken = await this.createNostrToken()
        if (!nostrToken) {
          return
        }
        resp = await LNbits.api.loginByProvider(
          'nostr',
          {Authorization: nostrToken},
          {}
        )
        window.location.href = '/wallet'
      } catch (error) {
        console.warn(error)
        const details = error?.response?.data?.detail || `${error}`
        Quasar.Notify.create({
          type: 'negative',
          message: 'Failed to sign in with Nostr.',
          caption: details
        })
      }
    },
    async createNostrToken() {
      try {
        async function _signEvent(e) {
          try {
            const {data} = await LNbits.api.getServerHealth()
            e.created_at = data.server_time
            return await window.nostr.signEvent(e)
          } catch (error) {
            console.error(error)
            Quasar.Notify.create({
              type: 'negative',
              message: 'Failed to sign nostr event.',
              caption: `${error}`
            })
          }
        }
        if (!window.nostr?.signEvent) {
          Quasar.Notify.create({
            type: 'negative',
            message: 'No Nostr signing app detected.',
            caption: 'Is "window.nostr" present?'
          })
          return
        }
        const tagU = `${window.location}nostr`
        const tagMethod = 'POST'
        const nostrToken = await NostrTools.nip98.getToken(
          tagU,
          tagMethod,
          e => _signEvent(e),
          true
        )
        const isTokenValid = await NostrTools.nip98.validateToken(
          nostrToken,
          tagU,
          tagMethod
        )
        if (!isTokenValid) {
          throw new Error('Invalid signed token!')
        }

        return nostrToken
      } catch (error) {
        console.warn(error)
        Quasar.Notify.create({
          type: 'negative',
          message: 'Failed create Nostr event.',
          caption: `${error}`
        })
      }
    }
  },
  computed: {
    showOauth() {
      return this.oauth.some(m => this.authMethods.includes(m))
    }
  },
  created() {}
})

window.app.component('separator-text', {
  template: '#separator-text',
  props: {
    text: String,
    uppercase: {
      type: Boolean,
      default: false
    },
    color: {
      type: String,
      default: 'grey'
    }
  }
})
