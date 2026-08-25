window.PageBlockExplorer = {
  template: '#page-blockexplorer',
  data() {
    return {
      query: '',
      loading: false,
      tip: null,
      fees: null,
      blocks: [],
      selectedBlock: null,
      blockDialog: false,
      txResult: null,
      txStatus: null,
      addressResult: null,
      currentAddress: ''
    }
  },
  computed: {
    feeList() {
      if (!this.fees || !this.fees.estimates) return []
      return Object.entries(this.fees.estimates).map(([blocks, rate]) => ({
        label: this.$t('n_block_fee', {n: blocks}),
        rate: (rate * 100000).toFixed(1) + ' sat/vB'
      }))
    },
    formattedBlocks() {
      const now = Math.floor(Date.now() / 1000)
      return this.blocks.map(b => ({
        ...b,
        shortHash: b.hash.slice(0, 8) + '...' + b.hash.slice(-4),
        timeAgo: this._timeAgo(now - b.timestamp),
        utcTime: new Date(b.timestamp * 1000).toUTCString(),
        difficulty: this._difficulty(b.bits)
      }))
    }
  },
  async created() {
    await Promise.all([this.loadTip(), this.loadFees(), this.loadBlocks()])
    this._blockWsActive = true
    this._connectBlocksWs()
    this._loadFromRoute()
  },
  beforeUnmount() {
    this._blockWsActive = false
    if (this._blockWs) this._blockWs.close()
    if (this._searchWs) this._searchWs.close()
  },
  watch: {
    $route(to) {
      this._loadFromRoute(to)
    },
    blockDialog(val) {
      if (!val && this.$route.params.type === 'block') {
        this.$router.push('/blockexplorer')
      }
    }
  },
  methods: {
    _loadFromRoute(route) {
      route = route || this.$route
      const {type, id} = route.params
      if (type === 'tx') {
        this.query = id
        this._fetchTx(id)
      } else if (type === 'address') {
        this.query = id
        this._fetchAddress(id)
      } else if (type === 'block') {
        this._openBlockByHeight(id)
      } else {
        this._resetResults()
        this.blockDialog = false
      }
    },
    _openBlockByHeight(height) {
      const h = parseInt(height, 10)
      const block =
        this.formattedBlocks.find(b => b.height === h) ||
        this.blocks.find(b => b.height === h)
      if (block) {
        this.selectedBlock = block
        this.blockDialog = true
      } else {
        this.selectedBlock = null
        this.blockDialog = false
      }
    },
    _resetResults() {
      this.txResult = null
      this.txStatus = null
      this.addressResult = null
      if (this._searchWs) {
        this._searchWs.close()
        this._searchWs = null
      }
    },
    _wsUrl(path) {
      const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      return `${proto}//${window.location.host}/blockexplorer/api/v1${path}`
    },
    _connectBlocksWs() {
      const ws = new WebSocket(this._wsUrl('/ws/blocks'))
      ws.onmessage = e => {
        const block = JSON.parse(e.data)
        const rest = this.blocks.filter(b => b.height !== block.height)
        this.blocks = [block, ...rest].slice(0, 5)
      }
      ws.onerror = () => ws.close()
      ws.onclose = () => {
        if (this._blockWsActive) setTimeout(() => this._connectBlocksWs(), 5000)
      }
      this._blockWs = ws
    },
    _connectSearchWs(path, onMessage) {
      if (this._searchWs) {
        this._searchWs.close()
        this._searchWs = null
      }
      const ws = new WebSocket(this._wsUrl(path))
      ws.onmessage = e => {
        try {
          onMessage(JSON.parse(e.data))
        } catch (_) {}
      }
      ws.onerror = () => ws.close()
      this._searchWs = ws
    },
    _timeAgo(seconds) {
      if (seconds < 60) return seconds + 's ago'
      if (seconds < 3600) return Math.floor(seconds / 60) + 'm ago'
      return Math.floor(seconds / 3600) + 'h ago'
    },
    _difficulty(bitsHex) {
      const exp = parseInt(bitsHex.slice(0, 2), 16)
      const mantissa = parseInt(bitsHex.slice(2), 16)
      const diff1 = 0xffff * Math.pow(2, 208)
      const target = mantissa * Math.pow(2, 8 * (exp - 3))
      const d = diff1 / target
      if (d >= 1e12) return (d / 1e12).toFixed(2) + 'T'
      if (d >= 1e9) return (d / 1e9).toFixed(2) + 'G'
      if (d >= 1e6) return (d / 1e6).toFixed(2) + 'M'
      return d.toFixed(0)
    },
    openBlock(b) {
      this.$router.push(`/blockexplorer/block/${b.height}`)
    },
    async loadBlocks() {
      try {
        const r = await LNbits.api.request(
          'GET',
          '/blockexplorer/api/v1/blocks'
        )
        this.blocks = r.data
      } catch (_) {}
    },
    async loadTip() {
      try {
        const r = await LNbits.api.request('GET', '/blockexplorer/api/v1/tip')
        this.tip = r.data
      } catch (e) {
        LNbits.utils.notifyApiError(e)
      }
    },
    async loadFees() {
      try {
        const r = await LNbits.api.request('GET', '/blockexplorer/api/v1/fees')
        this.fees = r.data
      } catch (_) {}
    },
    clearResult() {
      this.query = ''
      if (this.$route.path !== '/blockexplorer') {
        this.$router.push('/blockexplorer')
      } else {
        this._resetResults()
      }
    },
    search() {
      const q = this.query.trim()
      if (!q) return
      if (/^[0-9a-fA-F]{64}$/.test(q)) {
        this.loadTx(q)
      } else {
        this.loadAddress(q)
      }
    },
    loadTx(txid) {
      this.$router.push(`/blockexplorer/tx/${txid}`)
    },
    loadAddress(address) {
      this.$router.push(`/blockexplorer/address/${address}`)
    },
    async _fetchTx(txid) {
      this.loading = true
      try {
        const r = await LNbits.api.request(
          'GET',
          '/blockexplorer/api/v1/tx/' + txid
        )
        this.txResult = r.data
        this.txStatus = null
        this.addressResult = null
        this._connectSearchWs(`/ws/tx/${txid}`, data => {
          if (!data.error) this.txStatus = data
        })
      } catch (e) {
        LNbits.utils.notifyApiError(e)
      } finally {
        this.loading = false
      }
    },
    async _fetchAddress(address) {
      this.loading = true
      try {
        const r = await LNbits.api.request(
          'GET',
          '/blockexplorer/api/v1/address/' + address
        )
        this.addressResult = r.data
        this.txResult = null
        this.txStatus = null
        this.currentAddress = address
        this._connectSearchWs(`/ws/address/${address}`, data => {
          if (!data.error) this.addressResult = data
        })
      } catch (e) {
        LNbits.utils.notifyApiError(e)
      } finally {
        this.loading = false
      }
    }
  }
}
