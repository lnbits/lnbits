Vue.component('lnbits-extension-settings-form', {
  name: 'lnbits-extension-settings-form',
  props: ['options', 'name', 'cancel'],
  data: function () {
    return {
      settings: undefined,
      usr: undefined,
      admin: false
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
          this.settings
        )
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
        await this.getSettings()
      } catch (error) {
        LNbits.utils.notifyApiError(error)
      }
    }
  },
  created: async function () {
    if (window.user.admin) {
      this.admin = true
      this.usr = window.user.id
      this.getSettings()
    }
  },
  template: `
    <q-form v-if="admin && settings" @submit="updateSettings" class="q-gutter-md">
      <lnbits-dynamic-fields :options="options" v-model="settings"></lnbits-dynamic-fields>
      <div class="row q-mt-lg">
        <q-btn v-close-popup unelevated color="primary" type="submit">Update</q-btn>
        <q-btn v-close-popup unelevated color="danger" @click="resetSettings" >Reset</q-btn>
        <q-btn v-if="cancel" v-close-popup flat color="grey" class="q-ml-auto">Cancel</q-btn>
      </div>
    </q-form>
  `
})

Vue.component('lnbits-extension-settings-btn-dialog', {
  name: 'lnbits-extension-settings-btn-dialog',
  props: ['options', 'name'],
  data: function () {
    return {
      admin: false,
      show: false
    }
  },
  created: async function () {
    if (window.user.admin) {
      this.admin = true
    }
  },
  template: `
    <q-btn v-if="admin && options" unelevated @click="show = true" color="primary" icon="settings" class="float-right">
        <q-dialog v-model="show" position="top">
          <q-card class="q-pa-lg q-pt-xl lnbits__dialog-card">
            <lnbits-extension-settings-form :options="options" :name="name" :cancel="true" />
          </q-card>
        </q-dialog>
    </q-btn>
  `
})

Vue.component('lnbits-extension-settings-tab-accordion', {
  name: 'lnbits-extension-settings-tab-accordion',
  props: ['options', 'name'],
  data: function () {
    return {
      admin: false
    }
  },
  created: async function () {
    if (window.user.admin) {
      this.admin = true
    }
  },
  template: `
    <q-expansion-item
      v-if="admin && options"
      icon="settings"
      label="Extension Settings"
    >
      <q-card-section>
        <lnbits-extension-settings-form :options="options" :name="name" />
      </q-card-section>
    </q-expansion-item>
  `
})
