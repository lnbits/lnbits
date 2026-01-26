window.app.component('lnbits-footer', {
  template: '#lnbits-footer',
  computed: {
    title() {
      return `${this.g.settings.siteTile}, ${this.g.settings.siteTagline}`
    },
    version() {
      return this.$t('lnbits_version') + ': ' + this.g.settings.version
    }
  }
})
