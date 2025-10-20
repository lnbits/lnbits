window.app.component('lnbits-qrcode-lnurl', {
  template: '#lnbits-qrcode-lnurl',
  mixins: [window.windowMixin],
  props: {
    url: {
      required: true,
      type: String
    },
    prefix: {
      type: String,
      default: 'lnurlp'
    }
  },
  data() {
    return {
      tab: 'bech32',
      lnurl: ''
    }
  },
  methods: {
    setLnurl() {
      if (this.tab == 'bech32') {
        const bytes = new TextEncoder().encode(this.url)
        const bech32 = NostrTools.nip19.encodeBytes('lnurl', bytes)
        this.lnurl = `lightning:${bech32.toUpperCase()}`
      } else if (this.tab == 'lud17') {
        if (this.url.startsWith('http://')) {
          this.lnurl = this.url.replace('http://', this.prefix + '://')
        } else {
          this.lnurl = this.url.replace('https://', this.prefix + '://')
        }
      }
      this.$emit('update:lnurl', this.lnurl)
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
  created() {
    this.setLnurl()
  }
})
