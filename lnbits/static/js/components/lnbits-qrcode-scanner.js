window.app.component('lnbits-qrcode-scanner', {
  template: '#lnbits-qrcode-scanner',
  mixins: [window.windowMixin],
  watch: {
    'g.showScanner'(newVal) {
      if (newVal === true) {
        if (this.g.hasCamera === false) {
          Quasar.Notify.create({
            message: 'No camera found on this device.',
            type: 'negative'
          })
          this.g.showScanner = false
        }
      }
    }
  },
  methods: {
    detect(val) {
      const rawValue = val[0].rawValue
      console.log('Detected QR code value:', rawValue)
      this.$emit('detect', rawValue)
      this.g.showScanner = false
    },
    async onInitQR(promise) {
      try {
        await promise
      } catch (error) {
        const mapping = {
          NotAllowedError: 'ERROR: you need to grant camera access permission',
          NotFoundError: 'ERROR: no camera on this device',
          NotSupportedError:
            'ERROR: secure context required (HTTPS, localhost)',
          NotReadableError: 'ERROR: is the camera already in use?',
          OverconstrainedError: 'ERROR: installed cameras are not suitable',
          StreamApiNotSupportedError:
            'ERROR: Stream API is not supported in this browser',
          InsecureContextError:
            'ERROR: Camera access is only permitted in secure context. Use HTTPS or localhost rather than HTTP.'
        }
        const valid_error = Object.keys(mapping).filter(key => {
          return error.name === key
        })
        const camera_error = valid_error
          ? mapping[valid_error]
          : `ERROR: Camera error (${error.name})`
        Quasar.Notify.create({
          message: camera_error,
          type: 'negative'
        })
        this.g.hasCamera = false
        this.showScanner = false
      }
    }
  }
})
