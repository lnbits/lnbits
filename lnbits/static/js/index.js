window.app = Vue.createApp({
  el: '#vue',
  mixins: [window.windowMixin],
  data() {
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
    showLogin(authMethod) {
      this.authAction = 'login'
      this.authMethod = authMethod
    },
    showRegister(authMethod) {
      this.user = ''
      this.username = null
      this.password = null
      this.passwordRepeat = null

      this.authAction = 'register'
      this.authMethod = authMethod
    },

    async register() {
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
    async reset() {
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
    async login() {
      try {
        await LNbits.api.login(this.username, this.password)
        window.location.href = '/wallet'
      } catch (e) {
        LNbits.utils.notifyApiError(e)
      }
    },
    async loginUsr() {
      try {
        await LNbits.api.loginUsr(this.usr)
        this.usr = ''
        window.location.href = '/wallet'
      } catch (e) {
        console.warn(e)
        LNbits.utils.notifyApiError(e)
      }
    },
    createWallet() {
      LNbits.api.createAccount(this.walletName).then(res => {
        window.location = '/wallet?usr=' + res.data.user + '&wal=' + res.data.id
      })
    },
    processing() {
      Quasar.Notify.create({
        timeout: 0,
        message: 'Processing...',
        icon: null
      })
    }
  },
  created() {
    this.description = SITE_DESCRIPTION
    this.allowedRegister = ALLOWED_REGISTER
    this.authAction =
      !this.allowedRegister ||
      Quasar.LocalStorage.getItem('lnbits.disclaimerShown')
        ? 'login'
        : 'register'
    this.isUserAuthorized = !!this.$q.cookies.get('is_lnbits_user_authorized')
    const _acccess_cookies_for_safari_refresh_do_not_delete = document.cookie
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
