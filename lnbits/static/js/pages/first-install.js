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
        firstInstallToken: ''
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
          first_install_token: this.loginData.firstInstallToken
        })
        .then(async () => {
          const res = await LNbits.api.getAuthUser()
          this.g.user = LNbits.map.user(res.data)
          this.g.isPublicPage = false
          this.$router.push('/admin')
        })
        .catch(this.utils.notifyApiError)
    }
  },
  created() {
    const params = new URLSearchParams(window.location.search)
    this.loginData.firstInstallToken = params.get('token') || ''
  }
}
