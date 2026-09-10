window.PageNode = {
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
      phoenixd: {capabilities: []},
      phoenixdAmount: 2000000,
      phoenixdEstimate: null,
      phoenixdReceive: '',
      phoenixdResult: '',
      phoenixdDialog: {show: false, operation: '', data: {}},
      phoenixdBusy: false,
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
            label: this.$t('amount'),
            field: row => this.formatMsat(row.amount),
            sortable: true
          },
          {
            name: 'fee',
            align: 'right',
            label: this.$t('fee'),
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
            label: this.$t('amount'),
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
  },
  watch: {
    tab(val) {
      if (val === 'transactions' && !this.paymentsTable.data.length) {
        this.getPayments()
        this.getInvoices()
      } else if (val === 'channels' && !this.channels.data.length) {
        this.getChannels()
        if (!this.managedChannels) this.getPeers()
      }
    }
  },
  computed: {
    managedChannels() {
      return this.info.managed_channels === true
    },
    canManage() {
      return this.g.user?.super_user === true
    },
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
    hasPhoenixdCapability(capability) {
      return this.phoenixd.capabilities.includes(capability)
    },
    getPhoenixdStatus() {
      return this.nodeApi('GET', '/phoenixd/status')
        .then(response => {
          this.phoenixd = response.data
        })
        .catch(() => {})
    },
    estimatePhoenixdLiquidity() {
      this.phoenixdEstimate = null
      return this.nodeApi('GET', '/phoenixd/liquidity-fees', {
        query: {amount_sat: this.phoenixdAmount}
      })
        .then(response => {
          this.phoenixdEstimate = response.data
        })
        .catch(() => {})
    },
    getPhoenixdReceive(kind) {
      this.phoenixdReceive = ''
      return this.nodeApi('GET', `/phoenixd/receive/${kind}`)
        .then(response => {
          this.phoenixdReceive = response.data.value
        })
        .catch(() => {})
    },
    showPhoenixdDialog(operation, data = {}) {
      this.phoenixdDialog = {show: true, operation, data: {...data}}
      this.phoenixdResult = ''
    },
    submitPhoenixd() {
      const {operation, data} = this.phoenixdDialog
      const descriptions = {
        close: `Close channel ${data.channel_id} and send its remaining balance to ${data.address} at ${data.fee_rate} sat/vB?`,
        send: `Withdraw ${data.amount_sat} sats to ${data.address} at ${data.fee_rate} sat/vB?`,
        bump: `Spend node funds to bump the funding transaction fee to a target of ${data.fee_rate} sat/vB?`
      }
      LNbits.utils
        .confirmDialog(
          descriptions[operation] +
            ' This spends funds backing LNbits wallets and cannot be undone.'
        )
        .onOk(async () => {
          this.phoenixdBusy = true
          try {
            const response = await this.nodeApi(
              'POST',
              `/phoenixd/${operation}`,
              {data}
            )
            this.phoenixdResult = response.data.txid
            this.phoenixdDialog.show = false
            await this.getInfo()
            await this.getChannels()
          } catch (_) {
            // nodeApi displays the error; keep the entered data for review.
          } finally {
            this.phoenixdBusy = false
          }
        })
    },
    exportPhoenixdHistory() {
      this.nodeApi('POST', '/phoenixd/export')
        .then(response => {
          Quasar.Notify.create({message: response.data.message})
        })
        .catch(() => {})
    },
    formatMsat(msat) {
      return LNbits.utils.formatMsat(msat)
    },
    nodeApi(method, url, options) {
      const params = new URLSearchParams(options?.query)
      return LNbits.api
        .request(method, `/node/api/v1${url}?${params}`, {}, options?.data)
        .catch(error => {
          LNbits.utils.notifyApiError(error)
          throw error
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
          const wasManaged = this.managedChannels
          this.info = response.data
          this.channel_stats = response.data.channel_stats
          if (this.managedChannels) {
            this.getPhoenixdStatus()
            if (!wasManaged) this.stateFilters = null
          } else {
            this.get1MLStats()
          }
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
      if (this.managedChannels) {
        this.showPhoenixdDialog('close', {channel_id: channel.id})
        return
      }
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
