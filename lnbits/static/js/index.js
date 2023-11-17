new Vue({
  el: '#vue',
  mixins: [windowMixin],
  data: function () {
    return {
      disclaimerDialog: {
        show: false,
        data: {},
        description: ''
      },
      authAction: 'login',
      authMethod: 'username-password',
      usr: '',
      username: '',
      email: '',
      password: '',
      password_repeat: '',
      walletName: '',
      signup: false
    }
  },
  computed: {
    formatDescription() {
      return LNbits.utils.convertMarkdown(this.description)
    },
    isUserAuthorized() {
      return this.$q.cookies.get('is_lnbits_user_authorized')
    }
  },
  methods: {
    showLogin: function (authMethod) {
      this.authAction = 'login'
      this.authMethod = authMethod
    },
    showRegister: function (authMethod) {
      this.authAction = 'register'
      this.authMethod = authMethod
    },
    register: async function () {
      try {
        await LNbits.api.register(
          this.username,
          this.email,
          this.password,
          this.password_repeat
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
        LNbits.utils.notifyApiError(e)
      }
    },
    createWallet: function () {
      LNbits.api.createAccount(this.walletName).then(res => {
        window.location = '/wallet?usr=' + res.data.user + '&wal=' + res.data.id
      })
    },
    processing: function () {
      this.$q.notify({
        timeout: 0,
        message: 'Processing...',
        icon: null
      })
    }
  },
  created() {
    this.description = SITE_DESCRIPTION

    if (this.isUserAuthorized) {
      window.location.href = '/wallet'
    }
  }
})
