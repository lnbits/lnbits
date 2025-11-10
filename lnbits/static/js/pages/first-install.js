window.PageFirstInstall = {
  template: '#page-first-install',
  mixins: [window.windowMixin],
  data() {
    return {
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
        await LNbits.api.request('PUT', '/api/v1/auth/first_install', null, {
          username: this.loginData.username,
          password: this.loginData.password,
          password_repeat: this.loginData.passwordRepeat
        })
        window.location.href = '/admin'
      } catch (e) {
        LNbits.utils.notifyApiError(e)
      }
    }
  },
  created() {
    document.title = 'First Install - LNbits'
  }
}
