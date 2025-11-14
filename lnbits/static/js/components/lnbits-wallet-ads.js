window.app.component('lnbits-wallet-ads', {
  template: '#lnbits-wallet-ads',
  mixins: [window.windowMixin],
  computed: {
    ads() {
      return this.AD_SPACE.map(ad => ad.split(';'))
    },
    adSpaceTitle() {
      return this.AD_SPACE_TITLE || 'Sponsored Ads'
    },
    adSpaceEnabled() {
      return this.AD_SPACE_ENABLED && this.AD_SPACE && this.AD_SPACE.length > 0
    }
  }
})
