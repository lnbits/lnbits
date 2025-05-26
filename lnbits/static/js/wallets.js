window.WalletsPageLogic = {
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
            align: 'left',
            label: 'Currency',
            field: 'currency',
            sortable: true
          },
          {
            name: 'balance_msat',
            align: 'left',
            label: 'Balance',
            field: 'balance_msat',
            sortable: false
          },
          {
            name: 'id',
            align: 'left',
            label: 'Id',
            field: 'id',
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
        console.log('### data', data)
        console.log('### total', data.total)
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
