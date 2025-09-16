window.ExtensionsBuilderPageLogic = {
  data: function () {
    return {
      step: 5,
      extensionData: {
        id: '',
        name: '',
        short_description: '',
        description: '',
        generate: {
          settings: true,
          owner: true,
          customer: true
        },
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

        settingsType: 'user',
        settingsFields: [],
        owner_data: {
          name: '',
          fields: []
        },

        client_data: {
          name: '',
          fields: []
        }
      },

      settingsTypes: [
        {label: 'User Settings', value: 'user'},
        {label: 'Admin Settings', value: 'admin'}
      ]
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
    }
  },
  created: function () {
    const extensionData = this.$q.localStorage.getItem(
      'lnbits.extension.builder.data'
    )
    if (extensionData) {
      this.extensionData = JSON.parse(extensionData)
    }
  },
  mixins: [windowMixin]
}
