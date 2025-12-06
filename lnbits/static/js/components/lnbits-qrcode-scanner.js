window.app.component('lnbits-qrcode-scanner', {
  template: '#lnbits-qrcode-scanner',
  props: ['callback'],
  data() {
    return {
      showScanner: false
    }
  },
  watch: {
    callback(newVal) {
      if (newVal === null) {
        return this.reset()
      }
      if (typeof newVal !== 'function') {
        Quasar.Notify.create({
          message: 'QR code scanner callback is not a function.',
          type: 'negative'
        })
        return this.reset()
      }
      if (this.g.hasCamera === false) {
        Quasar.Notify.create({
          message: 'No camera found on this device.',
          type: 'negative'
        })
        return this.reset()
      }
      this.showScanner = true
    }
  },
  methods: {
    reset() {
      this.showScanner = false
      this.g.scanner = null
    },
    detect(val) {
      const rawValue = val[0].rawValue
      console.log('Detected QR code value:', rawValue)
      this.callback(rawValue)
      this.$emit('detect', rawValue)
      this.reset()
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
        this.reset()
      }
    }
  }
})
