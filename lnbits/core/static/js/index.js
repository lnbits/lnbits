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
      isOwner: false,
      adminPassword: ''
    }
  },
  methods: {
    createWallet: function () {
      LNbits.href.createWallet(this.walletName, undefined, this.adminPassword)
    },
    processing: function () {
      this.$q.notify({
        timeout: 0,
        message: 'Processing...',
        icon: null
      })
    }
  }
})
