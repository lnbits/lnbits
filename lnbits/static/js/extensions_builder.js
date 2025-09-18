window.ExtensionsBuilderPageLogic = {
  data: function () {
    return {
      step: 1,
      extensionDataCleanString: '',
      extensionData: {
        id: '',
        name: '',
        stub_version: '',
        short_description: '',
        description: '',
        public_page: {
          has_public_page: true,
          owner_data_fields: {
            name: '',
            description: ''
          },
          client_data_fields: {
            public_inputs: []
          },
          action_fields: {
            generate_action: true,
            wallet_id: '',
            currency: '',
            amount: ''
          }
        },
        settings_data: {
          name: 'Settings',
          enabled: true,
          type: 'user',
          fields: []
        },
        owner_data: {
          name: '',
          fields: []
        },
        client_data: {
          enabled: true,
          name: '',
          fields: []
        }
      },

      settingsTypes: [
        {label: 'User Settings', value: 'user'},
        {label: 'Admin Settings', value: 'admin'}
      ],
      extensionStubVersions: []
    }
  },

  methods: {
    nextStep() {
      this.$q.localStorage.set(
        'lnbits.extension.builder.data',
        JSON.stringify(this.extensionData)
      )
      this.$refs.stepper.next()
      console.log('### Next step', JSON.stringify(this.extensionData))
    },
    previousStep() {
      this.$refs.stepper.previous()
    },
    clearAllData() {
      LNbits.utils
        .confirmDialog(
          'Are you sure you want to clear all data? This action cannot be undone.'
        )
        .onOk(() => {
          this.extensionData = JSON.parse(this.extensionDataCleanString)
          this.$q.localStorage.remove('lnbits.extension.builder.data')
          this.$refs.stepper.set(1)
        })
    },
    exportJsonData() {
      const status = Quasar.exportFile(
        `${this.extensionData.id || 'data-export'}.json`,
        JSON.stringify(this.extensionData, null, 2),
        'text/json'
      )
      if (status !== true) {
        Quasar.Notify.create({
          message: 'Browser denied file download...',
          color: 'negative',
          icon: null
        })
      } else {
        Quasar.Notify.create({
          message: 'File downloaded!',
          color: 'positive',
          icon: 'file_download'
        })
      }
    },
    onJsonDataInput(event) {
      const file = event.target.files[0]
      console.log('### file', file)
      const reader = new FileReader()
      reader.onload = e => {
        this.extensionData = {
          ...this.extensionData,
          ...JSON.parse(e.target.result)
        }
        this.$refs.extensionDataInput.value = null
        Quasar.Notify.create({
          message: 'File loaded!',
          color: 'positive',
          icon: 'file_upload'
        })
      }
      reader.readAsText(file)
    },
    async buildExtension() {
      try {
        const {data} = await LNbits.api.request(
          'POST',
          '/api/v1/extension/builder',
          null,
          this.extensionData
        )

        console.log('### buildExtensions', data)
      } catch (error) {
        LNbits.utils.notifyApiError(error)
      }
    },
    async getStubExtensionReleases() {
      try {
        const stub_ext_id = 'extension_builder_stub'
        const {data} = await LNbits.api.request(
          'GET',
          `/api/v1/extension/${stub_ext_id}/releases`
        )

        this.extensionStubVersions = data.sort((a, b) =>
          a.version < b.version ? 1 : -1
        )
        this.extensionData.stub_version = this.extensionStubVersions[0]
          ? this.extensionStubVersions[0].version
          : ''
        console.log('### stub extension releases', this.extensionStubVersions)
      } catch (error) {
        LNbits.utils.notifyApiError(error)
      }
    }
  },
  created: function () {
    this.extensionDataCleanString = JSON.stringify(this.extensionData)
    const extensionData = this.$q.localStorage.getItem(
      'lnbits.extension.builder.data'
    )
    if (extensionData) {
      this.extensionData = {...this.extensionData, ...JSON.parse(extensionData)}
      console.log('### loaded extension data', this.extensionData)
    }
    this.getStubExtensionReleases()
  },
  mixins: [windowMixin]
}
