window.app = Vue.createApp({
  el: '#vue',
  mixins: [window.windowMixin],
  data() {
    return {
      user: null,
      hasUsername: false,
      showUserId: false,
      reactionOptions: [
        'None',
        'confettiBothSides',
        'confettiFireworks',
        'confettiStars'
      ],
      borderOptions: [
        'retro-border',
        'hard-border',
        'neon-border',
        'no-border'
      ],
      tab: 'user',
      credentialsData: {
        show: false,
        oldPassword: null,
        newPassword: null,
        newPasswordRepeat: null,
        username: null,
        pubkey: null
      }
    }
  },
  methods: {
    activeLanguage(lang) {
      return window.i18n.global.locale === lang
    },
    changeLanguage(newValue) {
      window.i18n.global.locale = newValue
      this.$q.localStorage.set('lnbits.lang', newValue)
    },
    toggleDarkMode() {
      this.$q.dark.toggle()
      this.$q.localStorage.set('lnbits.darkMode', this.$q.dark.isActive)
      if (!this.$q.dark.isActive && this.gradientChoice) {
        this.toggleGradient()
      }
    },
    applyGradient() {
      this.$q.localStorage.set('lnbits.gradientBg', this.gradientChoice)
      if (this.$q.localStorage.getItem('lnbits.gradientBg')) {
        if (!this.$q.dark.isActive) {
          this.toggleDarkMode()
        }
        this.setColors()
        darkBgColor = this.$q.localStorage.getItem('lnbits.darkBgColor')
        primaryColor = this.$q.localStorage.getItem('lnbits.primaryColor')
        const gradientStyle = `linear-gradient(to bottom right, ${LNbits.utils.hexDarken(String(primaryColor), -70)}, #0a0a0a)`
        document.body.style.setProperty(
          'background-image',
          gradientStyle,
          'important'
        )
        const gradientStyleCards = `background-color: ${LNbits.utils.hexAlpha(String(darkBgColor), 0.55)} !important`
        const style = document.createElement('style')
        style.innerHTML = `
          body[data-theme="${this.$q.localStorage.getItem('lnbits.theme')}"] .q-card:not(.q-dialog .q-card, .lnbits__dialog-card, .q-dialog-plugin--dark),
          body.body${this.$q.dark.isActive ? '--dark' : ''} .q-header,
          body.body${this.$q.dark.isActive ? '--dark' : ''} .q-drawer,
          body.body${this.$q.dark.isActive ? '--dark' : ''} .q-tab-panels {
          ${gradientStyleCards}
          }

          body[data-theme="${this.$q.localStorage.getItem('lnbits.theme')}"].body--dark {
          background: ${LNbits.utils.hexDarken(String(primaryColor), -88)} !important;
          }

          [data-theme="${this.$q.localStorage.getItem('lnbits.theme')}"] .q-card--dark {
          background: ${String(darkBgColor)} !important;
          }
        `
        document.head.appendChild(style)
      }
    },
    applyBackgroundImage() {
      if (this.backgroundImage) {
        this.$q.localStorage.set('lnbits.backgroundImage', this.backgroundImage)
        this.gradientChoice = true
        this.applyGradient()
      }
      let bgImage = this.$q.localStorage.getItem('lnbits.backgroundImage')
      if (bgImage) {
        this.backgroundImage = bgImage
        const style = document.createElement('style')
        style.innerHTML = `
  body[data-theme="${this.$q.localStorage.getItem('lnbits.theme')}"]::before {
    content: '';
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: url(${bgImage});
    background-size: cover;
    filter: blur(8px);
    z-index: -1;
    background-position: center;
  background-repeat: no-repeat;
  background-size: cover;
  }

  body[data-theme="${this.$q.localStorage.getItem('lnbits.theme')}"] .q-page-container {
    backdrop-filter: none; /* Ensure the page content is not affected */
  }`
        document.head.appendChild(style)
      }
    },
    applyBorder() {
      if (this.borderChoice) {
        this.$q.localStorage.setItem('lnbits.border', this.borderChoice)
      }
      let borderStyle = this.$q.localStorage.getItem('lnbits.border')
      this.borderChoice = borderStyle
      let borderStyleCSS
      if (borderStyle == 'hard-border') {
        borderStyleCSS = `box-shadow: 0 0 0 1px rgba(0,0,0,.12), 0 0 0 1px #ffffff47; border: none;`
      }
      if (borderStyle == 'neon-border') {
        borderStyleCSS = `border: 2px solid ${this.$q.localStorage.getItem('lnbits.primaryColor')}; box-shadow: none;`
      }
      if (borderStyle == 'no-border') {
        borderStyleCSS = `box-shadow: none; border: none;`
      }
      if (borderStyle == 'retro-border') {
        borderStyleCSS = `border: none; border-color: rgba(255, 255, 255, 0.28); box-shadow: 0 1px 5px rgba(255, 255, 255, 0.2), 0 2px 2px rgba(255, 255, 255, 0.14), 0 3px 1px -2px rgba(255, 255, 255, 0.12);`
      }
      let style = document.createElement('style')
      style.innerHTML = `body[data-theme="${this.$q.localStorage.getItem('lnbits.theme')}"] .q-card.q-card--dark, .q-date--dark { ${borderStyleCSS} }`
      document.head.appendChild(style)
    },
    toggleGradient() {
      this.gradientChoice = !this.gradientChoice
      this.applyGradient()
      this.$q.localStorage.set('lnbits.backgroundImage', '')
      this.applyBorder()
      if (!this.gradientChoice) {
        window.location.reload()
      }
      this.gradientChoice = this.$q.localStorage.getItem('lnbits.gradientBg')
    },
    reactionChoiceFunc() {
      this.$q.localStorage.set('lnbits.reactions', this.reactionChoice)
    },
    backgroundImageFunc() {
      this.$q.localStorage.set('lnbits.backgroundImage', this.backgroundImage)
      this.applyBackgroundImage()
    },
    changeColor: function (newValue) {
      document.body.setAttribute('data-theme', newValue)
      this.$q.localStorage.set('lnbits.theme', newValue)
      this.setColors()
      this.applyGradient()
      this.applyBackgroundImage()
      this.applyBorder()
    },
    async updateAccount() {
      try {
        const {data} = await LNbits.api.request(
          'PUT',
          '/api/v1/auth/update',
          null,
          {
            user_id: this.user.id,
            username: this.user.username,
            email: this.user.email,
            extra: this.user.extra
          }
        )
        this.user = data
        this.hasUsername = !!data.username
        Quasar.Notify.create({
          type: 'positive',
          message: 'Account updated.'
        })
      } catch (e) {
        LNbits.utils.notifyApiError(e)
      }
    },
    disableUpdatePassword() {
      return (
        !this.credentialsData.newPassword ||
        !this.credentialsData.newPasswordRepeat ||
        this.credentialsData.newPassword !==
          this.credentialsData.newPasswordRepeat
      )
    },
    async updatePassword() {
      if (!this.credentialsData.username) {
        Quasar.Notify.create({
          type: 'warning',
          message: 'Please set a username.'
        })
        return
      }
      try {
        const {data} = await LNbits.api.request(
          'PUT',
          '/api/v1/auth/password',
          null,
          {
            user_id: this.user.id,
            username: this.credentialsData.username,
            password_old: this.credentialsData.oldPassword,
            password: this.credentialsData.newPassword,
            password_repeat: this.credentialsData.newPasswordRepeat
          }
        )
        this.user = data
        this.hasUsername = !!data.username
        this.credentialsData.show = false
        Quasar.Notify.create({
          type: 'positive',
          message: 'Password updated.'
        })
      } catch (e) {
        LNbits.utils.notifyApiError(e)
      }
    },
    async updatePubkey() {
      try {
        const {data} = await LNbits.api.request(
          'PUT',
          '/api/v1/auth/pubkey',
          null,
          {
            user_id: this.user.id,
            pubkey: this.credentialsData.pubkey
          }
        )
        this.user = data
        this.hasUsername = !!data.username
        this.credentialsData.show = false
        this.$q.notify({
          type: 'positive',
          message: 'Public key updated.'
        })
      } catch (e) {
        LNbits.utils.notifyApiError(e)
      }
    },
    showUpdateCredentials() {
      this.credentialsData = {
        show: true,
        oldPassword: null,
        username: this.user.username,
        pubkey: this.user.pubkey,
        newPassword: null,
        newPasswordRepeat: null
      }
    }
  },
  async created() {
    try {
      const {data} = await LNbits.api.getAuthenticatedUser()
      this.user = data
      this.hasUsername = !!data.username
      if (!this.user.extra) this.user.extra = {}
    } catch (e) {
      LNbits.utils.notifyApiError(e)
    }
    const hash = window.location.hash.replace('#', '')
    if (hash) {
      this.tab = hash
    }
    this.applyGradient()
    this.applyBackgroundImage()
    this.applyBorder()
  }
})
