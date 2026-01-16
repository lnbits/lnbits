window.app.component('lnbits-preview', {
  props: ['name', 'template', 'component'],
  watch: {
    name: 'reload'
  },
  methods: {
    async reload() {
      await LNbits.utils.loadTemplate(this.template)
      await LNbits.utils.loadScript(this.component)
      self._component = window[this.name]
      console.log(
        'LNbits preview reloaded component:',
        this.name,
        self._component
      )
      this.$forceUpdate()
    }
  },
  async created() {
    await this.reload()
  },
  render() {
    if (self._component) {
      return Vue.h(self._component)
    }
    return Vue.h('div', 'Loading...')
  }
})
