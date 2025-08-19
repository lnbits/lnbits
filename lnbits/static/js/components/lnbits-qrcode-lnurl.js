window.app.component('lnbits-funding-sources', {
  template: '#lnbits-qrcode-lnurl',
  mixins: [window.windowMixin],
  props: ['url'],
  methods: {
    setLnurl() {
      if (this.tab == 'bech32') {
        const bytes = new TextEncoder().encode(this.url)
        const bech32 = NostrTools.nip19.encodeBytes('lnurl', bytes)
        this.lnurl = `lightning:${bech32.toUpperCase()}`
      } else if (this.tab == 'lud17') {
        this.lnurl = this.url.replace('https://', 'lnurlp://')
      }
    }
  },
  watch: {
    url() {
      this.setLnurl()
    },
    tab() {
      this.setLnurl()
    }
  },
  data() {
    return {
      tab: 'bech32',
      lnurl: ''
    }
  }
})
