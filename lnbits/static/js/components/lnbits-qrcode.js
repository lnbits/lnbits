window.app.component('lnbits-qrcode', {
  mixins: [window.windowMixin],
  template: '#lnbits-qrcode',
  components: {
    QrcodeVue: QrcodeVue.default
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
    print: {
      type: Boolean,
      default: false
    },
    showButtons: {
      type: Boolean,
      default: true
    },
    href: {
      type: String,
      default: ''
    },
    margin: {
      type: Number,
      default: 3
    },
    maxWidth: {
      type: Number,
      default: 450
    },
    logo: {
      type: String,
      default: LNBITS_QR_LOGO
    }
  },
  data() {
    return {
      nfcTagWriting: false,
      nfcSupported: typeof NDEFReader != 'undefined'
    }
  },
  methods: {
    printQrCode() {
      const svg = this.$refs.qrCode.$el.outerHTML
      const printWindow = window.open('', '_blank')
      printWindow.document.write(`
        <html>
          <head>
            <title>Print QR Code</title>
            <style>
              body {
                display: flex;
                justify-content: center;
                align-items: center;
                height: 100vh;
                margin: 0;
              }
              img {
                position: absolute;
                max-width: 51px;
                width: 14%;
                overflow: hidden;
                background: #fff;
                overflow: hidden;
                padding: -1.2rem;
                border-radius: -1.2rem;
              }
            </style>
          </head>
          <body>${svg}<img src="${this.logo}"></body>
        </html>
      `)
      printWindow.document.close()
      printWindow.focus()
      printWindow.print()
      printWindow.close()
    },
    clickQrCode(event) {
      if (this.href === '') {
        this.utils.copyText(this.value)
        event.preventDefault()
        event.stopPropagation()
        return false
      }
    },
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
  mounted() {
    this.$refs.qrCode.$el.style.maxWidth = this.maxWidth + 'px'
    this.$refs.qrCode.$el.setAttribute('width', '100%')
    this.$refs.qrCode.$el.removeAttribute('height')
  }
})
