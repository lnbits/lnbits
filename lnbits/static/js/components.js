/* global _, Vue, moment, LNbits, EventHub, decryptLnurlPayAES */

Vue.component('lnbits-fsat', {
  props: {
    amount: {
      type: Number,
      default: 0
    }
  },
  template: '<span>{{ fsat }}</span>',
  computed: {
    fsat: function () {
      return LNbits.utils.formatSat(this.amount)
    }
  }
})

Vue.component('lnbits-wallet-list', {
  data: function () {
    return {
      user: null,
      activeWallet: null,
      activeBalance: [],
      showForm: false,
      walletName: '',
      LNBITS_DENOMINATION: LNBITS_DENOMINATION
    }
  },
  template: `
    <q-list v-if="user && user.wallets.length" dense class="lnbits-drawer__q-list">
      <q-item-label header v-text="$t('wallets')"></q-item-label>
      <q-item v-for="wallet in wallets" :key="wallet.id"
        clickable
        :active="activeWallet && activeWallet.id === wallet.id"
        tag="a" :href="wallet.url">
        <q-item-section side>
          <q-avatar size="md"
            :color="(activeWallet && activeWallet.id === wallet.id)
              ? (($q.dark.isActive) ? 'primary' : 'primary')
              : 'grey-5'">
            <q-icon name="flash_on" :size="($q.dark.isActive) ? '21px' : '20px'"
              :color="($q.dark.isActive) ? 'blue-grey-10' : 'grey-3'"></q-icon>
          </q-avatar>
        </q-item-section>
        <q-item-section>
          <q-item-label lines="1">{{ wallet.name }}</q-item-label>
          <q-item-label v-if="LNBITS_DENOMINATION != 'sats'" caption>{{ parseFloat(String(wallet.live_fsat).replaceAll(",", "")) / 100  }} {{ LNBITS_DENOMINATION }}</q-item-label>
          <q-item-label v-else caption>{{ wallet.live_fsat }} {{ LNBITS_DENOMINATION }}</q-item-label>
        </q-item-section>
        <q-item-section side v-show="activeWallet && activeWallet.id === wallet.id">
          <q-icon name="chevron_right" color="grey-5" size="md"></q-icon>
        </q-item-section>
      </q-item>
      <q-item clickable @click="showForm = !showForm">
        <q-item-section side>
          <q-icon :name="(showForm) ? 'remove' : 'add'" color="grey-5" size="md"></q-icon>
        </q-item-section>
        <q-item-section>
          <q-item-label lines="1" class="text-caption" v-text="$t('add_wallet')"></q-item-label>
        </q-item-section>
      </q-item>
      <q-item v-if="showForm">
        <q-item-section>
          <q-form @submit="createWallet">
            <q-input filled dense v-model="walletName" label="Name wallet *">
              <template v-slot:append>
                <q-btn round dense flat icon="send" size="sm" @click="createWallet" :disable="walletName === ''"></q-btn>
              </template>
            </q-input>
          </q-form>
        </q-item-section>
      </q-item>
    </q-list>
  `,
  computed: {
    wallets: function () {
      var bal = this.activeBalance
      return this.user.wallets.map(function (obj) {
        obj.live_fsat =
          bal.length && bal[0] === obj.id
            ? LNbits.utils.formatSat(bal[1])
            : obj.fsat
        return obj
      })
    }
  },
  methods: {
    createWallet: function () {
      LNbits.api.createWallet(this.user.wallets[0], this.walletName)
    },
    updateWalletBalance: function (payload) {
      this.activeBalance = payload
    }
  },
  created: function () {
    if (window.user) {
      this.user = LNbits.map.user(window.user)
    }
    if (window.wallet) {
      this.activeWallet = LNbits.map.wallet(window.wallet)
    }
    EventHub.$on('update-wallet-balance', this.updateWalletBalance)
  }
})

Vue.component('lnbits-extension-list', {
  data: function () {
    return {
      extensions: [],
      user: null
    }
  },
  template: `
    <q-list v-if="user && userExtensions.length > 0" dense class="lnbits-drawer__q-list">
      <q-item-label header v-text="$t('extensions')"></q-item-label>
      <q-item v-for="extension in userExtensions" :key="extension.code"
        clickable
        :active="extension.isActive"
        tag="a" :href="extension.url">
        <q-item-section side>
          <q-avatar size="md">
            <q-img
              :src="extension.tile"
              style="max-width:20px"
            ></q-img>
          </q-avatar>
        </q-item-section>
        <q-item-section>
          <q-item-label lines="1">{{ extension.name }} </q-item-label>
        </q-item-section>
        <q-item-section side v-show="extension.isActive">
          <q-icon name="chevron_right" color="grey-5" size="md"></q-icon>
        </q-item-section>
      </q-item>
      <div class="lt-md q-mt-xl q-mb-xl"></div>
    </q-list>
  `,
  computed: {
    userExtensions: function () {
      if (!this.user) return []

      var path = window.location.pathname
      var userExtensions = this.user.extensions

      return this.extensions
        .filter(function (obj) {
          return userExtensions.indexOf(obj.code) !== -1
        })
        .map(function (obj) {
          obj.isActive = path.startsWith(obj.url)
          return obj
        })
    }
  },
  created: function () {
    if (window.extensions) {
      this.extensions = window.extensions
        .map(function (data) {
          return LNbits.map.extension(data)
        })
        .sort(function (a, b) {
          return a.name.localeCompare(b.name)
        })
    }

    if (window.user) {
      this.user = LNbits.map.user(window.user)
    }
  }
})

Vue.component('lnbits-manage', {
  props: ['showAdmin', 'showNode', 'showExtensions', 'showUsers'],
  methods: {
    isActive: function (path) {
      return window.location.pathname === path
    }
  },
  data: function () {
    return {
      extensions: [],
      user: null
    }
  },
  template: `
    <q-list v-if="user" dense class="lnbits-drawer__q-list">
      <q-item-label header v-text="$t('manage')"></q-item-label>
      <div v-if="user.admin">
        <q-item v-if='showAdmin' clickable tag="a" href="/admin" :active="isActive('/admin')">
          <q-item-section side>
            <q-icon name="admin_panel_settings" :color="isActive('/admin') ? 'primary' : 'grey-5'" size="md"></q-icon>
          </q-item-section>
          <q-item-section>
            <q-item-label lines="1" v-text="$t('server')"></q-item-label>
          </q-item-section>
        </q-item>
        <q-item v-if='showNode' clickable tag="a" href="/node" :active="isActive('/node')">
          <q-item-section side>
            <q-icon name="developer_board" :color="isActive('/node') ? 'primary' : 'grey-5'" size="md"></q-icon>
          </q-item-section>
          <q-item-section>
            <q-item-label lines="1" v-text="$t('node')"></q-item-label>
          </q-item-section>
        </q-item>
        <q-item v-if="showUsers" clickable tag="a" href="/users" :active="isActive('/users')">
          <q-item-section side>
            <q-icon name="groups" :color="isActive('/users') ? 'primary' : 'grey-5'" size="md"></q-icon>
          </q-item-section>
          <q-item-section>
            <q-item-label lines="1" v-text="$t('users')"></q-item-label>
          </q-item-section>
        </q-item>
      </div>
      <q-item v-if="showExtensions" clickable tag="a" href="/extensions" :active="isActive('/extensions')">
        <q-item-section side>
          <q-icon name="extension" :color="isActive('/extensions') ? 'primary' : 'grey-5'" size="md"></q-icon>
        </q-item-section>
        <q-item-section>
          <q-item-label lines="1" v-text="$t('extensions')"></q-item-label>
        </q-item-section>
      </q-item>
    </q-list>
  `,

  created: function () {
    if (window.user) {
      this.user = LNbits.map.user(window.user)
    }
  }
})

Vue.component('lnbits-payment-details', {
  props: ['payment'],
  mixins: [windowMixin],
  data: function () {
    return {
      LNBITS_DENOMINATION: LNBITS_DENOMINATION
    }
  },
  template: `
  <div class="q-py-md" style="text-align: left">

  <div v-if="payment.tag" class="row justify-center q-mb-md">
    <q-badge v-if="hasTag" color="yellow" text-color="black">
      #{{ payment.tag }}
    </q-badge>
  </div>

  <div class="row">
    <b v-text="$t('created')"></b>:
    {{ payment.date }} ({{ payment.dateFrom }})
  </div>

  <div class="row" v-if="hasExpiry">
   <b v-text="$t('expiry')"></b>:
   {{ payment.expirydate }} ({{ payment.expirydateFrom }})
  </div>

  <div class="row">
   <b v-text="$t('amount')"></b>:
    {{ (payment.amount / 1000).toFixed(3) }} {{LNBITS_DENOMINATION}}
  </div>

  <div class="row">
    <b v-text="$t('fee')"></b>:
    {{ (payment.fee / 1000).toFixed(3) }} {{LNBITS_DENOMINATION}}
  </div>

  <div class="text-wrap">
    <b style="white-space: nowrap;" v-text="$t('payment_hash')"></b>:&nbsp;{{ payment.payment_hash }}
        <q-icon name="content_copy" @click="copyText(payment.payment_hash)" size="1em" color="grey" class="q-mb-xs cursor-pointer" />
  </div>

  <div class="text-wrap">
    <b style="white-space: nowrap;" v-text="$t('memo')"></b>:&nbsp;{{ payment.memo }}
  </div>

  <div class="text-wrap" v-if="payment.webhook">
    <b style="white-space: nowrap;" v-text="$t('webhook')"></b>:&nbsp;{{ payment.webhook }}:&nbsp;<q-badge :color="webhookStatusColor" text-color="white">
      {{ webhookStatusText }}
    </q-badge>
  </div>

  <div class="text-wrap" v-if="hasPreimage">
    <b style="white-space: nowrap;" v-text="$t('payment_proof')"></b>:&nbsp;{{ payment.preimage }}
  </div>

  <div class="row" v-for="entry in extras">
    <q-badge v-if="hasTag" color="secondary" text-color="white">
      extra
    </q-badge>
    <b>{{ entry.key }}</b>:
    {{ entry.value }}
  </div>

  <div class="row" v-if="hasSuccessAction">
    <b>Success action</b>:
      <lnbits-lnurlpay-success-action
        :payment="payment"
        :success_action="payment.extra.success_action"
      ></lnbits-lnurlpay-success-action>
  </div>

</div>
  `,
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

Vue.component('lnbits-lnurlpay-success-action', {
  props: ['payment', 'success_action'],
  data() {
    return {
      decryptedValue: this.success_action.ciphertext
    }
  },
  template: `
    <div>
      <p class="q-mb-sm">{{ success_action.message || success_action.description }}</p>
      <code v-if="decryptedValue" class="text-h6 q-mt-sm q-mb-none">
        {{ decryptedValue }}
      </code>
      <p v-else-if="success_action.url" class="text-h6 q-mt-sm q-mb-none">
        <a target="_blank" style="color: inherit;" :href="success_action.url">{{ success_action.url }}</a>
      </p>
    </div>
  `,
  mounted: function () {
    if (this.success_action.tag !== 'aes') return null

    decryptLnurlPayAES(this.success_action, this.payment.preimage).then(
      value => {
        this.decryptedValue = value
      }
    )
  }
})

Vue.component('lnbits-qrcode', {
  mixins: [windowMixin],
  props: ['value'],
  components: {[VueQrcode.name]: VueQrcode},
  data() {
    return {
      logo: LNBITS_QR_LOGO
    }
  },
  template: `
  <div class="qrcode__wrapper">
    <qrcode :value="value"
    :options="{errorCorrectionLevel: 'Q', width: 800}" class="rounded-borders"></qrcode>
    <img class="qrcode__image" :src="logo" alt="..." />
  </div>
  `
})

Vue.component('lnbits-notifications-btn', {
  mixins: [windowMixin],
  props: ['pubkey'],
  data() {
    return {
      isSupported: false,
      isSubscribed: false,
      isPermissionGranted: false,
      isPermissionDenied: false
    }
  },
  template: `
    <q-btn
      v-if="g.user.wallets"
      :disabled="!this.isSupported"
      dense
      flat
      round
      @click="toggleNotifications()"
      :icon="this.isSubscribed ? 'notifications_active' : 'notifications_off'"
      size="sm"
      type="a"
    >
      <q-tooltip v-if="this.isSupported && !this.isSubscribed">Subscribe to notifications</q-tooltip>
      <q-tooltip v-if="this.isSupported && this.isSubscribed">Unsubscribe from notifications</q-tooltip>
      <q-tooltip v-if="this.isSupported && this.isPermissionDenied">
          Notifications are disabled,<br/>please enable or reset permissions
      </q-tooltip>
      <q-tooltip v-if="!this.isSupported">Notifications are not supported</q-tooltip>
    </q-btn>
  `,
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
      var self = this

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
        .catch(function (e) {
          console.log(e)
        })

      // create push subscription
      navigator.serviceWorker.ready.then(registration => {
        navigator.serviceWorker.getRegistration().then(registration => {
          registration.pushManager
            .getSubscription()
            .then(function (subscription) {
              if (
                subscription === null ||
                !self.isUserSubscribed(self.g.user.id)
              ) {
                const applicationServerKey = self.urlB64ToUint8Array(
                  self.pubkey
                )
                const options = {applicationServerKey, userVisibleOnly: true}

                registration.pushManager
                  .subscribe(options)
                  .then(function (subscription) {
                    LNbits.api
                      .request(
                        'POST',
                        '/api/v1/webpush',
                        self.g.user.wallets[0].adminkey,
                        {
                          subscription: JSON.stringify(subscription)
                        }
                      )
                      .then(function (response) {
                        self.saveUserSubscribed(response.data.user)
                        self.isSubscribed = true
                      })
                      .catch(function (error) {
                        LNbits.utils.notifyApiError(error)
                      })
                  })
              }
            })
            .catch(function (e) {
              console.log(e)
            })
        })
      })
    },
    unsubscribe() {
      var self = this

      navigator.serviceWorker.ready
        .then(registration => {
          registration.pushManager.getSubscription().then(subscription => {
            if (subscription) {
              LNbits.api
                .request(
                  'DELETE',
                  '/api/v1/webpush?endpoint=' + btoa(subscription.endpoint),
                  self.g.user.wallets[0].adminkey
                )
                .then(function () {
                  self.removeUserSubscribed(self.g.user.id)
                  self.isSubscribed = false
                })
                .catch(function (error) {
                  LNbits.utils.notifyApiError(error)
                })
            }
          })
        })
        .catch(function (e) {
          console.log(e)
        })
    },
    checkSupported: function () {
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
    updateSubscriptionStatus: async function () {
      var self = this

      await navigator.serviceWorker.ready
        .then(registration => {
          registration.pushManager.getSubscription().then(subscription => {
            self.isSubscribed =
              !!subscription && self.isUserSubscribed(self.g.user.id)
          })
        })
        .catch(function (e) {
          console.log(e)
        })
    }
  },
  created: function () {
    this.isPermissionDenied = Notification.permission === 'denied'

    if (this.checkSupported()) {
      this.updateSubscriptionStatus()
    }
  }
})

Vue.component('lnbits-dynamic-fields', {
  mixins: [windowMixin],
  props: ['options', 'value'],
  data() {
    return {
      formData: null,
      rules: [val => !!val || 'Field is required']
    }
  },

  template: `
    <div v-if="formData">
      <div class="row q-mb-lg" v-for="o in options">
        <div class="col auto-width">
          <p v-if=o.options?.length class="q-ml-xl">
            <span v-text="o.label || o.name"></span> <small v-if="o.description"> (<span v-text="o.description"></span>)</small>
          </p>
          <lnbits-dynamic-fields v-if="o.options?.length" :options="o.options" v-model="formData[o.name]"
            @input="handleValueChanged" class="q-ml-xl">
          </lnbits-dynamic-fields>
          <div v-else>
            <q-input
              v-if="o.type === 'number'"
              type="number"
              v-model="formData[o.name]"
              @input="handleValueChanged"
              :label="o.label || o.name"
              :hint="o.description"
              :rules="applyRules(o.required)"
              filled
              dense
            ></q-input>
            <q-input
              v-else-if="o.type === 'text'"
              type="textarea"
              rows="5"
              v-model="formData[o.name]"
              @input="handleValueChanged"
              :label="o.label || o.name"
              :hint="o.description"
              :rules="applyRules(o.required)"
              filled
              dense
            ></q-input>
            <q-input
              v-else-if="o.type === 'password'"
              v-model="formData[o.name]"
              @input="handleValueChanged"
              type="password"
              :label="o.label || o.name"
              :hint="o.description"
              :rules="applyRules(o.required)"
              filled
              dense
            ></q-input>
            <q-select
              v-else-if="o.type === 'select'"
              v-model="formData[o.name]"
              @input="handleValueChanged"
              :label="o.label || o.name"
              :hint="o.description"
              :options="o.values"
              :rules="applyRules(o.required)"
            ></q-select>
            <q-select
              v-else-if="o.isList"
              v-model.trim="formData[o.name]"
              @input="handleValueChanged"
              input-debounce="0"
              new-value-mode="add-unique"
              :label="o.label || o.name"
              :hint="o.description"
              :rules="applyRules(o.required)"
              filled
              multiple
              dense
              use-input
              use-chips
              multiple
              hide-dropdown-icon
            ></q-select>
            <div v-else-if="o.type === 'bool'">
              <q-item tag="label" v-ripple>
                <q-item-section avatar top>
                  <q-checkbox v-model="formData[o.name]" @input="handleValueChanged" />
                </q-item-section>
                <q-item-section>
                  <q-item-label><span v-text="o.label || o.name"></span></q-item-label>
                  <q-item-label caption> <span v-text="o.description"></span> </q-item-label>
                </q-item-section>
              </q-item>
            </div>
            <q-input
              v-else-if="o.type === 'hidden'"
              v-model="formData[o.name]"
              type="text"
              style="display: none"
              :rules="applyRules(o.required)"
            ></q-input>
            <q-input
              v-else
              v-model="formData[o.name]"
              @input="handleValueChanged"
              :hint="o.description"
              :label="o.label || o.name"
              :rules="applyRules(o.required)"
              filled
              dense
            ></q-input>
          </div>
        </div>
      </div>
    </div>
  `,
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
      this.$emit('input', this.formData)
    }
  },
  created: function () {
    this.formData = this.buildData(this.options, this.value)
  }
})

Vue.component('lnbits-update-balance', {
  mixins: [windowMixin],
  props: ['wallet_id', 'callback'],
  computed: {
    denomination() {
      return LNBITS_DENOMINATION
    },
    admin() {
      return this.g.user.admin
    }
  },
  data: function () {
    return {
      credit: 0
    }
  },
  methods: {
    updateBalance: function (credit) {
      LNbits.api
        .updateBalance(credit, this.wallet_id)
        .then(res => {
          if (res.data.status !== 'Success') {
            throw new Error(res.data)
          }
          this.callback({
            success: true,
            credit: parseInt(credit),
            wallet_id: this.wallet_id
          })
        })
        .then(_ => {
          credit = parseInt(credit)
          this.$q.notify({
            type: 'positive',
            message: this.$t('wallet_topup_ok', {
              amount: credit
            }),
            icon: null
          })
          return credit
        })
        .catch(function (error) {
          LNbits.utils.notifyApiError(error)
        })
    }
  },
  template: `
      <q-btn
        v-if="admin"
        round
        color="primary"
        icon="add"
        size="sm"
      >
        <q-popup-edit
          class="bg-accent text-white"
          v-slot="scope"
          v-model="credit"
        >
          <q-input
            filled
            :label='$t("credit_label", { denomination: denomination })'
            :hint="$t('credit_hint')"
            v-model="scope.value"
            dense
            autofocus
            @keyup.enter="updateBalance(scope.value)"
          >
            <template v-slot:append>
              <q-icon name="edit" />
            </template>
          </q-input>
        </q-popup-edit>
        <q-tooltip>Topup Wallet</q-tooltip>
      </q-btn>
    `
})
