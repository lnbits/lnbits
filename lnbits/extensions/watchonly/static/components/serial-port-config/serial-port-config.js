async function serialPortConfig(path) {
  const t = await loadTemplateAsync(path)
  Vue.component('serial-port-config', {
    name: 'serial-port-config',
    template: t,
    data() {
      return {
        config: {
          baudRate: 9600,
          bufferSize: 255,
          dataBits: 8,
          flowControl: 'none',
          parity: 'none',
          stopBits: 1
        }
      }
    },
    methods: {
      getConfig: function () {
        return this.config
      }
    }
  })
}
