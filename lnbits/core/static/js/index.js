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
      savedUsers: null,
      showSavingOpts: null,
      locally: [],
      localSelection: ""
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
    },
    locallySelected: function () {
      console.log(this.localSelection)
      window.localStorage.setItem('lnbits.current.user', this.localSelection)
      window.location.href = "/wallet?usr=local";
    }
  },
  created: function () {
    let allowSaving = JSON.parse(window.localStorage.getItem('lnbits.saving'))
    userList = JSON.parse(window.localStorage.getItem('lnbits.users'))
    this.savingFormats = allowSaving.formats
    for (let i = 0; i < userList.length; i++) {
      this.locally[i] = userList[i].id
    }
    console.log(this.locally)
  }
})
