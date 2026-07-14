window.app.component('lnbits-admin-blockexplorer', {
  props: ['form-data'],
  template: '#lnbits-admin-blockexplorer',
  data() {
    return {
      electrumServers: [
        'ssl://fulcrum.lnbits.com:50002',
        'ssl://mainnet.nunchuk.io:52002',
        'ssl://fulcrum.grey.pw:50002',
        'ssl://electrum2.bluewallet.io:443',
        'ssl://electrum.acinq.co:50002',
        'ssl://electrum.blockstream.info:50002',
        'ssl://bitcoin.mullvad.net:5010'
      ]
    }
  },
  computed: {
    electrumServerOptions() {
      return [...this.electrumServers, 'Custom']
    },
    electrumServerPreset: {
      get() {
        return this.electrumServers.includes(
          this.formData.lnbits_blockexplorer_electrum_url
        )
          ? this.formData.lnbits_blockexplorer_electrum_url
          : 'Custom'
      },
      set(value) {
        if (value === 'Custom') {
          if (this.electrumServerPreset !== 'Custom') {
            this.formData.lnbits_blockexplorer_electrum_url = ''
          }
          return
        }
        this.formData.lnbits_blockexplorer_electrum_url = value
      }
    }
  }
})
