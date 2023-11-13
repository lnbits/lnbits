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
    }
  },
  methods: {
    register: function () {
      axios({
        method: 'POST',
        url: '/api/v1/register',
        data: {
          username: this.username,
          email: this.email,
          password: this.password,
          password_repeat: this.password_repeat
        }
      })
        .then(response => {
          this.$q.localStorage.set('lnbits.token', response.data.access_token)
          window.location.href = '/wallet'
        })
        .catch(LNbits.utils.notifyApiError)
    },
    onSubmit: function (evt) {
      console.log('### onSubmit', evt)
      // evt.target.submit()

      return false
    },
    login: async function () {
      try {
        const {data} = await LNbits.api.login(this.username, this.pasword)
        this.$q.localStorage.set('lnbits.token', data.access_token)
        window.location.href = 'wallet'
      } catch (e) {
        LNbits.utils.notifyApiError(e)
      }
    },
    loginUsr: async function () {
      try {
        const {data} = await LNbits.api.login('none', 'none', {usr: this.usr})
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
    if (this.$q.localStorage.getItem('lnbits.token')) {
      window.location.href = '/wallet'
    }
  }
})
