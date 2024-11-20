window.app = Vue.createApp({
  el: '#vue',
  mixins: [window.windowMixin],
  data: function () {
    return {
      auditEntries: [],
      searchData: {
        user_id: '',
        ip_address: '',
        request_type: '',
        request_method: '',
        response_code: '',
        path: '',
        route_path: ''
      },
      auditTable: {
        columns: [
          {
            name: 'created_at',
            align: 'left',
            label: 'Date',
            field: 'created_at',
            sortable: true
          },
          {
            name: 'duration',
            align: 'left',
            label: 'Duration',
            field: 'duration',
            sortable: true
          },

          {
            name: 'user_id',
            align: 'left',
            label: 'User Id',
            field: 'user_id',
            sortable: false
          },
          {
            name: 'ip_address',
            align: 'left',
            label: 'IP Address',
            field: 'ip_address',
            sortable: false
          },

          {
            name: 'request_type',
            align: 'left',
            label: 'Type',
            field: 'request_type',
            sortable: false
          },
          {
            name: 'request_method',
            align: 'left',
            label: 'Method',
            field: 'request_method',
            sortable: false
          },
          {
            name: 'response_code',
            align: 'left',
            label: 'Code',
            field: 'response_code',
            sortable: false
          },
          {
            name: 'path',
            align: 'left',
            label: 'Path',
            field: 'path',
            sortable: false
          },

          {
            name: 'route_path',
            align: 'left',
            label: 'Route Path',
            field: 'route_path',
            sortable: false
          },

          {
            name: 'query_string',
            align: 'left',
            label: 'Query',
            field: 'query_string',
            sortable: false
          }
        ],
        pagination: {
          sortBy: 'created_at',
          rowsPerPage: 10,
          page: 1,
          descending: true,
          rowsNumber: 10
        },
        search: null,
        hideEmpty: true,
        loading: false
      }
    }
  },

  created() {
    console.log('### audit entries')
  },

  methods: {
    async fetchAudit() {
      console.log('### fetchAudit')
    },
    async searchAuditBy(fieldName) {
      console.log('### searchAuditBy', fieldName)
    }
  }
})
