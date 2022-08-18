async function initMyCheckbox(path) {
  const t = await loadTemplateAsync(path)
  Vue.component('my-checkbox', {
    name: 'my-checkbox',
    template: t,
    data() {
      return {checked: false, title: 'Check me'}
    },
    methods: {
      check() {
        this.checked = !this.checked
        console.log('### checked', this.checked)
      }
    }
  })
}
