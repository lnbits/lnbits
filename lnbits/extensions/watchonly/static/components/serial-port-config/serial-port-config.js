async function serialPortConfig(path) {
  const t = await loadTemplateAsync(path)
  Vue.component('serial-port-config', {
    name: 'serial-port-config',
    props: ['config'],
    template: t,
    data() {
      return {}
    },
    methods: {}
  })
}
