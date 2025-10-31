window.app.component('lnbits-admin-funding', {
  props: ['is-super-user', 'form-data', 'settings'],
  template: '#lnbits-admin-funding',
  mixins: [window.windowMixin],
  data() {
    return {
      auditData: []
    }
  },
  created() {
    this.getAudit()
  },
  methods: {
    getAudit() {
      LNbits.api
        // TODO: should not use admin key here
        .request('GET', '/admin/api/v1/audit', this.g.user.wallets[0].adminkey)
        .then(response => {
          this.auditData = response.data
        })
        .catch(LNbits.utils.notifyApiError)
    }
  }
})
