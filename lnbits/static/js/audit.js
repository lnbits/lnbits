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
        path: ''
      },
      auditTable: {
        columns: [
          {
            name: 'created_at',
            align: 'center',
            label: 'Date',
            field: 'created_at',
            sortable: true
          },
          {
            name: 'duration',
            align: 'left',
            label: 'Duration (sec)',
            field: 'duration',
            sortable: true
          },
          {
            name: 'request_method',
            align: 'left',
            label: 'Method',
            field: 'request_method',
            sortable: false
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

  async created() {
    console.log('### audit entries')
    await this.fetchAudit()
  },

  methods: {
    async fetchAudit(props) {
      try {
        const params = LNbits.utils.prepareFilterQuery(this.auditTable, props)
        const {data} = await LNbits.api.request(
          'GET',
          `/audit/api/v1?${params}`
        )
        this.auditTable.loading = false
        this.auditTable.pagination.rowsNumber = data.total
        this.auditEntries = data.data
      } catch (error) {
        console.warn(error)
        LNbits.utils.notifyApiError(error)
      }
    },
    async searchAuditBy(fieldName) {
      const fieldValue = this.searchData[fieldName]
      this.auditTable.filter = {}
      if (fieldValue) {
        this.auditTable.filter[fieldName] = fieldValue
      }

      await this.fetchAudit()
    },
    formatDate: function (value) {
      return Quasar.date.formatDate(new Date(value), 'YYYY-MM-DD HH:mm')
    },
    shortify(value) {
      valueLength = (value || '').length
      if (valueLength <= 10) {
        return value
      }
      return `${value.substring(0, 5)}...${value.substring(valueLength - 5, valueLength)}`
    }
  }
})
