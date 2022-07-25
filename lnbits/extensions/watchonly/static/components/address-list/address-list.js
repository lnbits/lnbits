async function addressList(path) {
  const template = await loadTemplateAsync(path)
  Vue.component('address-list', {
    name: 'address-list',
    template,

    props: ['accounts', 'mempool_endpoint', 'inkey'],
    watch: {
      immediate: true,
      accounts(newVal, oldVal) {
        if ((newVal || []).length !== (oldVal || []).length) {
          this.refreshAddresses() // todo await
        }
      }
    },
    data: function () {
      return {
        addresses: [],
        show: false,
        data: [],
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
          columns: [
            {
              name: 'expand',
              align: 'left',
              label: ''
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
              name: 'note',
              align: 'left',
              label: 'Note',
              field: 'note',
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
            rowsPerPage: 0,
            sortBy: 'amount',
            descending: true
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
      getAddressesForWallet: async function (walletId) {
        try {
          const {data} = await LNbits.api.request(
            'GET',
            '/watchonly/api/v1/addresses/' + walletId,
            this.inkey
          )
          return data.map(mapAddressesData)
        } catch (err) {
          this.$q.notify({
            type: 'warning',
            message: `Failed to fetch addresses for wallet with id ${walletId}.`,
            timeout: 10000
          })
          LNbits.utils.notifyApiError(err)
        }
        return []
      },
      refreshAddresses: async function () {
        if (!this.accounts) return
        this.addresses = []
        for (const {id, type} of this.accounts) {
          const newAddresses = await this.getAddressesForWallet(id)
          const uniqueAddresses = newAddresses.filter(
            newAddr => !this.addresses.find(a => a.address === newAddr.address)
          )

          const lastAcctiveAddress =
            uniqueAddresses.filter(a => !a.isChange && a.hasActivity).pop() ||
            {}

          uniqueAddresses.forEach(a => {
            a.expanded = false
            a.accountType = type
            a.gapLimitExceeded =
              !a.isChange &&
              a.addressIndex >
                lastAcctiveAddress.addressIndex + DEFAULT_RECEIVE_GAP_LIMIT
          })
          this.addresses.push(...uniqueAddresses)
        }
        this.$emit('update:addresses', this.addresses)
      },
      scanAddress: async function (addressData) {
        this.$emit('scan:address', addressData)
      },
      showAddressDetails: function (addressData) {
        this.$emit('show-address-details', addressData)
      }
    },

    created: async function () {
      await this.refreshAddresses()
      // this.$emit('update:addresses', this.addresses)
    }
  })
}
