window.app.component('lnbits-disclaimer', {
  template: '#lnbits-disclaimer',
  mixins: [window.windowMixin],
  computed: {
    showDisclaimer() {
      return !g.disclaimerShown && g.isUserAuthorized
    }
  }
})
