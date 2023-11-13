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
    isUserLoggedIn() {
      return !!this.$q.localStorage.getItem('lnbits.token')
    }
  },
  methods: {
    register: async function () {
      try {
        const {data} = await LNbits.api.register(
          this.username,
          this.email,
          this.password,
          this.password_repeat
        )
        this.$q.localStorage.set('lnbits.token', data.access_token)
        window.location.href = 'wallet'
      } catch (e) {
        LNbits.utils.notifyApiError(e)
      }
    },
    login: async function () {
      try {
        const {data} = await LNbits.api.login(this.username, this.password)
        this.$q.localStorage.set('lnbits.token', data.access_token)
        window.location.href = 'wallet'
      } catch (e) {
        LNbits.utils.notifyApiError(e)
      }
    },
    loginUsr: async function () {
      try {
        const {data} = await LNbits.api.loginUsr(this.usr)
        this.$q.localStorage.set('lnbits.token', data.access_token)
        window.location.href = 'wallet'
      } catch (e) {
        LNbits.utils.notifyApiError(e)
      }
    },
    logout: function () {
      console.log('### loghout')
      this.$q.localStorage.remove('lnbits.token')
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
    if (this.isUserLoggedIn) {
      window.location.href = '/wallet'
    }
  }
})
