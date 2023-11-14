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
      return this.$q.localStorage.getItem('lnbits.user.authorized')
    }
  },
  methods: {
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
        this.$q.localStorage.set('lnbits.user.authorized', true)
        window.location.href = '/wallet'
      } catch (e) {
        LNbits.utils.notifyApiError(e)
      }
    },
    loginUsr: async function () {
      try {
        await LNbits.api.loginUsr(this.usr)
        this.$q.localStorage.set('lnbits.user.authorized', true)
        window.location.href = '/wallet'
      } catch (e) {
        LNbits.utils.notifyApiError(e)
      }
    },
    createWallet: function () {
      LNbits.api.createAccount(this.walletName).then(res => {
        window.location = '/wallet?wal=' + res.data.id
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
