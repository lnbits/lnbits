window.ExtensionsBuilderPageLogic = {
  data: function () {
    return {
      step: 0,
      settingsTypes: [
        {label: 'User Settings', value: 'user'},
        {label: 'Admin Settings', value: 'admin'}
      ],
      generate: {
        settings: true,
        owner: true,
        customer: true,
        publicPages: true
      },

      settingsType: 'user',
      settingsFields: [],
      ownerFields: [
        {
          name: 'created_at',
          type: 'datetime',
          label: 'Created At',
          hint: 'The date and time when the record was created.',
          optional: false,
          sortable: true,
          searchable: true,
          readonly: true,
          fields: []
        },
        {
          name: 'updated_at',
          type: 'datetime',
          label: 'Updated At',
          hint: 'The date and time when the record was last updated.',
          optional: false,
          sortable: true,
          searchable: true,
          readonly: true,
          fields: []
        },

        {
          name: 'extra',
          type: 'json',
          label: 'Extra Data',
          hint: 'This data is not searchable. But adding data fields here does not require a database migration.',
          optional: false,
          sortable: true,
          searchable: true,
          readonly: true,
          fields: [] // For nested fields in JSON type
        }
      ],
      customerFields: []
    }
  },

  methods: {},
  created: function () {
    this.customerFields = JSON.parse(JSON.stringify(this.ownerFields))
  },
  mixins: [windowMixin]
}
