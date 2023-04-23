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
      password: '',
      password_repeat: '',
      walletName: ''
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
          email: this.username,
          password: this.password,
          password_repeat: this.password_repeat
        }
      })
        .then(response => {
          this.$q.cookies.set('access-token', response.data.access_token)
          this.$q.localStorage.set('lnbits.token', response.data.access_token)
          this.$q.localStorage.set('lnbits.usr', response.data.usr)
          window.location.href = '/wallet'
        })
        .catch(LNbits.utils.notifyApiError)
    },
    login: function () {
      axios({
        method: 'POST',
        url: '/api/v1/login',
        data: {username: this.username, password: this.password}
      })
        .then(response => {
          this.$q.cookies.set('access-token', response.data.access_token)
          this.$q.localStorage.set('lnbits.token', response.data.access_token)
          // this.$q.localStorage.set('lnbits.usr', response.data.usr)
          window.location.href = '/wallet'
        })
        .catch(LNbits.utils.notifyApiError)
    },
    login_usr: function () {
      axios({
        method: 'POST',
        url: '/api/v1/login',
        data: {usr: this.usr, username: 'unknown', password: 'unknown'}
      })
        .then(response => {
          this.$q.cookies.set('access-token', response.data.access_token)
          this.$q.localStorage.set('lnbits.token', response.data.access_token)
          // this.$q.localStorage.set('lnbits.usr', response.data.usr)
          window.location.href = '/wallet'
        })
        .catch(LNbits.utils.notifyApiError)
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
  }
})
