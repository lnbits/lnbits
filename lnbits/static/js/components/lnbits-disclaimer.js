window.app.component('lnbits-disclaimer', {
  template: '#lnbits-disclaimer',
  computed: {
    showDisclaimer() {
      return !g.disclaimerShown && g.isUserAuthorized
    }
  }
})
