window.PageNode = {
  mixins: [window.windowMixin],
  template: '#page-node',
  config: {
    globalProperties: {
      LNbits,
      msg: 'hello'
    }
  },
  data() {
    return {
      isSuperUser: false,
      wallet: {},
      tab: 'dashboard',
      payments: 1000,
      info: {},
      channel_stats: {},

      channels: {
        data: [],
        filter: ''
      },

      activeBalance: {},
      ranks: {},

      peers: {
        data: [],
        filter: ''
      },

      connectPeerDialog: {
        show: false,
        data: {}
      },

      setFeeDialog: {
        show: false,
        data: {
          fee_ppm: 0,
          fee_base_msat: 0
        }
      },

      openChannelDialog: {
        show: false,
        data: {}
      },

      closeChannelDialog: {
        show: false,
        data: {}
      },

      nodeInfoDialog: {
        show: false,
        data: {}
      },

      transactionDetailsDialog: {
        show: false,
        data: {}
      },

      states: [
        {label: 'Active', value: 'active', color: 'green'},
        {label: 'Pending', value: 'pending', color: 'orange'},
        {label: 'Inactive', value: 'inactive', color: 'grey'},
        {label: 'Closed', value: 'closed', color: 'red'}
      ],

      stateFilters: [
        {label: 'Active', value: 'active'},
        {label: 'Pending', value: 'pending'}
      ],

      paymentsTable: {
        data: [],
        columns: [
          {
            name: 'pending',
            label: ''
          },
          {
            name: 'date',
            align: 'left',
            label: this.$t('date'),
            field: 'date',
            sortable: true
          },
          {
            name: 'sat',
            align: 'right',
            label: this.$t('amount') + ' (' + LNBITS_DENOMINATION + ')',
            field: row => this.formatMsat(row.amount),
            sortable: true
          },
          {
            name: 'fee',
            align: 'right',
            label: this.$t('fee') + ' (m' + LNBITS_DENOMINATION + ')',
            field: 'fee'
          },
          {
            name: 'destination',
            align: 'right',
            label: 'Destination',
            field: 'destination'
          },
          {
            name: 'memo',
            align: 'left',
            label: this.$t('memo'),
            field: 'memo'
          }
        ],
        pagination: {
          rowsPerPage: 10,
          page: 1,
          rowsNumber: 10
        },
        filter: null
      },
      invoiceTable: {
        data: [],
        columns: [
          {
            name: 'pending',
            label: ''
          },
          {
            name: 'paid_at',
            field: 'paid_at',
            align: 'left',
            label: 'Paid at',
            sortable: true
          },
          {
            name: 'expiry',
            label: this.$t('expiry'),
            field: 'expiry',
            align: 'left',
            sortable: true
          },
          {
            name: 'amount',
            label: this.$t('amount') + ' (' + LNBITS_DENOMINATION + ')',
            field: row => this.formatMsat(row.amount),
            sortable: true
          },
          {
            name: 'memo',
            align: 'left',
            label: this.$t('memo'),
            field: 'memo'
          }
        ],
        pagination: {
          rowsPerPage: 10,
          page: 1,
          rowsNumber: 10
        },
        filter: null
      }
    }
  },
  created() {
    this.getInfo()
    this.get1MLStats()
  },
  watch: {
    tab(val) {
      if (val === 'transactions' && !this.paymentsTable.data.length) {
        this.getPayments()
        this.getInvoices()
      } else if (val === 'channels' && !this.channels.data.length) {
        this.getChannels()
        this.getPeers()
      }
    }
  },
  computed: {
    checkChanges() {
      return !_.isEqual(this.settings, this.formData)
    },
    filteredChannels() {
      return this.stateFilters
        ? this.channels.data.filter(channel => {
            return this.stateFilters.find(({value}) => value == channel.state)
          })
        : this.channels.data
    },
    totalBalance() {
      return this.filteredChannels.reduce(
        (balance, channel) => {
          balance.local_msat += channel.balance.local_msat
          balance.remote_msat += channel.balance.remote_msat
          balance.total_msat += channel.balance.total_msat
          return balance
        },
        {local_msat: 0, remote_msat: 0, total_msat: 0}
      )
    }
  },
  methods: {
    formatMsat(msat) {
      return LNbits.utils.formatMsat(msat)
    },
    nodeApi(method, url, options) {
      const params = new URLSearchParams(options?.query)
      return LNbits.api
        .request(method, `/node/api/v1${url}?${params}`, {}, options?.data)
        .catch(error => {
          LNbits.utils.notifyApiError(error)
        })
    },
    getChannel(channel_id) {
      return this.nodeApi('GET', `/channels/${channel_id}`).then(response => {
        this.setFeeDialog.data.fee_ppm = response.data.fee_ppm
        this.setFeeDialog.data.fee_base_msat = response.data.fee_base_msat
      })
    },
    getChannels() {
      return this.nodeApi('GET', '/channels').then(response => {
        this.channels.data = response.data
      })
    },
    getInfo() {
      return this.nodeApi('GET', '/info')
        .then(response => {
          this.info = response.data
          this.channel_stats = response.data.channel_stats
        })
        .catch(() => {
          this.info = {}
          this.channel_stats = {}
        })
    },
    get1MLStats() {
      return this.nodeApi('GET', '/rank')
        .then(response => {
          this.ranks = response.data
        })
        .catch(() => {
          this.ranks = {}
        })
    },
    getPayments(props) {
      if (props) {
        this.paymentsTable.pagination = props.pagination
      }
      let pagination = this.paymentsTable.pagination
      const query = {
        limit: pagination.rowsPerPage,
        offset: (pagination.page - 1) * pagination.rowsPerPage ?? 0
      }
      return this.nodeApi('GET', '/payments', {query}).then(response => {
        this.paymentsTable.data = response.data.data
        this.paymentsTable.pagination.rowsNumber = response.data.total
      })
    },
    getInvoices(props) {
      if (props) {
        this.invoiceTable.pagination = props.pagination
      }
      let pagination = this.invoiceTable.pagination
      const query = {
        limit: pagination.rowsPerPage,
        offset: (pagination.page - 1) * pagination.rowsPerPage ?? 0
      }
      return this.nodeApi('GET', '/invoices', {query}).then(response => {
        this.invoiceTable.data = response.data.data
        this.invoiceTable.pagination.rowsNumber = response.data.total
      })
    },
    getPeers() {
      return this.nodeApi('GET', '/peers').then(response => {
        this.peers.data = response.data
      })
    },
    connectPeer() {
      this.nodeApi('POST', '/peers', {data: this.connectPeerDialog.data}).then(
        () => {
          this.connectPeerDialog.show = false
          this.getPeers()
        }
      )
    },
    disconnectPeer(id) {
      LNbits.utils
        .confirmDialog('Do you really wanna disconnect this peer?')
        .onOk(() => {
          this.nodeApi('DELETE', `/peers/${id}`).then(response => {
            Quasar.Notify.create({
              message: 'Disconnected',
              icon: null
            })
            this.needsRestart = true
            this.getPeers()
          })
        })
    },
    setChannelFee(channel_id) {
      this.nodeApi('PUT', `/channels/${channel_id}`, {
        data: this.setFeeDialog.data
      })
        .then(response => {
          this.setFeeDialog.show = false
          this.getChannels()
        })
        .catch(LNbits.utils.notifyApiError)
    },
    openChannel() {
      this.nodeApi('POST', '/channels', {data: this.openChannelDialog.data})
        .then(response => {
          this.openChannelDialog.show = false
          this.getChannels()
        })
        .catch(error => {
          console.log(error)
        })
    },
    showCloseChannelDialog(channel) {
      this.closeChannelDialog.show = true
      this.closeChannelDialog.data = {
        force: false,
        short_id: channel.short_id,
        ...channel.point
      }
    },
    closeChannel() {
      this.nodeApi('DELETE', '/channels', {
        query: this.closeChannelDialog.data
      }).then(response => {
        this.closeChannelDialog.show = false
        this.getChannels()
      })
    },
    showSetFeeDialog(channel_id) {
      this.setFeeDialog.show = true
      this.setFeeDialog.channel_id = channel_id
      this.getChannel(channel_id)
    },
    showOpenChannelDialog(peer_id) {
      this.openChannelDialog.show = true
      this.openChannelDialog.data = {peer_id, funding_amount: 0}
    },
    showNodeInfoDialog(node) {
      this.nodeInfoDialog.show = true
      this.nodeInfoDialog.data = node
    },
    showTransactionDetailsDialog(details) {
      this.transactionDetailsDialog.show = true
      this.transactionDetailsDialog.data = details
    },
    shortenNodeId(nodeId) {
      return nodeId
        ? nodeId.substring(0, 5) + '...' + nodeId.substring(nodeId.length - 5)
        : '...'
    }
  }
}
