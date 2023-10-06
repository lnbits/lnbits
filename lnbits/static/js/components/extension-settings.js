Vue.component('extension-settings', {
  name: 'extension-settings',
  props: ['settings-data', 'settings-endpoint', 'adminkey'],
  data: function () {
    return {
      internalSettings: {},
      show: false
    }
  },

  computed: {
    settings: {
      get() {
        return this.internalSettings
      },
      set(value) {
        value.isLoaded = true
        this.internalSettings = JSON.parse(JSON.stringify(value))
        // this.$emit(
        //   'update:settings-data',
        //   JSON.parse(JSON.stringify(this.internalSettings))
        // )
      }
    }
  },
  methods: {
    updateSettings: async function () {
      try {
        const {data} = await LNbits.api.request(
          'PUT',
          this.settingsEndpoint,
          this.adminkey,
          this.settings
        )
        this.show = false
        this.settings = data
      } catch (error) {
        LNbits.utils.notifyApiError(error)
      }
    },
    getSettings: async function () {
      try {
        const {data} = await LNbits.api.request(
          'GET',
          this.settingsEndpoint,
          this.adminkey
        )
        this.settings = data
      } catch (error) {
        LNbits.utils.notifyApiError(error)
      }
    },
    resetSettings: async function () {
      try {
        const {data} = await LNbits.api.request(
          'DELETE',
          this.settingsEndpoint,
          this.adminkey
        )
        this.settings = data
      } catch (error) {
        LNbits.utils.notifyApiError(error)
      }
    }
  },
  created: async function () {
    await this.getSettings()
  },
  template: `
      <div class="extension-settings">
        <q-card>
          <div class="row items-center no-wrap q-mb-md q-pt-sm q-pb-sm">
            <div class="col-lg-2 col-sm-3 q-ml-lg">
              <q-btn unelevated @click="show = true" color="primary" icon="settings">
              </q-btn>
            </div>
          </div>
        </q-card>
        <q-dialog v-model="show" position="top">
          <q-card class="q-pa-lg q-pt-xl lnbits__dialog-card">
            <q-form @submit="updateSettings" class="q-gutter-md">
              <q-slot name="formDialog"></q-slot>
              <div class="row q-mt-lg">
                <q-btn unelevated color="primary" type="submit">Update</q-btn>
                <q-btn unelevated color="danger" @click="resetSettings" >Reset</q-btn>
                <q-btn v-close-popup flat color="grey" class="q-ml-auto">Cancel</q-btn>
              </div>
            </q-form>
          </q-card>
        </q-dialog>
      </div>
  `
})
