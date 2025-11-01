window.app.component('lnbits-wallet-header', {
  mixins: [window.windowMixin],
  template: '#lnbits-wallet-header',
  methods: {
    closeCamera() {
      this.parse.camera.show = false
    },
    showCamera() {
      this.parse.camera.show = true
    },
    async onCameraInitQR(promise) {
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
        this.parse.camera.show = false
        Quasar.Notify.create({
          message: camera_error,
          type: 'negative'
        })
      }
    }
  }
})
