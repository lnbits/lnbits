window.app.component('lnbits-footer', {
  template: '#lnbits-footer',
  mixins: [window.windowMixin],
  computed: {
    version() {
      return this.LNBITS_VERSION || 'unknown version'
    },
    title() {
      return `${this.SITE_TITLE}, ${this.SITE_TAGLINE}`
    },
    showFooter() {
      return (
        this.SITE_TITLE == 'LNbits' &&
        this.LNBITS_SHOW_HOME_PAGE_ELEMENTS == true
      )
    }
  }
})
