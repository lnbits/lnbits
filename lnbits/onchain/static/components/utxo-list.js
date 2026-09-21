import {satOrBtc} from '../js/utils.js'
window.app.component('onchain-utxo-list', {
  name: 'onchain-utxo-list',
  template: '#onchain-utxo-list',

  props: [
    'utxos',
    'accounts',
    'selectable',
    'payed-amount',
    'sats-denominated',
    'mempool-endpoint',
    'filter'
  ],

  data: function () {
    return {
      filterLocal: this.filter || '',
      utxosTable: {
        pagination: {
          rowsPerPage: 10
        }
      },
      utxoSelectionModes: [
        'Manual',
        'Random',
        'Select All',
        'Smaller Inputs First',
        'Larger Inputs First'
      ],
      utxoSelectionMode: 'Larger Inputs First',
      utxoSelectAmount: 0
    }
  },

  watch: {
    filter(value) {
      this.filterLocal = value || ''
    }
  },

  computed: {
    utxosTableColumns() {
      return [
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
          label: this.$t('onchain.status'),
          sortable: true
        },
        {
          name: 'address',
          align: 'left',
          label: this.$t('onchain.address_label'),
          field: 'address',
          sortable: true
        },
        {
          name: 'amount',
          align: 'left',
          label: this.$t('onchain.amount'),
          field: 'amount',
          sortable: true
        },
        {
          name: 'date',
          align: 'left',
          label: this.$t('onchain.date'),
          field: 'date',
          sortable: true
        },
        {
          name: 'wallet',
          align: 'left',
          label: this.$t('onchain.account'),
          field: 'wallet',
          sortable: true
        }
      ]
    },
    columns: function () {
      return this.utxosTableColumns.filter(c =>
        c.selectable ? this.selectable : true
      )
    }
  },

  methods: {
    satBtc(val, showUnit = true) {
      return satOrBtc(val, showUnit, this.satsDenominated)
    },
    getWalletName: function (walletId) {
      return (
        (this.accounts || []).find(w => w.id === walletId)?.title || 'unknown'
      )
    },
    getWalletName: function (walletId) {
      const wallet = (this.accounts || []).find(wl => wl.id === walletId)
      return wallet ? wallet.title : 'unknown'
    },
    getTotalSelectedUtxoAmount: function () {
      const total = (this.utxos || [])
        .filter(u => u.selected)
        .reduce((t, a) => t + (a.amount || 0), 0)
      return total
    },
    refreshUtxoSelection: function (totalPayedAmount) {
      this.utxoSelectAmount = totalPayedAmount
      this.applyUtxoSelectionMode()
    },
    updateUtxoSelection: function () {
      this.utxoSelectAmount = this.payedAmount
      this.applyUtxoSelectionMode()
    },
    applyUtxoSelectionMode: function () {
      const mode = this.utxoSelectionMode
      const isSelectAll = mode === 'Select All'
      if (isSelectAll) {
        this.utxos.forEach(u => (u.selected = true))
        return
      }

      const isManual = mode === 'Manual'
      if (isManual || !this.utxoSelectAmount) return

      this.utxos.forEach(u => (u.selected = false))

      const isSmallerFirst = mode === 'Smaller Inputs First'
      const isLargerFirst = mode === 'Larger Inputs First'
      let selectedUtxos = this.utxos.slice()
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
        utxo.selected = total < this.utxoSelectAmount
        total += utxo.amount
        return total
      }, 0)
    }
  },

  created: async function () {}
})
