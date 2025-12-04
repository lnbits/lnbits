window.PageHome = {
  template: '#page-home',
  mixins: [window.windowMixin],
  data() {
    return {
      lnurl: '',
      authAction: 'login',
      authMethod: 'username-password',
      usr: '',
      username: '',
      reset_key: '',
      email: '',
      password: '',
      passwordRepeat: '',
      walletName: '',
      signup: false
    }
  },
  computed: {
    showClaimLnurl() {
      return (
        this.lnurl !== '' &&
        this.allowRegister &&
        'user-id-only' in this.LNBITS_AUTH_METHODS
      )
    },
    formatDescription() {
      return LNbits.utils.convertMarkdown(this.SITE_DESCRIPTION)
    },
    isAccessTokenExpired() {
      return this.$q.cookies.get('is_access_token_expired')
    },
    allowRegister() {
      return this.LNBITS_NEW_ACCOUNTS_ALLOWED
    },
    // TODO: this makes no sense
    hasCustomImage() {
      return this.LNBITS_CUSTOM_IMAGE
    },
    showHomepageElements() {
      return this.HOMEPAGE_ELEMENTS_ENABLED
    },
    siteTitle() {
      return this.SITE_TITLE || ''
    },
    siteTagline() {
      return this.SITE_TAGLINE || ''
    },
    adsEnabled() {
      return this.AD_SPACE_ENABLED && this.AD_SPACE && this.AD_SPACE.length > 0
    },
    adsTitle() {
      return this.AD_SPACE_TITLE || ''
    },
    ads() {
      return this.AD_SPACE.map(ad => ad.split(';'))
    },
    lnbitsBannerEnabled() {
      return (
        this.isSatsDenomination &&
        this.SITE_TITLE == 'LNbits' &&
        this.LNBITS_SHOW_HOME_PAGE_ELEMENTS == true
      )
    }
  },
  methods: {
    showLogin(authMethod) {
      this.authAction = 'login'
      this.authMethod = authMethod
    },
    showRegister(authMethod) {
      this.user = ''
      this.username = null
      this.password = null
      this.passwordRepeat = null

      this.authAction = 'register'
      this.authMethod = authMethod
    },

    async register() {
      try {
        await LNbits.api.register(
          this.username,
          this.email,
          this.password,
          this.passwordRepeat
        )
        this.refreshAuthUser()
      } catch (e) {
        LNbits.utils.notifyApiError(e)
      }
    },
    async reset() {
      try {
        await LNbits.api.reset(
          this.reset_key,
          this.password,
          this.passwordRepeat
        )
        this.refreshAuthUser()
      } catch (e) {
        LNbits.utils.notifyApiError(e)
      }
    },
    async login() {
      try {
        await LNbits.api.login(this.username, this.password)
        this.refreshAuthUser()
      } catch (e) {
        LNbits.utils.notifyApiError(e)
      }
    },
    async loginUsr() {
      try {
        await LNbits.api.loginUsr(this.usr)
        this.refreshAuthUser()
      } catch (e) {
        console.warn(e)
        LNbits.utils.notifyApiError(e)
      }
    },
    async refreshAuthUser() {
      try {
        const res = await LNbits.api.getAuthUser()
        this.g.user = LNbits.map.user(res.data)
        this.g.isPublicPage = false
        this.$router.push(`/wallet/${this.g.user.wallets[0].id}`)
      } catch (e) {
        console.warn(e)
        LNbits.utils.notifyApiError(e)
      }
    },
    createWallet() {
      LNbits.api.createAccount(this.walletName).then(res => {
        this.$router.push(`/wallet/${res.data.id}`)
      })
    },
    processing() {
      Quasar.Notify.create({
        timeout: 0,
        message: 'Processing...',
        icon: null
      })
    }
  },
  created() {
    if (this.g.isUserAuthorized) {
      return this.refreshAuthUser()
    }
    const urlParams = new URLSearchParams(window.location.search)
    this.reset_key = urlParams.get('reset_key')
    if (this.reset_key) {
      this.authAction = 'reset'
    }
    // check if lightning parameters are present in the URL
    if (urlParams.has('lightning')) {
      this.lnurl = urlParams.get('lightning')
    }
  }
}
