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
    }
  }
});
