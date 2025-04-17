window.NodePageLogic = {
  mixins: [window.windowMixin],
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
    api(method, url, options) {
      const params = new URLSearchParams(options?.query)
      return LNbits.api
        .request(method, `/node/api/v1${url}?${params}`, {}, options?.data)
        .catch(error => {
          LNbits.utils.notifyApiError(error)
        })
    },
    getChannel(channel_id) {
      return this.api('GET', `/channels/${channel_id}`).then(response => {
        this.setFeeDialog.data.fee_ppm = response.data.fee_ppm
        this.setFeeDialog.data.fee_base_msat = response.data.fee_base_msat
      })
    },
    getChannels() {
      return this.api('GET', '/channels').then(response => {
        this.channels.data = response.data
      })
    },
    getInfo() {
      return this.api('GET', '/info').then(response => {
        this.info = response.data
        this.channel_stats = response.data.channel_stats
      })
    },
    get1MLStats() {
      return this.api('GET', '/rank').then(response => {
        this.ranks = response.data
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
      return this.api('GET', '/payments', {query}).then(response => {
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
      return this.api('GET', '/invoices', {query}).then(response => {
        this.invoiceTable.data = response.data.data
        this.invoiceTable.pagination.rowsNumber = response.data.total
      })
    },
    getPeers() {
      return this.api('GET', '/peers').then(response => {
        this.peers.data = response.data
        console.log('peers', this.peers)
      })
    },
    connectPeer() {
      this.api('POST', '/peers', {data: this.connectPeerDialog.data}).then(
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
          this.api('DELETE', `/peers/${id}`).then(response => {
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
      this.api('PUT', `/channels/${channel_id}`, {
        data: this.setFeeDialog.data
      })
        .then(response => {
          this.setFeeDialog.show = false
          this.getChannels()
        })
        .catch(LNbits.utils.notifyApiError)
    },
    openChannel() {
      this.api('POST', '/channels', {data: this.openChannelDialog.data})
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
      this.api('DELETE', '/channels', {
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
      console.log('details', details)
    },
    shortenNodeId(nodeId) {
      return nodeId
        ? nodeId.substring(0, 5) + '...' + nodeId.substring(nodeId.length - 5)
        : '...'
    }
  }
}

window.app.component('lnbits-node-ranks', {
  props: ['ranks'],
  data() {
    return {
      stats: [
        {label: 'Capacity', key: 'capacity'},
        {label: 'Channels', key: 'channelcount'},
        {label: 'Age', key: 'age'},
        {label: 'Growth', key: 'growth'},
        {label: 'Availability', key: 'availability'}
      ]
    }
  },
  template: `
    <q-card class='q-my-none'>
    <div class='column q-ma-md'>
      <h5 class='text-subtitle1 text-bold q-my-none'>1ml Node Rank</h5>
      <div v-for='stat in stats' class='q-gutter-sm'>
        <div class='row items-center'>
          <div class='col-9'>{{ stat.label }}</div>
          <div class='col-3 text-subtitle1 text-bold'>
            {{ (ranks && ranks[stat.key]) ?? '-' }}
          </div>
        </div>
      </div>
    </div>
    </q-card>
  `
})

window.app.component('lnbits-channel-stats', {
  props: ['stats'],
  data() {
    return {
      states: [
        {label: 'Active', value: 'active', color: 'green'},
        {label: 'Pending', value: 'pending', color: 'orange'},
        {label: 'Inactive', value: 'inactive', color: 'grey'},
        {label: 'Closed', value: 'closed', color: 'red'}
      ]
    }
  },
  template: `
    <q-card>
    <div class='column q-ma-md'>
      <h5 class='text-subtitle1 text-bold q-my-none'>Channels</h5>
      <div v-for='state in states' class='q-gutter-sm'>
        <div class='row'>
          <div class='col-9'>
            <q-badge rounded size='md' :color='state.color'>{{ state.label }}</q-badge>
          </div>
          <div class='col-3 text-subtitle1 text-bold'>
            {{ (stats?.counts && stats.counts[state.value]) ?? "-" }}
          </div>
        </div>
      </div>
    </div>
    </q-card>
  `
})

window.app.component('lnbits-stat', {
  props: ['title', 'amount', 'msat', 'btc'],
  computed: {
    value() {
      return (
        this.amount ??
        (this.btc
          ? LNbits.utils.formatSat(this.btc)
          : LNbits.utils.formatMsat(this.msat))
      )
    }
  },
  template: `
    <q-card>
    <q-card-section>
      <div class='text-overline text-primary'>
        {{ title }}
      </div>
      <div>
        <span class='text-h4 text-bold q-my-none'>{{ value }}</span>
        <span class='text-h5' v-if='msat != undefined'>sats</span>
        <span class='text-h5' v-if='btc != undefined'>BTC</span>
      </div>
    </q-card-section>
    </q-card>
  `
})

window.app.component('lnbits-node-qrcode', {
  props: ['info'],
  mixins: [window.windowMixin],
  template: `
    <q-card class="my-card">
      <q-card-section>
        <div class="text-h6">
          <div style="text-align: center">
            <vue-qrcode
              :value="info.addresses[0]"
              :options="{width: 250}"
              v-if='info.addresses[0]'
              class="rounded-borders"
            ></vue-qrcode>
            <div v-else class='text-subtitle1'>
              No addresses available
            </div>
          </div>
        </div>
      </q-card-section>
      <q-card-actions vertical>
        <q-btn
          dense
          unelevated
          size="md"
          @click="copyText(info.id)"
        >Public Key<q-tooltip> Click to copy </q-tooltip>
        </q-btn>
      </q-card-actions>
    </q-card>
  `
})

window.app.component('lnbits-node-info', {
  props: ['info'],
  data() {
    return {
      showDialog: false
    }
  },
  mixins: [window.windowMixin],
  methods: {
    shortenNodeId(nodeId) {
      return nodeId
        ? nodeId.substring(0, 5) + '...' + nodeId.substring(nodeId.length - 5)
        : '...'
    }
  },
  template: `
    <div class='row items-baseline q-gutter-x-sm'>
    <div class='text-h4 text-bold'>{{ this.info.alias }}</div>
    <div class='row items-center q-gutter-sm'>
      <div class='text-subtitle1 text-light'>{{ this.info.backend_name }}</div>
      <q-badge
        :style='\`background-color: #\${this.info.color}\`'
        class='text-bold'
      >
        #{{ this.info.color }}
      </q-badge>
      <div class='text-bold'>{{ shortenNodeId(this.info.id) }}</div>
      <q-btn
        size='xs'
        flat
        dense
        icon='content_paste'
        @click='copyText(info.id)'
      ></q-btn>
      <q-btn
        size='xs'
        flat
        dense
        icon='qr_code'
        @click='showDialog = true'
      ></q-btn>
    </div>
      <q-dialog v-model="showDialog">
        <lnbits-node-qrcode :info='info'></lnbits-node-qrcode>
      </q-dialog>
    </div>
  `
})

window.app.component('lnbits-stat', {
  props: ['title', 'amount', 'msat', 'btc'],
  computed: {
    value() {
      return (
        this.amount ??
        (this.btc
          ? LNbits.utils.formatSat(this.btc)
          : LNbits.utils.formatMsat(this.msat))
      )
    }
  },
  template: `
        <q-card>
        <q-card-section>
          <div class='text-overline text-primary'>
            {{ title }}
          </div>
          <div>
            <span class='text-h4 text-bold q-my-none'>{{ value }}</span>
            <span class='text-h5' v-if='msat != undefined'>sats</span>
            <span class='text-h5' v-if='btc != undefined'>BTC</span>
          </div>
        </q-card-section>
        </q-card>
      `
})

window.app.component('lnbits-channel-balance', {
  props: ['balance', 'color'],
  methods: {
    formatMsat(msat) {
      return LNbits.utils.formatMsat(msat)
    }
  },
  template: `
    <div>
        <div class="row items-center justify-between">
          <span class="text-weight-thin">
            Local: {{ formatMsat(balance.local_msat) }}
            sats
          </span>
          <span class="text-weight-thin">
            Remote: {{ formatMsat(balance.remote_msat) }}
            sats
          </span>
        </div>

        <q-linear-progress
          rounded
          size="25px"
          :value="balance.local_msat / balance.total_msat"
          :color="color"
          :style="\`color: #\${this.color}\`"
        >
          <div class="absolute-full flex flex-center">
            <q-badge
              color="white"
              text-color="accent"
              :label="formatMsat(balance.total_msat) + ' sats'"
            >
              {{ balance.alias }}
            </q-badge>
          </div>
       </q-linear-progress>
    </div>
  `
})

window.app.component('lnbits-date', {
  props: ['ts'],
  computed: {
    date() {
      return LNbits.utils.formatDate(this.ts)
    },
    dateFrom() {
      return moment.utc(this.date).fromNow()
    }
  },
  template: `
    <div>
      <q-tooltip>{{ this.date }}</q-tooltip>
      {{ this.dateFrom }}
    </div>
  `
})
