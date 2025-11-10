window.app.component('lnbits-wallet-disclaimer', {
  mixins: [window.windowMixin],
  template: '#lnbits-wallet-disclaimer',
  data() {
    return {
      disclaimerDialog: {
        show: false,
        location: window.location
      }
    }
  },
  mounted() {
    if (!Quasar.LocalStorage.getItem('lnbits.disclaimerShown')) {
      this.disclaimerDialog.show = true
      Quasar.LocalStorage.setItem('lnbits.disclaimerShown', true)
      Quasar.LocalStorage.setItem('lnbits.reactions', 'confettiTop')
    }
  }
})
