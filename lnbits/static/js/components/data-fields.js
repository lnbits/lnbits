window.app.component('lnbits-data-fields', {
  name: 'lnbits-data-fields',
  template: '#lnbits-data-fields',
  props: ['fields', 'hide-advanced'],
  data() {
    return {
      fieldTypes: [
        {label: 'Text', value: 'str'},
        {label: 'Integer', value: 'int'},
        {label: 'Float', value: 'float'},
        {label: 'Boolean', value: 'bool'},
        {label: 'Date Time', value: 'datetime'},
        {label: 'JSON', value: 'json'},
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
        name: 'field_name_' + (this.fields.length + 1),
        type: 'text',
        label: '',
        hint: '',
        optional: true,
        sortable: true,
        searchable: true,
        editable: true,
        fields: [] // For nested fields in JSON type
      })
    },
    removeField: function (field) {
      const index = this.fields.indexOf(field)
      if (index > -1) {
        this.fields.splice(index, 1)
      }
    }
  },
  async created() {
    if (!this.hideAdvanced) {
      this.fieldsTable.columns.push(
        {
          name: 'editable',
          align: 'left',
          label: 'UI Editable',
          field: 'editable',
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
      )
    }
  }
})
