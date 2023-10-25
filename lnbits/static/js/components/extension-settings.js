Vue.component('lnbits-extension-settings-form', {
  name: 'lnbits-extension-settings-form',
  props: ['options', 'adminkey', 'endpoint'],
  methods: {
    updateSettings: async function () {
      if (!this.settings) {
        return Quasar.plugins.Notify.create({
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
  template: `
    <q-form v-if="settings" @submit="updateSettings" class="q-gutter-md">
      <lnbits-dynamic-fields :options="options" v-model="settings"></lnbits-dynamic-fields>
      <div class="row q-mt-lg">
        <q-btn v-close-popup unelevated color="primary" type="submit">Update</q-btn>
        <q-btn v-close-popup unelevated color="danger" @click="resetSettings" >Reset</q-btn>
        <slot name="actions"></slot>
      </div>
    </q-form>
  `,
  data: function () {
    return {
      settings: undefined
    }
  }
})

Vue.component('lnbits-extension-settings-btn-dialog', {
  name: 'lnbits-extension-settings-btn-dialog',
  props: ['options', 'adminkey', 'endpoint'],
  template: `
    <q-btn v-if="options" unelevated @click="show = true" color="primary" icon="settings" class="float-right">
        <q-dialog v-model="show" position="top">
          <q-card class="q-pa-lg q-pt-xl lnbits__dialog-card">
            <lnbits-extension-settings-form :options="options" :adminkey="adminkey" :endpoint="endpoint">
                <template v-slot:actions>
                    <q-btn v-close-popup flat color="grey" class="q-ml-auto">Close</q-btn>
                </template>
            </lnbits-extension-settings-form>
          </q-card>
        </q-dialog>
    </q-btn>
  `,
  data: function () {
    return {
      show: false
    }
  }
})
