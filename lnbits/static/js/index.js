/* global Vue, Quasar, LNbits, SITE_DESCRIPTION, windowMixin */
const app = Vue.createApp({
  mixins: [windowMixin],
  data: function () {
    return {
      disclaimerDialog: {
        show: false,
        data: {},
        description: ''
      },
      walletName: ''
    }
  },
  computed: {
    formatDescription() {
      return LNbits.utils.convertMarkdown(this.description)
    }
  },
  methods: {
    createWallet: function () {
      LNbits.api.createAccount(this.walletName).then(res => {
        window.location = '/wallet?usr=' + res.data.user + '&wal=' + res.data.id
      })
    },
    processing: function () {
      this.$q.notify({
        timeout: 0,
        message: 'Processing...',
        icon: null
      })
    }
  },
  created() {
    this.description = SITE_DESCRIPTION
  }
})

window.app = app
