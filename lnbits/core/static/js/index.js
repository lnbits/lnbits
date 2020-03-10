new Vue({
  el: '#vue',
  mixins: [windowMixin],
  data: function () {
    return {
      walletName: ''
    };
  },
  methods: {
    createWallet: function () {
      LNbits.href.createWallet(this.walletName);
    },
    processing: function () {
      this.$q.notify({
        timeout: 0,
        message: 'Processing...',
        icon: null
      });
    }
  }
});
