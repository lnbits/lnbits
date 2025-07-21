window.ExtensionsBuilderPageLogic = {
  data: function () {
    return {
      step: 0,
      isUserSettings: true,
      fields: [],
      fieldTypes: [
        {label: 'Text', value: 'text'},
        {label: 'Integer', value: 'int'},
        {label: 'Float', value: 'float'},
        {label: 'Boolean', value: 'boolean'},
        {label: 'Date Time', value: 'datetime'},
        {label: 'Wallet Select', value: 'wallet'},
        {label: 'Currency Select', value: 'currency'}
      ],
      fieldsTable: {
        columns: [
          {
            name: 'name',
            align: 'left',
            label: 'Field Name',
            field: 'name',
            sortable: true
          },
          {
            name: 'type',
            align: 'left',
            label: 'Type',
            field: 'type',
            sortable: false
          },
          {
            name: 'label',
            align: 'left',
            label: 'UI Label',
            field: 'label',
            sortable: true
          },

          {
            name: 'hint',
            align: 'left',
            label: 'UI Hint',
            field: 'hint',
            sortable: false
          },
          {
            name: 'optional',
            align: 'left',
            label: 'Optional',
            field: 'optional',
            sortable: false
          },
          {
            name: 'sortable',
            align: 'left',
            label: 'Sortable',
            field: 'sortable',
            sortable: false
          },
          {
            name: 'searchable',
            align: 'left',
            label: 'Searchable',
            field: 'searchable',
            sortable: false
          }
        ],
        pagination: {
          sortBy: 'name',
          rowsPerPage: 100,
          page: 1,
          rowsNumber: 100
        },
        search: null,
        hideEmpty: true
      }
    }
  },

  methods: {
    addField: function () {
      this.fields.push({
        name: '',
        type: 'text',
        label: '',
        hint: '',
        optional: false,
        sortable: true,
        searchable: true
      })
    },
    removeField: function (field) {
      const index = this.fields.indexOf(field)
      if (index > -1) {
        this.fields.splice(index, 1)
      }
    }
  },
  created: function () {},
  mixins: [windowMixin]
}
