window.app.component('lnbits-qrcode', {
  mixins: [window.windowMixin],
  template: '#lnbits-qrcode',
  components: {
    QrcodeVue
  },
  props: {
    value: {
      type: String,
      required: true
    },
    nfc: {
      type: Boolean,
      default: false
    },
    options: Object
  },
  data() {
    return {
      nfcTagWriting: false,
      nfcSupported: typeof NDEFReader != 'undefined',
      custom: {
        margin: 3,
        width: 350,
        size: 350,
        logo: LNBITS_QR_LOGO
      }
    }
  },
  methods: {
    async writeNfcTag() {
      try {
        if (!this.nfcSupported) {
          throw {
            toString: function () {
              return 'NFC not supported on this device or browser.'
            }
          }
        }

        const ndef = new NDEFReader()

        this.nfcTagWriting = true
        this.$q.notify({
          message: 'Tap your NFC tag to write the LNURL-withdraw link to it.'
        })

        await ndef.write({
          records: [{recordType: 'url', data: this.value, lang: 'en'}]
        })

        this.nfcTagWriting = false
        this.$q.notify({
          type: 'positive',
          message: 'NFC tag written successfully.'
        })
      } catch (error) {
        this.nfcTagWriting = false
        this.$q.notify({
          type: 'negative',
          message: error
            ? error.toString()
            : 'An unexpected error has occurred.'
        })
      }
    },
    downloadSVG() {
      const filename = 'qrcode.svg'
      const svg = this.$refs.qrCode.$el
      if (!svg) {
        console.error('SVG element not found')
        return
      }

      // Serialize the SVG content
      const serializer = new XMLSerializer()
      let source = serializer.serializeToString(svg)

      // Add SVG namespace if not present
      if (!source.match(/^<svg[^>]+xmlns="http:\/\/www\.w3\.org\/2000\/svg"/)) {
        source = source.replace(
          /^<svg/,
          '<svg xmlns="http://www.w3.org/2000/svg"'
        )
      }

      // Add XML declaration
      source = '<?xml version="1.0" standalone="no"?>\n' + source

      // Convert to Blob and trigger download
      const blob = new Blob([source], {type: 'image/svg+xml;charset=utf-8'})
      const url = URL.createObjectURL(blob)

      const link = document.createElement('a')
      link.href = url
      link.download = filename
      document.body.appendChild(link)
      link.click()

      // Cleanup
      document.body.removeChild(link)
      URL.revokeObjectURL(url)
    }
  },
  created() {
    this.custom = {...this.custom, ...this.options}
  }
})
