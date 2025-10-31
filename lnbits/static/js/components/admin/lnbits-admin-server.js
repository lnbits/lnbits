window.app.component('lnbits-admin-server', {
  props: ['form-data'],
  template: '#lnbits-admin-server',
  mixins: [window.windowMixin],
  data() {
    return {
      currencies: []
    }
  },
  async created() {
    this.currencies = await LNbits.api.getCurrencies()
  }
})
