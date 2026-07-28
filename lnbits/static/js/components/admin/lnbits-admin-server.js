window.app.component('lnbits-admin-server', {
  props: ['form-data'],
  template: '#lnbits-admin-server',
  computed: {
    lightningAddressBlacklistText: {
      get() {
        const value = this.formData.lnbits_wallet_lightning_address_blacklist
        return Array.isArray(value) ? value.join('\n') : value || ''
      },
      set(value) {
        this.formData.lnbits_wallet_lightning_address_blacklist = value
          .split(/[\n,]/)
          .map(word => word.trim().toLowerCase())
          .filter(word => word.length)
      }
    }
  }
})
