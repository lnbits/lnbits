window.windowMixin = {
  i18n: window.i18n,
  data() {
    return {
      g: window.g,
      toggleSubs: true,
      mobileSimple: true,
      walletFlip: true,
      showAddWalletDialog: {show: false},
      isUserAuthorized: false,
      isSatsDenomination: WINDOW_SETTINGS['LNBITS_DENOMINATION'] == 'sats',
      allowedThemes: WINDOW_SETTINGS['LNBITS_THEME_OPTIONS'],
      walletEventListeners: [],
      darkChoice: this.$q.localStorage.has('lnbits.darkMode')
        ? this.$q.localStorage.getItem('lnbits.darkMode')
        : true,
      borderChoice: this.$q.localStorage.has('lnbits.border')
        ? this.$q.localStorage.getItem('lnbits.border')
        : USE_DEFAULT_BORDER,
      gradientChoice: this.$q.localStorage.has('lnbits.gradientBg')
        ? this.$q.localStorage.getItem('lnbits.gradientBg')
        : USE_DEFAULT_GRADIENT,
      themeChoice: this.$q.localStorage.has('lnbits.theme')
        ? this.$q.localStorage.getItem('lnbits.theme')
        : USE_DEFAULT_THEME,
      reactionChoice: this.$q.localStorage.has('lnbits.reactions')
        ? this.$q.localStorage.getItem('lnbits.reactions')
        : USE_DEFAULT_REACTION,
      bgimageChoice: this.$q.localStorage.has('lnbits.backgroundImage')
        ? this.$q.localStorage.getItem('lnbits.backgroundImage')
        : USE_DEFAULT_BGIMAGE,
      ...WINDOW_SETTINGS
    }
  },

  methods: {
    flipWallets(smallScreen) {
      this.walletFlip = !this.walletFlip
      if (this.walletFlip && smallScreen) {
        this.g.visibleDrawer = false
      }
      this.$q.localStorage.set('lnbits.walletFlip', this.walletFlip)
    },
    goToWallets() {
      this.$router.push({
        path: '/wallets'
      })
    },
    submitAddWallet() {
      if (
        this.showAddWalletDialog.name &&
        this.showAddWalletDialog.name.length > 0
      ) {
        LNbits.api.createWallet(
          this.g.user.wallets[0],
          this.showAddWalletDialog.name
        )
        this.showAddWalletDialog = {show: false}
      } else {
        this.$q.notify({
          message: 'Please enter a name for the wallet',
          color: 'negative'
        })
      }
    },
    simpleMobile() {
      this.$q.localStorage.set('lnbits.mobileSimple', !this.mobileSimple)
      this.refreshRoute()
    },
    paymentEvents() {
      this.g.walletEventListeners = this.g.walletEventListeners || []
      this.g.user.wallets.forEach(wallet => {
        if (!this.g.walletEventListeners.includes(wallet.id)) {
          this.g.walletEventListeners.push(wallet.id)
          LNbits.events.onInvoicePaid(wallet, data => {
            const walletIndex = this.g.user.wallets.findIndex(
              w => w.id === wallet.id
            )
            if (walletIndex !== -1) {
              //needed for balance being deducted
              let satBalance = data.wallet_balance
              if (data.payment.amount < 0) {
                satBalance = data.wallet_balance += data.payment.amount / 1000
              }
              //update the wallet
              Object.assign(this.g.user.wallets[walletIndex], {
                sat: satBalance,
                msat: data.wallet_balance * 1000,
                fsat: data.wallet_balance.toLocaleString()
              })
              //update the current wallet
              if (this.g.wallet.id === data.payment.wallet_id) {
                Object.assign(this.g.wallet, this.g.user.wallets[walletIndex])

                //if on the wallet page and payment is incoming trigger the eventReaction
                if (
                  data.payment.amount > 0 &&
                  window.location.pathname === '/wallet'
                ) {
                  eventReaction(data.wallet_balance * 1000)
                }
              }
            }
            this.g.updatePaymentsHash = data.payment.payment_hash
            this.g.updatePayments = !this.g.updatePayments
          })
        }
      })
    },
    selectWallet(wallet) {
      Object.assign(this.g.wallet, wallet)
      // this.wallet = this.g.wallet
      this.g.updatePayments = !this.g.updatePayments
      this.balance = parseInt(wallet.balance_msat / 1000)
      const currentPath = this.$route.path
      if (currentPath !== '/wallet') {
        this.$router.push({
          path: '/wallet',
          query: {wal: this.g.wallet.id}
        })
      } else {
        this.$router.replace({
          path: '/wallet',
          query: {wal: this.g.wallet.id}
        })
      }
    },
    formatBalance(amount) {
      if (LNBITS_DENOMINATION != 'sats') {
        return LNbits.utils.formatCurrency(amount / 100, LNBITS_DENOMINATION)
      } else {
        return LNbits.utils.formatSat(amount) + ' sats'
      }
    },
    changeTheme(newValue) {
      document.body.setAttribute('data-theme', newValue)
      this.$q.localStorage.set('lnbits.theme', newValue)
      this.themeChoice = newValue
    },
    applyGradient() {
      if (this.gradientChoice) {
        document.body.classList.add('gradient-bg')
        this.$q.localStorage.set('lnbits.gradientBg', true)
        // Ensure dark mode is enabled when gradient background is applied
        if (!this.$q.dark.isActive) {
          this.toggleDarkMode()
        }
      } else {
        document.body.classList.remove('gradient-bg')
        this.$q.localStorage.set('lnbits.gradientBg', false)
      }
    },
    applyBackgroundImage() {
      if (this.bgimageChoice == 'null') this.bgimageChoice = ''
      if (this.bgimageChoice == '') {
        document.body.classList.remove('bg-image')
      } else {
        document.body.classList.add('bg-image')
        document.body.style.setProperty(
          '--background',
          `url(${this.bgimageChoice})`
        )
      }
      this.$q.localStorage.set('lnbits.backgroundImage', this.bgimageChoice)
    },
    applyBorder() {
      // Remove any existing border classes
      document.body.classList.forEach(cls => {
        if (cls.endsWith('-border')) {
          document.body.classList.remove(cls)
        }
      })
      this.$q.localStorage.setItem('lnbits.border', this.borderChoice)
      document.body.classList.add(this.borderChoice)
    },
    toggleDarkMode() {
      this.$q.dark.toggle()
      this.darkChoice = this.$q.dark.isActive
      this.$q.localStorage.set('lnbits.darkMode', this.$q.dark.isActive)
      if (!this.$q.dark.isActive) {
        this.gradientChoice = false
        this.applyGradient()
      }
    },
    copyText(text, message, position) {
      Quasar.copyToClipboard(text).then(() => {
        Quasar.Notify.create({
          message: message || 'Copied to clipboard!',
          position: position || 'bottom'
        })
      })
    },
    async checkUsrInUrl() {
      try {
        const params = new URLSearchParams(window.location.search)
        const usr = params.get('usr')
        if (!usr) {
          return
        }

        if (!this.isUserAuthorized) {
          await LNbits.api.loginUsr(usr)
        }

        params.delete('usr')
        const cleanQueryPrams = params.size ? `?${params.toString()}` : ''

        window.history.replaceState(
          {},
          document.title,
          window.location.pathname + cleanQueryPrams
        )
      } finally {
        this.isUserAuthorized = !!this.$q.cookies.get(
          'is_lnbits_user_authorized'
        )
      }
    },
    async logout() {
      LNbits.utils
        .confirmDialog(
          'Do you really want to logout?' +
            ' Please visit "My Account" page to check your credentials!'
        )
        .onOk(async () => {
          try {
            await LNbits.api.logout()
            window.location = '/'
          } catch (e) {
            LNbits.utils.notifyApiError(e)
          }
        })
    },
    themeParams() {
      const url = new URL(window.location.href)
      const params = new URLSearchParams(window.location.search)
      const fields = ['theme', 'dark', 'gradient']
      const toBoolean = value =>
        value.trim().toLowerCase() === 'true' || value === '1'

      // Check if any of the relevant parameters ('theme', 'dark', 'gradient') are present in the URL.
      if (fields.some(param => params.has(param))) {
        const theme = params.get('theme')
        const darkMode = params.get('dark')
        const gradient = params.get('gradient')
        const border = params.get('border')

        if (theme && this.allowedThemes.includes(theme.trim().toLowerCase())) {
          const normalizedTheme = theme.trim().toLowerCase()
          document.body.setAttribute('data-theme', normalizedTheme)
          this.$q.localStorage.set('lnbits.theme', normalizedTheme)
        }

        if (darkMode) {
          const isDark = toBoolean(darkMode)
          this.$q.localStorage.set('lnbits.darkMode', isDark)
          if (!isDark) {
            this.$q.localStorage.set('lnbits.gradientBg', false)
          }
        }

        if (gradient) {
          const isGradient = toBoolean(gradient)
          this.$q.localStorage.set('lnbits.gradientBg', isGradient)
          if (isGradient) {
            this.$q.localStorage.set('lnbits.darkMode', true)
          }
        }
        if (border) {
          this.$q.localStorage.set('lnbits.border', border)
        }

        // Remove processed parameters
        fields.forEach(param => params.delete(param))

        window.history.replaceState(null, null, url.pathname)
      }
    },
    refreshRoute() {
      const path = window.location.pathname
      console.log(path)

      this.$router.push('/temp').then(() => {
        this.$router.replace({path})
      })
    }
  },
  async created() {
    this.$q.dark.set(
      this.$q.localStorage.has('lnbits.darkMode')
        ? this.$q.localStorage.getItem('lnbits.darkMode')
        : true
    )
    Chart.defaults.color = this.$q.dark.isActive ? '#fff' : '#000'
    this.changeTheme(this.themeChoice)
    this.applyBorder()
    if (this.$q.dark.isActive) {
      this.applyGradient()
    }
    this.applyBackgroundImage()

    let locale = this.$q.localStorage.getItem('lnbits.lang')
    if (locale) {
      window.LOCALE = locale
      window.i18n.global.locale = locale
    }

    this.g.langs = window.langs ?? []

    addEventListener('offline', event => {
      console.log('offline', event)
      this.g.offline = true
    })

    addEventListener('online', event => {
      console.log('back online', event)
      this.g.offline = false
    })

    if (window.user) {
      this.g.user = Vue.reactive(window.LNbits.map.user(window.user))
    }
    if (window.wallet) {
      this.g.wallet = Vue.reactive(window.LNbits.map.wallet(window.wallet))
    }
    if (window.extensions) {
      this.g.extensions = Vue.reactive(window.extensions)
    }
    await this.checkUsrInUrl()
    this.themeParams()
    this.walletFlip = this.$q.localStorage.getItem('lnbits.walletFlip')
    if (
      this.$q.screen.gt.sm ||
      this.$q.localStorage.getItem('lnbits.mobileSimple') == false
    ) {
      this.mobileSimple = false
    }
  },
  mounted() {
    if (this.g.user) {
      this.paymentEvents()
    }
  }
}
