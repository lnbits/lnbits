window.PageNodePublic = {
  template: '#page-node-public',
  mixins: [window.windowMixin],
  data() {
    return {
      enabled: false,
      isSuperUser: false,
      wallet: {},
      tab: 'dashboard',
      payments: 1000,
      info: {},
      channel_stats: {},
      channels: [],
      activeBalance: {},
      ranks: {},
      peers: [],
      connectPeerDialog: {
        show: false,
        data: {}
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
      states: [
        {label: 'Active', value: 'active', color: 'green'},
        {label: 'Pending', value: 'pending', color: 'orange'},
        {label: 'Inactive', value: 'inactive', color: 'grey'},
        {label: 'Closed', value: 'closed', color: 'red'}
      ]
    }
  },
  created() {
    this.getInfo()
    this.get1MLStats()
  },
  methods: {
    formatMsat(msat) {
      return LNbits.utils.formatMsat(msat)
    },
    api(method, url, data) {
      return LNbits.api.request(method, '/node/public/api/v1' + url, {}, data)
    },
    getInfo() {
      this.api('GET', '/info', {})
        .then(response => {
          this.info = response.data
          this.channel_stats = response.data.channel_stats
          this.enabled = true
        })
        .catch(() => {
          this.info = {}
          this.channel_stats = {}
        })
    },
    get1MLStats() {
      this.api('GET', '/rank', {})
        .then(response => {
          this.ranks = response.data
        })
        .catch(() => {
          this.ranks = {}
        })
    }
  }
}
