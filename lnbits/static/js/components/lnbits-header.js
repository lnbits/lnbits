window.app.component('lnbits-header', {
  template: '#lnbits-header',
  mixins: [window.windowMixin],
  computed: {
    hasServiceFeeMax() {
      return (
        this.g.user &&
        this.LNBITS_SERVICE_FEE_MAX &&
        this.LNBITS_SERVICE_FEE_MAX > 0
      )
    },
    serviceFeeMax() {
      return this.LNBITS_SERVICE_FEE_MAX || 0
    },
    hasServiceFee() {
      return (
        this.g.user && this.LNBITS_SERVICE_FEE && this.LNBITS_SERVICE_FEE > 0
      )
    },
    serviceFee() {
      return this.LNBITS_SERVICE_FEE || 0
    },
    hasCustomBadge() {
      return this.LNBITS_CUSTOM_BADGE && this.LNBITS_CUSTOM_BADGE != ''
    },
    customBadge() {
      return this.LNBITS_CUSTOM_BADGE || ''
    },
    customBadgeColor() {
      return this.LNBITS_CUSTOM_BADGE_COLOR || ''
    },
    title() {
      return this.SITE_TITLE
    },
    titleIsLnbits() {
      return this.SITE_TITLE == 'LNbits'
    },
    customLogoUrl() {
      return this.USE_CUSTOM_LOGO || null
    },
    showAdmin() {
      return this.g.user && (this.g.user.super_user || this.g.user.admin)
    },
    showVoidwallet() {
      return this.g.user && this.VOIDWALLET == true
    },
    displayName() {
      return (
        this.g.user?.extra?.display_name ||
        this.g.user.username ||
        this.g.user?.extra?.first_name ||
        'Anon'
      )
    },
    displayRole() {
      if (this.g.user?.super_user) {
        return 'Super User'
      } else if (this.g.user?.admin) {
        return 'Admin'
      } else {
        return 'User'
      }
    }
  }
})
