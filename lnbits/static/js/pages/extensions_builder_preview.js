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
      component: null
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
      self._component = window[this.component]
      console.log(
        'LNbits preview reloaded component:',
        self.component,
        !!self._component
      )
      this.$forceUpdate()
    }
  },
  async created() {
    const urlParams = new URLSearchParams(window.location.search)
    this.extId = urlParams.get('ext_id') || ''
    this.pageName = urlParams.get('page') || ''
    this.component = urlParams.get('component') || ''

    console.log(
      '### Preview params',
      this.extId,
      ':',
      this.pageName,
      ':',
      this.component
    ) // --- IGNORE ---
    await this.reload()
  },
  render() {
    if (self._component) {
      return Vue.h(self._component)
    }
    return Vue.h('div', 'Loading...')
  }
}
