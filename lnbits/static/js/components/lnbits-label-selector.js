window.app.component('lnbits-label-selector', {
  template: '#lnbits-label-selector',
  props: ['labels'],
  mixins: [window.windowMixin],
  data() {
    return {
      labelFilter: '',
      localLabels: []
    }
  },

  methods: {
    toggleLabel(label) {
      const hasLabel = this.localLabels.includes(label.name)

      if (hasLabel) {
        const index = this.localLabels.indexOf(label.name)
        if (index !== -1) {
          this.localLabels.splice(index, 1)
        }
      } else {
        this.localLabels.push(label.name)
      }
    },
    saveLabels() {
      this.$emit('update:labels', this.localLabels)
    },
    clearLabels() {
      this.localLabels = []
      this.saveLabels()
    }
  },
  created() {
    this.localLabels = [...this.labels]
  }
})
