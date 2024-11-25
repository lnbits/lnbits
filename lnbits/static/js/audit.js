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
      },
      auditDetailsDialog: {
        data: null,
        show: false
      }
    }
  },

  async created() {
    await this.fetchAudit()
  },
  mounted() {
    this.initCharts()
  },

  methods: {
    async fetchAudit(props) {
      try {
        const params = LNbits.utils.prepareFilterQuery(this.auditTable, props)
        const {data} = await LNbits.api.request(
          'GET',
          `/audit/api/v1?${params}`
        )

        this.auditTable.pagination.rowsNumber = data.total
        this.auditEntries = data.data
        await this.fetchAuditStats(props)
      } catch (error) {
        console.warn(error)
        LNbits.utils.notifyApiError(error)
      } finally {
        this.auditTable.loading = false
      }
    },
    async fetchAuditStats(props) {
      try {
        const params = LNbits.utils.prepareFilterQuery(this.auditTable, props)
        const {data} = await LNbits.api.request(
          'GET',
          `/audit/api/v1/stats?${params}`
        )
        console.log('### data', data)

        this.requestMethodChart.data.labels = data.request_method.map(
          rm => rm.field
        )
        this.requestMethodChart.data.datasets[0].data = data.request_method.map(
          rm => rm.total
        )

        this.requestMethodChart.update()

        this.responseCodeChart.data.labels = data.response_code.map(
          rm => rm.field
        )
        this.responseCodeChart.data.datasets[0].data = data.response_code.map(
          rm => rm.total
        )

        this.responseCodeChart.update()

        this.componentUseChart.data.labels = data.component.map(
          rm => rm.field
        )
        this.componentUseChart.data.datasets[0].data = data.component.map(
          rm => rm.total
        )

        this.componentUseChart.update()

        this.longDurationChart.data.labels = data.long_duration.map(
          rm => rm.field
        )
        this.longDurationChart.data.datasets[0].data = data.long_duration.map(
          rm => rm.total
        )

        this.longDurationChart.update()
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
    showDetailsDialog(entry) {
      const details = JSON.parse(entry?.request_details || '')
      try {
        if (details.body) {
          details.body = JSON.parse(details.body)
        }
      } catch (e) {
        // do nothing
      }
      this.auditDetailsDialog.data = JSON.stringify(details, null, 4)
      this.auditDetailsDialog.show = true
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
    },
    initCharts() {
      // Chart.defaults.color = 'secondary'
      this.responseCodeChart = new Chart(
        this.$refs.responseCodeChart.getContext('2d'),
        {
          type: 'doughnut',

          options: {
            responsive: true,


            plugins: {
              legend: {
                position: 'bottom'
              },
              title: {
                display: true,
                text: 'HTTP Response Codes'
              }
            }
          },
          data: {
            datasets: [
              {
                label: '',
                data: [20, 10],
                backgroundColor: [
                  'rgb(100, 99, 200)',
                  'rgb(54, 162, 235)',
                  'rgb(255, 205, 86)',
                  'rgb(255, 5, 86)',
                  'rgb(25, 205, 86)',
                  'rgb(255, 205, 250)'
                ]
              }
            ],
            labels: []
          }
        }
      )
      this.requestMethodChart = new Chart(
        this.$refs.requestMethodChart.getContext('2d'),
        {
          type: 'bar',

          options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {

              title: {
                display: true,
                text: 'HTTP Methods'
              }
            }
          },
          data: {
            datasets: [
              {
                label: 'HTTP Methods',
                data: [],
                backgroundColor: [
                  'rgb(255, 99, 132)',
                  'rgb(54, 162, 235)',
                  'rgb(255, 205, 86)',
                  'rgb(255, 5, 86)',
                  'rgb(25, 205, 86)',
                  'rgb(255, 205, 250)'
                ],
                hoverOffset: 4
              }
            ]
          }
        }
      )
      this.componentUseChart = new Chart(
          this.$refs.componentUseChart.getContext('2d'),
          {
            type: 'pie',
            options: {
              responsive: true,
              plugins: {
                legend: {
                  position: 'xxx'
                },
                title: {
                  display: true,
                  text: 'Components'
                }
              },
              onClick: (event, elements, chart) => {
                if (elements[0]) {
                   const i = elements[0].index;
                   console.log("#### click",chart.data.labels[i] + ': ' + chart.data.datasets[0]);
                }
              }
            },
            data: {
              datasets: [
                {
                  label: 'Components',
                  data: [],
                  backgroundColor: [
                    'rgb(255, 99, 132)',
                    'rgb(54, 162, 235)',
                    'rgb(255, 205, 86)',
                    'rgb(255, 5, 86)',
                    'rgb(25, 205, 86)',
                    'rgb(255, 205, 250)',
                    'rgb(100, 205, 250)',
                    'rgb(120, 205, 250)',
                    'rgb(140, 205, 250)',
                    'rgb(160, 205, 250)'
                  ],
                  hoverOffset: 4
                }
              ]
            }
          }
        )
        this.longDurationChart = new Chart(
          this.$refs.longDurationChart.getContext('2d'),
          {
            type: 'bar',
            options: {
              responsive: true,
              indexAxis: 'y',
              maintainAspectRatio: false,
              plugins: {
                legend: {
                  position: 'xxx'
                },
                title: {
                  display: true,
                  text: 'Long Duration'
                }
              },
              onClick: (event, elements, chart) => {
                if (elements[0]) {
                   const i = elements[0].index;
                   console.log("#### click",chart.data.labels[i] + ': ' + chart.data.datasets[0]);
                }
              }
            },
            data: {
              datasets: [
                {
                  label: 'Components',
                  data: [],
                  backgroundColor: [
                    'rgb(255, 99, 132)',
                    'rgb(54, 162, 235)',
                    'rgb(255, 205, 86)',
                    'rgb(255, 5, 86)',
                    'rgb(25, 205, 86)',
                    'rgb(255, 205, 250)',
                    'rgb(100, 205, 250)',
                    'rgb(120, 205, 250)',
                    'rgb(140, 205, 250)',
                    'rgb(160, 205, 250)'
                  ],
                  hoverOffset: 4
                }
              ]
            }
          }
        )
    }
  }
})
