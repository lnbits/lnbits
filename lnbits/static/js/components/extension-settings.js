Vue.component('extension-settings', {
  name: 'extension-settings',
  props: ['settings-data', 'settings-endpoint'],
  data: function () {
    return {
      interalSettings: this.settingsData,
      usr: undefined,
      admin: false,
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
        this.$emit(
          'update:settings-data',
          JSON.parse(JSON.stringify(this.internalSettings))
        )
      }
    }
  },
  methods: {
    updateSettings: async function () {
      try {
        const {data} = await LNbits.api.request(
          'PUT',
          this.settingsEndpoint + '?usr=' + window.user.id,
          null,
          this.interalSettings
        )
        this.show = false
        this.interalSettings = data
      } catch (error) {
        LNbits.utils.notifyApiError(error)
      }
    },
    getSettings: async function () {
      try {
        const {data} = await LNbits.api.request(
          'GET',
          this.settingsEndpoint + '?usr=' + this.usr
        )
        this.interalSettings = data
      } catch (error) {
        LNbits.utils.notifyApiError(error)
      }
    },
    resetSettings: async function () {
      try {
        await LNbits.api.request(
          'DELETE',
          this.settingsEndpoint + '?usr=' + this.usr
        )
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
    <q-btn v-if="admin" unelevated @click="show = true" color="primary" icon="settings" class="float-right">
        <q-dialog v-model="show" position="top">
          <q-card class="q-pa-lg q-pt-xl lnbits__dialog-card">
            <q-form @submit="updateSettings" class="q-gutter-md">
              <slot v-bind:settings="settings"></slot>
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
