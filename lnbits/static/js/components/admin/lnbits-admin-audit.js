window.app.component('lnbits-admin-audit', {
  props: ['form-data'],
  template: '#lnbits-admin-audit',
  mixins: [window.windowMixin],
  data() {
    return {
      formAddIncludePath: '',
      formAddExcludePath: '',
      formAddIncludeResponseCode: ''
    }
  },
  methods: {
    addIncludePath() {
      if (this.formAddIncludePath === '') {
        return
      }
      const paths = this.formData.lnbits_audit_include_paths
      if (!paths.includes(this.formAddIncludePath)) {
        this.formData.lnbits_audit_include_paths = [
          ...paths,
          this.formAddIncludePath
        ]
      }
      this.formAddIncludePath = ''
    },
    removeIncludePath(path) {
      this.formData.lnbits_audit_include_paths =
        this.formData.lnbits_audit_include_paths.filter(p => p !== path)
    },
    addExcludePath() {
      if (this.formAddExcludePath === '') {
        return
      }
      const paths = this.formData.lnbits_audit_exclude_paths
      if (!paths.includes(this.formAddExcludePath)) {
        this.formData.lnbits_audit_exclude_paths = [
          ...paths,
          this.formAddExcludePath
        ]
      }
      this.formAddExcludePath = ''
    },

    removeExcludePath(path) {
      this.formData.lnbits_audit_exclude_paths =
        this.formData.lnbits_audit_exclude_paths.filter(p => p !== path)
    },
    addIncludeResponseCode() {
      if (this.formAddIncludeResponseCode === '') {
        return
      }
      const codes = this.formData.lnbits_audit_http_response_codes
      if (!codes.includes(this.formAddIncludeResponseCode)) {
        this.formData.lnbits_audit_http_response_codes = [
          ...codes,
          this.formAddIncludeResponseCode
        ]
      }
      this.formAddIncludeResponseCode = ''
    },
    removeIncludeResponseCode(code) {
      this.formData.lnbits_audit_http_response_codes =
        this.formData.lnbits_audit_http_response_codes.filter(c => c !== code)
    }
  }
})
