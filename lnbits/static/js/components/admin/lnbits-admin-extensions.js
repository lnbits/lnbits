window.app.component('lnbits-admin-extensions', {
  props: ['form-data'],
  template: '#lnbits-admin-extensions',
  mixins: [window.windowMixin],
  data() {
    return {
      formAddExtensionsManifest: ''
    }
  },
  methods: {
    addExtensionsManifest() {
      const addManifest = this.formAddExtensionsManifest.trim()
      const manifests = this.formData.lnbits_extensions_manifests
      if (
        addManifest &&
        addManifest.length &&
        !manifests.includes(addManifest)
      ) {
        this.formData.lnbits_extensions_manifests = [...manifests, addManifest]
        this.formAddExtensionsManifest = ''
      }
    },
    removeExtensionsManifest(manifest) {
      const manifests = this.formData.lnbits_extensions_manifests
      this.formData.lnbits_extensions_manifests = manifests.filter(
        m => m !== manifest
      )
    }
  }
})
