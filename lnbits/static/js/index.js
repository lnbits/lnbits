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
    login: function () {
      axios({
        method: 'POST',
        url: '/api/v1/login',
        headers: {'Content-Type': 'application/x-www-form-urlencoded'},
        data: {username: this.username, password: this.password}
      })
        .then(response => {
          this.$q.localStorage.set('lnbits.token', response.data.access_token)
          window.location.href = 'wallet'
        })
        .catch(LNbits.utils.notifyApiError)
    },
    loginUsr: function () {
      axios({
        method: 'POST',
        url: `/api/v1/login?usr=${this.usr}`,
        headers: {'Content-Type': 'application/x-www-form-urlencoded'},
        data: {username: 'none', password: 'none'}
      })
        .then(response => {
          this.$q.localStorage.set('lnbits.token', response.data.access_token)
          window.location.href = '/wallet'
        })
        .catch(LNbits.utils.notifyApiError)
    },
    logout: function () {
      console.log('### loghout')
      this.$q.localStorage.remove('lnbits.token')
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
    if (this.$q.localStorage.getItem('lnbits.token')) {
      window.location.href = '/wallet'
    }
  }
})
