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
    options: Object
  },
  data() {
    return {
      custom: {
        margin: 3,
        width: 350,
        size: 350,
        logo: LNBITS_QR_LOGO
      }
    }
  },
  methods: {
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
