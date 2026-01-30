window.PageFirstInstall = {
  template: '#page-first-install',
  data() {
    return {
      setupToken: '',
      loginData: {
        isPwd: true,
        isPwdRepeat: true,
        username: '',
        password: '',
        passwordRepeat: ''
      }
    }
  },
  computed: {
    checkPasswordsMatch() {
      return this.loginData.password !== this.loginData.passwordRepeat
    }
  },
  methods: {
    setPassword() {
      LNbits.api
        .request('PUT', `/api/v1/auth/first_install`, null, {
          username: this.loginData.username,
          password: this.loginData.password,
          password_repeat: this.loginData.passwordRepeat,
          token: this.setupToken
        })
        .then(() => {
          window.location.href = '/admin'
        })
        .catch(this.utils.notifyApiError)
    }
  },
  created() {
    const params = new URLSearchParams(window.location.search)
    this.setupToken = params.get('token') || ''
    document.title = 'First Install - LNbits'
  }
}
