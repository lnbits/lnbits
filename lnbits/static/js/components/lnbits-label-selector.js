window.app.component('lnbits-label-selector', {
  template: '#lnbits-label-selector',
  props: ['labels'],
  mixins: [window.windowMixin],
  data() {
    return {
      labelFilter: ''
    }
  },

  methods: {
    toggleLabel(label) {
      const hasLabel = this.labels.includes(label.name)

      if (hasLabel) {
        const index = this.labels.indexOf(label.name)
        if (index !== -1) {
          this.labels.splice(index, 1)
        }
      } else {
        this.labels.push(label.name)
      }
    },
    saveLabels() {
      this.$emit('update:labels', this.labels)
    }
  }
})
