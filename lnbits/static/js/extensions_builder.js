window.ExtensionsBuilderPageLogic = {
  data: function () {
    return {
      step: 1,
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
    const extensionData = this.$q.localStorage.getItem(
      'lnbits.extension.builder.data'
    )
    if (extensionData) {
      this.extensionData = JSON.parse(extensionData)
    }
    this.getStubExtensionReleases()
  },
  mixins: [windowMixin]
}
