async function walletConfig(path) {
  const t = await loadTemplateAsync(path)
  Vue.component('wallet-config', {
    name: 'wallet-config',
    template: t,

    props: ['total', 'config', 'adminkey'],
    data: function () {
      return {}
    },

    methods: {
      satBtc(val, showUnit = true) {
        return satOrBtc(val, showUnit, this.config.data.sats_denominated)
      },
      updateConfig: async function () {
        // const wallet = this.g.user.wallets[0]
        try {
          await LNbits.api.request(
            'PUT',
            '/watchonly/api/v1/config',
            this.adminkey,
            this.config.data
          )
          this.config.show = false
        } catch (error) {
          LNbits.utils.notifyApiError(error)
        }
      },
      getConfig: async function () {
        try {
          const {data} = await LNbits.api.request(
            'GET',
            '/watchonly/api/v1/config',
            this.adminkey
          )
          this.config.data = data
        } catch (error) {
          LNbits.utils.notifyApiError(error)
        }
      }
    },
    created: async function () {
        await this.getConfig()
    }
  })
}
