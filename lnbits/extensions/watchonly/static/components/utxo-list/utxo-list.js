async function utxoList(path) {
  const template = await loadTemplateAsync(path)
  Vue.component('utxo-list', {
    name: 'utxo-list',
    template,

    props: ['utxos', 'accounts', 'sats_denominated', 'mempool_endpoint'],

    data: function () {
      return {
        utxosTable: {
          columns: [
            {
              name: 'expand',
              align: 'left',
              label: ''
            },
            {
              name: 'selected',
              align: 'left',
              label: ''
            },
            {
              name: 'status',
              align: 'center',
              label: 'Status',
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
              name: 'amount',
              align: 'left',
              label: 'Amount',
              field: 'amount',
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
              name: 'wallet',
              align: 'left',
              label: 'Account',
              field: 'wallet',
              sortable: true
            }
          ],
          pagination: {
            rowsPerPage: 10
          },
          filter: ''
        }
      }
    },

    methods: {
      satBtc(val, showUnit = true) {
        return satOrBtc(val, showUnit, this['sats_denominated'])
      },
      getWalletName: function (walletId) {
        const wallet = (this.accounts || []).find(wl => wl.id === walletId)
        return wallet ? wallet.title : 'unknown'
      },
      getTotalSelectedUtxoAmount: function () {
        const total = this.utxos
          .filter(u => u.selected)
          .reduce((t, a) => t + (a.amount || 0), 0)
        return total
      }
    },

    created: async function () {}
  })
}
