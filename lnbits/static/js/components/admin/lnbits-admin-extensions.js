window.app.component('lnbits-admin-extensions', {
  props: ['form-data'],
  template: '#lnbits-admin-extensions',
  data() {
    return {
      formAddExtensionsManifest: '',
      formAddWasmManifest: ''
    }
  },
  methods: {
    addExtensionsManifest() {
      this.addManifest(
        'lnbits_extensions_manifests',
        'formAddExtensionsManifest'
      )
    },
    addWasmManifest() {
      this.addManifest(
        'lnbits_wasm_extensions_manifests',
        'formAddWasmManifest'
      )
    },
    addManifest(manifestField, inputField) {
      const addManifest = this[inputField].trim()
      const manifests = this.formData[manifestField] || []
      if (
        addManifest &&
        addManifest.length &&
        !manifests.includes(addManifest)
      ) {
        this.formData[manifestField] = [...manifests, addManifest]
        this[inputField] = ''
      }
    },
    removeExtensionsManifest(manifest) {
      this.removeManifest('lnbits_extensions_manifests', manifest)
    },
    removeWasmManifest(manifest) {
      this.removeManifest('lnbits_wasm_extensions_manifests', manifest)
    },
    removeManifest(manifestField, manifest) {
      const manifests = this.formData[manifestField] || []
      this.formData[manifestField] = manifests.filter(m => m !== manifest)
    }
  }
})
