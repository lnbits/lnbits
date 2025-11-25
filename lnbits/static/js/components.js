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

window.app.component('lnbits-manage', {
  mixins: [window.windowMixin],
  template: '#lnbits-manage',
  computed: {
    showAdmin() {
      return this.LNBITS_ADMIN_UI
    },
    showUsers() {
      return this.LNBITS_ADMIN_UI
    },
    showNode() {
      return this.LNBITS_NODE_UI
    },
    showAudit() {
      return this.LNBITS_AUDIT_ENABLED
    },
    showExtensions() {
      return this.LNBITS_EXTENSIONS_DEACTIVATE_ALL === false
    }
  },
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
    this.utils
      .decryptLnurlPayAES(this.success_action, this.payment.preimage)
      .then(value => {
        this.decryptedValue = value
      })
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
      reset_key: this.resetKey,
      keycloakOrg: LNBITS_AUTH_KEYCLOAK_ORG || 'Keycloak',
      keycloakIcon: LNBITS_AUTH_KEYCLOAK_ICON
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
      this.$emit('update:password_1', this.password)
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

window.app.component('lnbits-node-ranks', {
  props: ['ranks'],
  data() {
    return {
      stats: [
        {label: 'Capacity', key: 'capacity'},
        {label: 'Channels', key: 'channelcount'},
        {label: 'Age', key: 'age'},
        {label: 'Growth', key: 'growth'},
        {label: 'Availability', key: 'availability'}
      ]
    }
  },
  template: `
    <q-card class='q-my-none'>
    <div class='column q-ma-md'>
      <h5 class='text-subtitle1 text-bold q-my-none'>1ml Node Rank</h5>
      <div v-for='stat in stats' class='q-gutter-sm'>
        <div class='row items-center'>
          <div class='col-9'>{{ stat.label }}</div>
          <div class='col-3 text-subtitle1 text-bold'>
            {{ (ranks && ranks[stat.key]) ?? '-' }}
          </div>
        </div>
      </div>
    </div>
    </q-card>
  `
})

window.app.component('lnbits-channel-stats', {
  props: ['stats'],
  data() {
    return {
      states: [
        {label: 'Active', value: 'active', color: 'green'},
        {label: 'Pending', value: 'pending', color: 'orange'},
        {label: 'Inactive', value: 'inactive', color: 'grey'},
        {label: 'Closed', value: 'closed', color: 'red'}
      ]
    }
  },
  template: `
    <q-card>
    <div class='column q-ma-md'>
      <h5 class='text-subtitle1 text-bold q-my-none'>Channels</h5>
      <div v-for='state in states' class='q-gutter-sm'>
        <div class='row'>
          <div class='col-9'>
            <q-badge rounded size='md' :color='state.color'>{{ state.label }}</q-badge>
          </div>
          <div class='col-3 text-subtitle1 text-bold'>
            {{ (stats?.counts && stats.counts[state.value]) ?? "-" }}
          </div>
        </div>
      </div>
    </div>
    </q-card>
  `
})

window.app.component('lnbits-stat', {
  props: ['title', 'amount', 'msat', 'btc'],
  computed: {
    value() {
      return (
        this.amount ??
        (this.btc
          ? LNbits.utils.formatSat(this.btc)
          : LNbits.utils.formatMsat(this.msat))
      )
    }
  },
  template: `
    <q-card>
    <q-card-section>
      <div class='text-overline text-primary'>
        {{ title }}
      </div>
      <div>
        <span class='text-h4 text-bold q-my-none'>{{ value }}</span>
        <span class='text-h5' v-if='msat != undefined'>sats</span>
        <span class='text-h5' v-if='btc != undefined'>BTC</span>
      </div>
    </q-card-section>
    </q-card>
  `
})

window.app.component('lnbits-node-qrcode', {
  props: ['info'],
  mixins: [window.windowMixin],
  template: `
    <q-card class="my-card">
      <q-card-section>
        <div class="text-h6">
          <div style="text-align: center">
            <vue-qrcode
              :value="info.addresses[0]"
              :options="{width: 250}"
              v-if='info.addresses[0]'
              class="rounded-borders"
            ></vue-qrcode>
            <div v-else class='text-subtitle1'>
              No addresses available
            </div>
          </div>
        </div>
      </q-card-section>
      <q-card-actions vertical>
        <q-btn
          dense
          unelevated
          size="md"
          @click="utils.copyText(info.id)"
        >Public Key<q-tooltip> Click to copy </q-tooltip>
        </q-btn>
      </q-card-actions>
    </q-card>
  `
})

window.app.component('lnbits-channel-balance', {
  props: ['balance', 'color'],
  methods: {
    formatMsat(msat) {
      return LNbits.utils.formatMsat(msat)
    }
  },
  template: `
    <div>
        <div class="row items-center justify-between">
          <span class="text-weight-thin">
            Local: {{ formatMsat(balance.local_msat) }}
            sats
          </span>
          <span class="text-weight-thin">
            Remote: {{ formatMsat(balance.remote_msat) }}
            sats
          </span>
        </div>

        <q-linear-progress
          rounded
          size="25px"
          :value="balance.local_msat / balance.total_msat"
          :color="color"
          :style="\`color: #\${this.color}\`"
        >
          <div class="absolute-full flex flex-center">
            <q-badge
              color="white"
              text-color="accent"
              :label="formatMsat(balance.total_msat) + ' sats'"
            >
              {{ balance.alias }}
            </q-badge>
          </div>
       </q-linear-progress>
    </div>
  `
})

window.app.component('lnbits-node-info', {
  props: ['info'],
  data() {
    return {
      showDialog: false
    }
  },
  mixins: [window.windowMixin],
  methods: {
    shortenNodeId(nodeId) {
      return nodeId
        ? nodeId.substring(0, 5) + '...' + nodeId.substring(nodeId.length - 5)
        : '...'
    }
  },
  template: `
    <div class='row items-baseline q-gutter-x-sm'>
    <div class='text-h4 text-bold'>{{ this.info.alias }}</div>
    <div class='row items-center q-gutter-sm'>
      <div class='text-subtitle1 text-light'>{{ this.info.backend_name }}</div>
      <q-badge
        :style='\`background-color: #\${this.info.color}\`'
        class='text-bold'
      >
        #{{ this.info.color }}
      </q-badge>
      <div class='text-bold'>{{ shortenNodeId(this.info.id) }}</div>
      <q-btn
        size='xs'
        flat
        dense
        icon='content_paste'
        @click='utils.copyText(info.id)'
      ></q-btn>
      <q-btn
        size='xs'
        flat
        dense
        icon='qr_code'
        @click='showDialog = true'
      ></q-btn>
    </div>
      <q-dialog v-model="showDialog">
        <lnbits-node-qrcode :info='info'></lnbits-node-qrcode>
      </q-dialog>
    </div>
  `
})

window.app.component('lnbits-stat', {
  props: ['title', 'amount', 'msat', 'btc'],
  computed: {
    value() {
      return (
        this.amount ??
        (this.btc
          ? LNbits.utils.formatSat(this.btc)
          : LNbits.utils.formatMsat(this.msat))
      )
    }
  },
  template: `
        <q-card>
        <q-card-section>
          <div class='text-overline text-primary'>
            {{ title }}
          </div>
          <div>
            <span class='text-h4 text-bold q-my-none'>{{ value }}</span>
            <span class='text-h5' v-if='msat != undefined'>sats</span>
            <span class='text-h5' v-if='btc != undefined'>BTC</span>
          </div>
        </q-card-section>
        </q-card>
      `
})
