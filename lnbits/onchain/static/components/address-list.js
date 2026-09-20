import {satOrBtc} from '../js/utils.js'
window.app.component('onchain-address-list', {
  name: 'onchain-address-list',
  template: '#onchain-address-list',
  props: [
    'addresses',
    'accounts',
    'mempool-endpoint',
    'inkey',
    'sats-denominated'
  ],
  data: function () {
    return {
      show: false,
      history: [],
      selectedWallet: null,
      note: '',
      filterOptions: [
        'Show Change Addresses',
        'Show Gap Addresses',
        'Only With Amount'
      ],
      filterValues: [],

      addressesTable: {
        pagination: {
          rowsPerPage: 0,
          sortBy: 'amount',
          descending: true
        },
        filter: ''
      }
    }
  },

  computed: {
    addressesTableColumns() {
      return [
        {
          name: 'expand',
          align: 'left',
          label: ''
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
          name: 'note',
          align: 'left',
          label: this.$t('onchain.note'),
          field: 'note',
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
    }
  },

  methods: {
    satBtc(val, showUnit = true) {
      return satOrBtc(val, showUnit, this.satsDenominated)
    },
    // todo: bad. base.js not present in custom components
    copyText: function (text, message, position) {
      var notify = this.$q.notify
      Quasar.copyToClipboard(text).then(function () {
        notify({
          message: message || 'Copied to clipboard!',
          position: position || 'bottom'
        })
      })
    },
    getWalletName: function (walletId) {
      const wallet = (this.accounts || []).find(wl => wl.id === walletId)
      return wallet ? wallet.title : 'unknown'
    },
    getFilteredAddresses: function () {
      const selectedWalletId = this.selectedWallet?.id
      const filter = this.filterValues || []
      const includeChangeAddrs = filter.includes('Show Change Addresses')
      const includeGapAddrs = filter.includes('Show Gap Addresses')
      const excludeNoAmount = filter.includes('Only With Amount')

      const walletsLimit = (this.accounts || []).reduce((r, w) => {
        r[`_${w.id}`] = w.address_no
        return r
      }, {})

      const fAddresses = this.addresses.filter(
        a =>
          (includeChangeAddrs || !a.isChange) &&
          (includeGapAddrs ||
            a.isChange ||
            a.addressIndex <= walletsLimit[`_${a.wallet}`]) &&
          !(excludeNoAmount && a.amount === 0) &&
          (!selectedWalletId || a.wallet === selectedWalletId)
      )
      return fAddresses
    },

    scanAddress: async function (addressData) {
      this.$emit('scan:address', addressData)
    },
    showAddressDetails: function (addressData) {
      this.$emit('show-address-details', addressData)
    },
    searchInTab: function (tab, value) {
      this.$emit('search:tab', {tab, value})
    },
    updateNoteForAddress: async function (addressData, note) {
      this.$emit('update:note', {addressId: addressData.id, note})
    }
  },

  created: async function () {}
})
