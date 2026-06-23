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
      addressResult: null,
      currentAddress: ''
    }
  },
  computed: {
    feeList() {
      if (!this.fees || !this.fees.estimates) return []
      return Object.entries(this.fees.estimates).map(([blocks, rate]) => ({
        label: blocks + '-block fee',
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
  },
  methods: {
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
      this.selectedBlock = b
      this.blockDialog = true
    },
    async loadBlocks() {
      try {
        const r = await LNbits.api.request('GET', '/blockexplorer/api/v1/blocks')
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
    async search() {
      const q = this.query.trim()
      if (!q) return
      this.txResult = null
      this.addressResult = null
      this.loading = true
      try {
        if (/^[0-9a-fA-F]{64}$/.test(q)) {
          await this.loadTx(q)
        } else {
          await this.loadAddress(q)
        }
      } finally {
        this.loading = false
      }
    },
    async loadTx(txid) {
      try {
        const r = await LNbits.api.request('GET', '/blockexplorer/api/v1/tx/' + txid)
        this.txResult = r.data
        this.addressResult = null
        this.query = txid
      } catch (e) {
        LNbits.utils.notifyApiError(e)
      }
    },
    async loadAddress(address) {
      try {
        const r = await LNbits.api.request(
          'GET',
          '/blockexplorer/api/v1/address/' + address
        )
        this.addressResult = r.data
        this.txResult = null
        this.currentAddress = address
        this.query = address
      } catch (e) {
        LNbits.utils.notifyApiError(e)
      }
    }
  }
}
