window.app.component('lnbits-extension-settings-form', {
  name: 'lnbits-extension-settings-form',
  template: '#lnbits-extension-settings-form',
  props: ['options', 'adminkey', 'endpoint'],
  methods: {
    async updateSettings() {
      if (!this.settings) {
        return Quasar.Notify.create({
          message: 'No settings to update',
          type: 'negative'
        })
      }
      try {
        const {data} = await LNbits.api.request(
          'PUT',
          this.endpoint,
          this.adminkey,
          this.settings
        )
        this.settings = data
      } catch (error) {
        LNbits.utils.notifyApiError(error)
      }
    },
    getSettings: async function () {
      try {
        const {data} = await LNbits.api.request(
          'GET',
          this.endpoint,
          this.adminkey
        )
        this.settings = data
      } catch (error) {
        LNbits.utils.notifyApiError(error)
      }
    },
    resetSettings: async function () {
      LNbits.utils
        .confirmDialog('Are you sure you want to reset the settings?')
        .onOk(async () => {
          try {
            await LNbits.api.request('DELETE', this.endpoint, this.adminkey)
            await this.getSettings()
          } catch (error) {
            LNbits.utils.notifyApiError(error)
          }
        })
    }
  },
  created: async function () {
    await this.getSettings()
  },
  data: function () {
    return {
      settings: undefined
    }
  }
})

window.app.component('lnbits-extension-settings-btn-dialog', {
  template: '#lnbits-extension-settings-btn-dialog',
  name: 'lnbits-extension-settings-btn-dialog',
  props: ['options', 'adminkey', 'endpoint'],
  data: function () {
    return {
      show: false
    }
  }
})
