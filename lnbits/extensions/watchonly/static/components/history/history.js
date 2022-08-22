async function history(path) {
  const template = await loadTemplateAsync(path)
  Vue.component('history', {
    name: 'history',
    template,

    props: ['history', 'mempool-endpoint', 'sats-denominated', 'filter'],
    data: function () {
      return {
        historyTable: {
          columns: [
            {
              name: 'expand',
              align: 'left',
              label: ''
            },
            {
              name: 'status',
              align: 'left',
              label: 'Status'
            },
            {
              name: 'amount',
              align: 'left',
              label: 'Amount',
              field: 'amount',
              sortable: true
            },
            {
              name: 'address',
              align: 'left',
              label: 'Address',
              field: 'address',
              sortable: true
            },
            {
              name: 'date',
              align: 'left',
              label: 'Date',
              field: 'date',
              sortable: true
            },
            {
              name: 'txId',
              field: 'txId'
            }
          ],
          exportColums: [
            {
              label: 'Action',
              field: 'action'
            },
            {
              label: 'Date&Time',
              field: 'date'
            },
            {
              label: 'Amount',
              field: 'amount'
            },
            {
              label: 'Fee',
              field: 'fee'
            },
            {
              label: 'Transaction Id',
              field: 'txId'
            }
          ],
          pagination: {
            rowsPerPage: 0
          }
        }
      }
    },

    methods: {
      satBtc(val, showUnit = true) {
        return satOrBtc(val, showUnit, this.satsDenominated)
      },
      getFilteredAddressesHistory: function () {
        return this.history.filter(a => (!a.isChange || a.sent) && !a.isSubItem)
      },
      exportHistoryToCSV: function () {
        const history = this.getFilteredAddressesHistory().map(a => ({
          ...a,
          action: a.sent ? 'Sent' : 'Received'
        }))
        LNbits.utils.exportCSV(
          this.historyTable.exportColums,
          history,
          'address-history'
        )
      }
    },
    created: async function () {}
  })
}
