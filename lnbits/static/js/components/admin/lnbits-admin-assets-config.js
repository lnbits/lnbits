window.app.component('lnbits-admin-assets-config', {
  props: ['form-data'],
  template: '#lnbits-admin-assets-config',
  mixins: [window.windowMixin],
  data() {
    return {
      newAllowedAssetMimeType: '',
      newNoLimitUser: ''
    }
  },
  async created() {},
  methods: {
    addAllowedAssetMimeType() {
      if (this.newAllowedAssetMimeType) {
        this.removeAllowedAssetMimeType(this.newAllowedAssetMimeType)
        this.formData.lnbits_assets_allowed_mime_types.push(
          this.newAllowedAssetMimeType
        )
        this.newAllowedAssetMimeType = ''
      }
    },
    removeAllowedAssetMimeType(type) {
      const index = this.formData.lnbits_assets_allowed_mime_types.indexOf(type)
      if (index !== -1) {
        this.formData.lnbits_assets_allowed_mime_types.splice(index, 1)
      }
    },
    addNewNoLimitUser() {
      if (this.newNoLimitUser) {
        this.removeNoLimitUser(this.newNoLimitUser)
        this.formData.lnbits_assets_no_limit_users.push(this.newNoLimitUser)
        this.newNoLimitUser = ''
      }
    },
    removeNoLimitUser(user) {
      if (user) {
        this.formData.lnbits_assets_no_limit_users =
          this.formData.lnbits_assets_no_limit_users.filter(u => u !== user)
      }
    }
  }
})
