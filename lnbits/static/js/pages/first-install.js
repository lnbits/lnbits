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
    async setPassword() {
      try {
        const tokenQuery = this.setupToken
          ? `?token=${encodeURIComponent(this.setupToken)}`
          : ''
        await LNbits.api.request(
          'PUT',
          `/api/v1/auth/first_install${tokenQuery}`,
          null,
          {
            username: this.loginData.username,
            password: this.loginData.password,
            password_repeat: this.loginData.passwordRepeat
          }
        )
        window.location.href = '/admin'
      } catch (e) {
        LNbits.utils.notifyApiError(e)
      }
    }
  },
  created() {
    const params = new URLSearchParams(window.location.search)
    this.setupToken = params.get('token') || ''
    document.title = 'First Install - LNbits'
  }
}
