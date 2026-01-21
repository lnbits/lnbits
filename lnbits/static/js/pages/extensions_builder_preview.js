window.PageExtensionBuilderPreview = {
  template: '#page-extension-builder-preview',
  mixins: [windowMixin],
  watch: {
    name: 'reload'
  },
  data() {
    return {
      extId: '',
      pageName: '',
      componentName: null
    }
  },
  methods: {
    async reload() {
      await LNbits.utils.loadTemplate(
        `/extensions/builder/preview/${this.extId}/template?page_name=${this.pageName}`
      )
      await LNbits.utils.loadScript(
        `/extensions/builder/preview/${this.extId}/component?page_name=${this.pageName}`
      )

      this._component = window[this.componentName]
      console.log(
        'LNbits preview reloaded componentName:',
        this.componentName,
        !!this._component
      )
      this.$forceUpdate()
    }
  },
  async created() {
    const urlParams = new URLSearchParams(window.location.search)
    this.extId = urlParams.get('ext_id') || ''
    this.pageName = urlParams.get('page') || ''
    this.componentName = urlParams.get('component') || ''

    await this.reload()
  },
  render() {
    if (this._component) {
      return Vue.h(this._component)
    }
    return Vue.h('div', 'Loading...')
  }
}
