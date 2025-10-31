window.PageWallets = {
  template: '#page-wallets',
  mixins: [window.windowMixin],
  data() {
    return {
      user: null,
      tab: 'wallets',
      wallets: [],
      showAddWalletDialog: {show: false},
      walletsTable: {
        columns: [
          {
            name: 'name',
            align: 'left',
            label: 'Name',
            field: 'name',
            sortable: true
          },
          {
            name: 'currency',
            align: 'center',
            label: 'Currency',
            field: 'currency',
            sortable: true
          },
          {
            name: 'updated_at',
            align: 'right',
            label: 'Last Updated',
            field: 'updated_at',
            sortable: true
          }
        ],
        pagination: {
          sortBy: 'updated_at',
          rowsPerPage: 12,
          page: 1,
          descending: true,
          rowsNumber: 10
        },
        search: '',
        hideEmpty: true,
        loading: false
      }
    }
  },
  watch: {
    'walletsTable.search': {
      handler() {
        const props = {}
        if (this.walletsTable.search) {
          props['search'] = this.walletsTable.search
        }
        this.getUserWallets()
      }
    }
  },
  methods: {
    async getUserWallets(props) {
      try {
        this.walletsTable.loading = true
        const params = LNbits.utils.prepareFilterQuery(this.walletsTable, props)
        const {data} = await LNbits.api.request(
          'GET',
          `/api/v1/wallet/paginated?${params}`,
          null
        )
        this.wallets = data.data
        this.walletsTable.pagination.rowsNumber = data.total
      } catch (e) {
        LNbits.utils.notifyApiError(e)
      } finally {
        this.walletsTable.loading = false
      }
    },

    goToWallet(walletId) {
      window.location = `/wallet?wal=${walletId}`
    },
    formattedFiatAmount(amount, currency) {
      return LNbits.utils.formatCurrency(Number(amount).toFixed(2), currency)
    },
    formattedSatAmount(amount) {
      return LNbits.utils.formatMsat(amount) + ' sat'
    }
  },
  async created() {
    await this.getUserWallets()
  }
}
