window.ExtensionsBuilderPageLogic = {
  data: function () {
    return {
      step: 0,
      isUserSettings: true,
      fields: [
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
      ]
    }
  },

  methods: {},
  created: function () {},
  mixins: [windowMixin]
}
