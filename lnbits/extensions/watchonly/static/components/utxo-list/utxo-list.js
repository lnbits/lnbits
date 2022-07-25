async function utxoList(path) {
  const template = await loadTemplateAsync(path)
  Vue.component('utxo-list', {
    name: 'utxo-list',
    template,

    props: [
      'utxos',
      'accounts',
      'selectable',
      'payed-amount',
      'sats_denominated',
      'mempool_endpoint'
    ],

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
              label: '',
              selectable: true
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
        },
        utxoSelectionModes: [
          'Manual',
          'Random',
          'Select All',
          'Smaller Inputs First',
          'Larger Inputs First'
        ],
        utxoSelectionMode: 'Random'
      }
    },

    computed: {
      columns: function () {
        return this.utxosTable.columns.filter(c =>
          c.selectable ? this.selectable : true
        )
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
      },
      applyUtxoSelectionMode: function () {
        const payedAmount = this['payed-amount']
        const mode = this.payment.utxoSelectionMode
        this.utxos.data.forEach(u => (u.selected = false))
        const isManual = mode === 'Manual'
        if (isManual || !payedAmount) return

        const isSelectAll = mode === 'Select All'
        if (isSelectAll || payedAmount >= this.utxos.total) {
          this.utxos.data.forEach(u => (u.selected = true))
          return
        }
        const isSmallerFirst = mode === 'Smaller Inputs First'
        const isLargerFirst = mode === 'Larger Inputs First'

        let selectedUtxos = this.utxos.data.slice()
        if (isSmallerFirst || isLargerFirst) {
          const sortFn = isSmallerFirst
            ? (a, b) => a.amount - b.amount
            : (a, b) => b.amount - a.amount
          selectedUtxos.sort(sortFn)
        } else {
          // default to random order
          selectedUtxos = _.shuffle(selectedUtxos)
        }
        selectedUtxos.reduce((total, utxo) => {
          utxo.selected = total < payedAmount
          total += utxo.amount
          return total
        }, 0)
      }
    },

    created: async function () {}
  })
}
