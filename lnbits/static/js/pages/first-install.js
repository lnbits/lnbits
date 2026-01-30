window.PageFirstInstall = {
  template: '#page-first-install',
  data() {
    return {
      loginData: {
        isPwd: true,
        isPwdRepeat: true,
        username: '',
        password: '',
        passwordRepeat: '',
        token: ''
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
          token: this.loginData.token
        })
        .then(() => {
          window.location.href = '/admin'
        })
        .catch(this.utils.notifyApiError)
    }
  },
  created() {
    const params = new URLSearchParams(window.location.search)
    this.loginData.token = params.get('token') || ''
    document.title = 'First Install - LNbits'
  }
}
