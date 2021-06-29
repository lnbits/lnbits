new Vue({
  el: '#vue',
  mixins: [windowMixin],
  data: function () {
    return {
      disclaimerDialog: {
        show: false,
        data: {}
      },
      walletName: '',
      savingFormats: null,
      savedUsers: null
    }
  },
  methods: {
    createWallet: function () {
      LNbits.href.createWallet(this.walletName)
    },
    processing: function () {
      this.$q.notify({
        timeout: 0,
        message: 'Processing...',
        icon: null
      })
    }
  },
  mounted: function () {
    let allowSaving = JSON.parse(window.localStorage.getItem('lnbits.saving'))
    let users = JSON.parse(window.localStorage.getItem('lnbits.users'))
    if (allowSaving) {
      this.savingFormats = allowSaving.formats
      this.savedUsers = users
    }
  }
})
