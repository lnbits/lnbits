
new Vue({
  el: '#vue',
  mixins: [windowMixin],
  data: function () {
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
      tab: 'user',
      passwordData: {
        show: false,
        oldPassword: null,
        newPassword: null,
        newPasswordRepeat: null
      }
    }
  },
  methods: {
    activeLanguage: function (lang) {
      return window.i18n.locale === lang
    },
    changeLanguage: function (newValue) {
      window.i18n.locale = newValue
      this.$q.localStorage.set('lnbits.lang', newValue)
    },
    toggleDarkMode: function () {
      this.$q.dark.toggle()
      this.$q.localStorage.set('lnbits.darkMode', this.$q.dark.isActive)
    },
    toggleGradient: async function () {
      // Toggle the gradient choice state
      this.gradientChoice = !this.gradientChoice;
      this.$q.localStorage.getItem('lnbits.gradientBg') || false
      if (this.gradientChoice) {
        const rgbPrimaryColor = LNbits.utils.hexToRgb(LNbits.utils.getPaletteColor('primary'))
        const gradientStyle = `linear-gradient(to bottom right, rgb(${rgbPrimaryColor.r * 0.5}, ${rgbPrimaryColor.g * 0.5}, ${rgbPrimaryColor.b * 0.5}), #0a0a0a)`;
        document.body.style.setProperty('background', gradientStyle, 'important');
      } else {
        document.body.style.removeProperty('background');
      }
    },
    reactionChoiceFunc: function () {
      this.$q.localStorage.set('lnbits.reactions', this.reactionChoice)
    },
    changeColor: function (newValue) {
      document.body.setAttribute('data-theme', newValue)
      this.$q.localStorage.set('lnbits.theme', newValue)
    },
    updateAccount: async function () {
      try {
        const {data} = await LNbits.api.request(
          'PUT',
          '/api/v1/auth/update',
          null,
          {
            user_id: this.user.id,
            username: this.user.username,
            email: this.user.email,
            config: this.user.config
          }
        )
        this.user = data
        this.$q.notify({
          type: 'positive',
          message: 'Account updated.'
        })
      } catch (e) {
        LNbits.utils.notifyApiError(e)
      }
    },
    updatePassword: async function () {
      if (!this.user.username) {
        this.$q.notify({
          type: 'warning',
          message: 'Please set a username first.'
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
            username: this.user.username,
            password_old: this.passwordData.oldPassword,
            password: this.passwordData.newPassword,
            password_repeat: this.passwordData.newPasswordRepeat
          }
        )
        this.user = data
        this.passwordData.show = false
        this.$q.notify({
          type: 'positive',
          message: 'Password updated.'
        })
      } catch (e) {
        LNbits.utils.notifyApiError(e)
      }
    },
    showChangePassword: function () {
      if (!this.user.username) {
        this.$q.notify({
          type: 'warning',
          message: 'Please set a username first.'
        })
        return
      }
      this.passwordData = {
        show: true,
        oldPassword: null,
        newPassword: null,
        newPasswordRepeat: null
      }
    }
  },
  created: async function () {
    try {
      const {data} = await LNbits.api.getAuthenticatedUser()
      this.user = data
      this.hasUsername = !!data.username
      if (!this.user.config) this.user.config = {}
    } catch (e) {
      LNbits.utils.notifyApiError(e)
    }
  }
})
