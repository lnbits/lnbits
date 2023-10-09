Vue.component('extension-settings', {
  name: 'extension-settings',
  props: ['options', 'name'],
  data: function () {
    return {
      settings: undefined,
      usr: undefined,
      admin: false,
      show: false
    }
  },
  methods: {
    endpoint: function () {
      return `/${this.name}/api/v1/settings?usr=${this.usr}`
    },
    updateSettings: async function () {
      try {
        const {data} = await LNbits.api.request(
          'PUT',
          this.endpoint(),
          null,
          this.interalSettings
        )
        this.show = false
        this.settings = data
      } catch (error) {
        LNbits.utils.notifyApiError(error)
      }
    },
    getSettings: async function () {
      try {
        const {data} = await LNbits.api.request('GET', this.endpoint())
        this.settings = data
      } catch (error) {
        LNbits.utils.notifyApiError(error)
      }
    },
    resetSettings: async function () {
      try {
        await LNbits.api.request('DELETE', this.endpoint())
        this.getSettings()
      } catch (error) {
        LNbits.utils.notifyApiError(error)
      }
    }
  },
  created: async function () {
    if (window.user.admin) {
      this.admin = true
      this.usr = window.user.id
      await this.getSettings()
    }
  },
  template: `
    <q-btn v-if="admin && settings" unelevated @click="show = true" color="primary" icon="settings" class="float-right">
        <q-dialog v-model="show" position="top">
          <q-card class="q-pa-lg q-pt-xl lnbits__dialog-card">
            <q-form @submit="updateSettings" class="q-gutter-md">
              <lnbits-dynamic-fields :options="options" v-model="settings"></lnbits-dynamic-fields>
              <div class="row q-mt-lg">
                <q-btn unelevated color="primary" type="submit">Update</q-btn>
                <q-btn unelevated color="danger" @click="resetSettings" >Reset</q-btn>
                <q-btn v-close-popup flat color="grey" class="q-ml-auto">Cancel</q-btn>
              </div>
            </q-form>
          </q-card>
        </q-dialog>
    </q-btn>
  `
})
