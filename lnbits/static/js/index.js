window.app = Vue.createApp({
  el: '#vue',
  mixins: [window.windowMixin],
  data: function () {
    return {
      disclaimerDialog: {
        show: false,
        data: {},
        description: ''
      },
      isUserAuthorized: false,
      authAction: 'login',
      authMethod: 'username-password',
      usr: '',
      username: '',
      reset_key: '',
      email: '',
      password: '',
      passwordRepeat: '',
      walletName: '',
      signup: false
    }
  },
  computed: {
    formatDescription() {
      return LNbits.utils.convertMarkdown(this.description)
    },
    isAccessTokenExpired() {
      return this.$q.cookies.get('is_access_token_expired')
    }
  },
  methods: {
    showLogin: function (authMethod) {
      this.authAction = 'login'
      this.authMethod = authMethod
    },
    showRegister: function (authMethod) {
      this.user = ''
      this.username = null
      this.password = null
      this.passwordRepeat = null

      this.authAction = 'register'
      this.authMethod = authMethod
    },
    signInWithNostr: async function () {
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
    createNostrToken: async function () {
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
    },
    register: async function () {
      try {
        await LNbits.api.register(
          this.username,
          this.email,
          this.password,
          this.passwordRepeat
        )
        window.location.href = '/wallet'
      } catch (e) {
        LNbits.utils.notifyApiError(e)
      }
    },
    reset: async function () {
      try {
        await LNbits.api.reset(
          this.reset_key,
          this.password,
          this.passwordRepeat
        )
        window.location.href = '/wallet'
      } catch (e) {
        LNbits.utils.notifyApiError(e)
      }
    },
    login: async function () {
      try {
        await LNbits.api.login(this.username, this.password)
        window.location.href = '/wallet'
      } catch (e) {
        LNbits.utils.notifyApiError(e)
      }
    },
    loginUsr: async function () {
      try {
        await LNbits.api.loginUsr(this.usr)
        this.usr = ''
        window.location.href = '/wallet'
      } catch (e) {
        console.warn(e)
        LNbits.utils.notifyApiError(e)
      }
    },
    createWallet: function () {
      LNbits.api.createAccount(this.walletName).then(res => {
        window.location = '/wallet?usr=' + res.data.user + '&wal=' + res.data.id
      })
    },
    processing: function () {
      Quasar.Notify.create({
        timeout: 0,
        message: 'Processing...',
        icon: null
      })
    },
    validateUsername: function (val) {
      const usernameRegex = new RegExp(
        '^(?=[a-zA-Z0-9._]{2,20}$)(?!.*[_.]{2})[^_.].*[^_.]$'
      )
      return usernameRegex.test(val)
    }
  },
  created() {
    this.description = SITE_DESCRIPTION
    this.isUserAuthorized = !!this.$q.cookies.get('is_lnbits_user_authorized')
    if (this.isUserAuthorized) {
      window.location.href = '/wallet'
    }
    this.reset_key = new URLSearchParams(window.location.search).get(
      'reset_key'
    )
    if (this.reset_key) {
      this.authAction = 'reset'
    }
  }
})
