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
      blockTransactions: [],
      blockTransactionsLoading: false,
      blockTransactionsError: '',
      blockTransactionsOffset: 0,
      blockTransactionsHasMore: false,
      blockTransactionPageSize: 12,
      txResult: null,
      txStatus: null,
      addressResult: null,
      currentAddress: '',
      addressHistoryPage: 1,
      addressHistoryPageSize: 20
    }
  },
  computed: {
    explorerPath() {
      return this.g.isPublicPage ? '/blockexplorer/public' : '/blockexplorer'
    },
    feeList() {
      if (!this.fees || !this.fees.estimates) return []
      return Object.entries(this.fees.estimates).map(([blocks, rate]) => ({
        label: this.$t('n_block_fee', {n: blocks}),
        rate: (rate * 100000).toFixed(1) + ' sat/vB'
      }))
    },
    recentBlocks() {
      return this.formattedBlocks.slice(0, 10)
    },
    blockIntervals() {
      const blocks = [...this.blocks].sort((a, b) => a.height - b.height)
      return blocks.slice(1).map((block, index) => ({
        height: block.height,
        minutes: Math.max(0, (block.timestamp - blocks[index].timestamp) / 60)
      }))
    },
    averageBlockInterval() {
      if (!this.blockIntervals.length) return '—'
      const total = this.blockIntervals.reduce(
        (sum, block) => sum + block.minutes,
        0
      )
      return this.$t('minutes_short', {
        value: (total / this.blockIntervals.length).toFixed(1)
      })
    },
    feeHistogramEntries() {
      if (!this.fees || !Array.isArray(this.fees.histogram)) return []
      return this.fees.histogram
        .map(entry => ({
          feeRate: Number(entry.fee_rate ?? entry[0]),
          vsize: Number(entry.vsize ?? entry[1])
        }))
        .filter(
          entry =>
            Number.isFinite(entry.feeRate) && Number.isFinite(entry.vsize)
        )
    },
    projectedBlocks() {
      const blockCapacity = 1000000
      const blocks = []
      let current = null

      const entries = [...this.feeHistogramEntries].sort(
        (a, b) => b.feeRate - a.feeRate
      )
      for (const entry of entries) {
        let remaining = entry.vsize
        while (remaining > 0) {
          if (!current || current.vsize >= blockCapacity) {
            if (blocks.length >= 5) break
            current = {vsize: 0, weightedFees: 0}
            blocks.push(current)
          }
          const amount = Math.min(blockCapacity - current.vsize, remaining)
          current.vsize += amount
          current.weightedFees += amount * entry.feeRate
          remaining -= amount
        }
        if (blocks.length >= 5 && current.vsize >= blockCapacity) break
      }

      return blocks.map((block, index) => ({
        id: `projected-${index}-${Math.round(
          block.weightedFees / Math.max(block.vsize, 1)
        )}`,
        label:
          index === 0
            ? this.$t('next_block')
            : this.$t('projected_block', {number: index + 1}),
        feeRate: block.weightedFees / Math.max(block.vsize, 1),
        vsize: block.vsize / blockCapacity,
        fill: Math.min(block.vsize / blockCapacity, 1)
      }))
    },
    projectedBlocksDisplay() {
      return [...this.projectedBlocks].reverse()
    },
    mempoolHistogram() {
      const entries = this.feeHistogramEntries
      if (!entries.length) return []
      const bucketSize = Math.max(1, Math.ceil(entries.length / 24))
      const buckets = []
      for (let i = 0; i < entries.length; i += bucketSize) {
        const group = entries.slice(i, i + bucketSize)
        const vsize = group.reduce((sum, entry) => sum + entry.vsize, 0)
        const weightedFees = group.reduce(
          (sum, entry) => sum + entry.feeRate * entry.vsize,
          0
        )
        buckets.push({
          feeRate: vsize ? weightedFees / vsize : group[0].feeRate,
          vsize
        })
      }
      return buckets.sort((a, b) => a.feeRate - b.feeRate)
    },
    mempoolSize() {
      const vsize = this.feeHistogramEntries.reduce(
        (sum, entry) => sum + entry.vsize,
        0
      )
      return `${(vsize / 1000000).toFixed(1)} MvB`
    },
    addressHistory() {
      return this.addressResult?.history || []
    },
    addressHistoryPages() {
      return Math.ceil(this.addressHistory.length / this.addressHistoryPageSize)
    },
    paginatedAddressHistory() {
      const start = (this.addressHistoryPage - 1) * this.addressHistoryPageSize
      return this.addressHistory.slice(
        start,
        start + this.addressHistoryPageSize
      )
    },
    addressHistoryRange() {
      if (!this.addressHistory.length) return ''
      const start =
        (this.addressHistoryPage - 1) * this.addressHistoryPageSize + 1
      const end = Math.min(
        start + this.addressHistoryPageSize - 1,
        this.addressHistory.length
      )
      return this.$t('pagination_range', {
        start,
        end,
        total: this.addressHistory.length
      })
    },
    formattedBlocks() {
      const now = Math.floor(Date.now() / 1000)
      return this.blocks.map((b, index) => {
        const previousBlock = this.blocks[index + 1]
        const intervalMinutes = previousBlock
          ? Math.max(0, (b.timestamp - previousBlock.timestamp) / 60)
          : null
        return {
          ...b,
          shortHash: b.hash.slice(0, 8) + '...' + b.hash.slice(-4),
          timeAgo: this._timeAgo(now - b.timestamp),
          utcTime: new Date(b.timestamp * 1000).toUTCString(),
          difficulty: this._difficulty(b.bits),
          intervalMinutes,
          intervalRatio:
            intervalMinutes === null
              ? 0
              : Math.min(Math.max(intervalMinutes / 20, 0.04), 1)
        }
      })
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
    if (this._blockIntervalChart) this._blockIntervalChart.destroy()
    if (this._mempoolChart) this._mempoolChart.destroy()
  },
  watch: {
    blocks() {
      this._scheduleChartRender()
    },
    fees() {
      this._scheduleChartRender()
    },
    '$q.dark.isActive'() {
      this._scheduleChartRender()
    },
    $route(to) {
      this._loadFromRoute(to)
    }
  },
  methods: {
    _loadFromRoute(route) {
      route = route || this.$route
      const {type, id} = route.params
      if (type === 'tx') {
        this._resetBlockResult()
        this.query = id
        this._fetchTx(id)
      } else if (type === 'address') {
        this._resetBlockResult()
        this.query = id
        this._fetchAddress(id)
      } else if (type === 'block') {
        this._openBlockByHeight(id)
      } else {
        this._resetResults()
        this._resetBlockResult()
      }
    },
    _openBlockByHeight(height) {
      const h = parseInt(height, 10)
      const block =
        this.formattedBlocks.find(b => b.height === h) ||
        this.blocks.find(b => b.height === h)
      if (block) {
        this._resetResults()
        this.selectedBlock = block
        this.loadBlockTransactions(h, 0)
      } else {
        this._resetBlockResult()
      }
    },
    _resetBlockResult() {
      this.selectedBlock = null
      this.blockTransactions = []
      this.blockTransactionsError = ''
      this.blockTransactionsOffset = 0
      this.blockTransactionsHasMore = false
    },
    _resetResults() {
      this.txResult = null
      this.txStatus = null
      this.addressResult = null
      this.addressHistoryPage = 1
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
        this.blocks = [block, ...rest].slice(0, 10)
        this.loadFees()
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
    _scheduleChartRender() {
      if (this._chartRenderPending) return
      this._chartRenderPending = true
      this.$nextTick(() => {
        this._chartRenderPending = false
        this._renderCharts()
      })
    },
    _themeColor(name, fallback) {
      const value = window
        .getComputedStyle(document.documentElement)
        .getPropertyValue(`--q-${name}`)
        .trim()
      return value || fallback
    },
    _chartOptions(yTitle, xTitle = '') {
      const textColor = this.$q.dark.isActive ? '#eeeeee' : '#424242'
      const gridColor = this.$q.dark.isActive
        ? 'rgba(255, 255, 255, 0.12)'
        : 'rgba(0, 0, 0, 0.12)'
      return {
        responsive: true,
        maintainAspectRatio: true,
        animation: false,
        interaction: {intersect: false, mode: 'index'},
        plugins: {
          legend: {labels: {color: textColor}}
        },
        scales: {
          x: {
            title: {display: Boolean(xTitle), text: xTitle, color: textColor},
            ticks: {color: textColor, maxRotation: 0},
            grid: {display: false}
          },
          y: {
            beginAtZero: true,
            title: {display: true, text: yTitle, color: textColor},
            ticks: {color: textColor},
            grid: {color: gridColor}
          }
        }
      }
    },
    _renderCharts() {
      this._renderBlockIntervalChart()
      this._renderMempoolChart()
    },
    _renderBlockIntervalChart() {
      const canvas = this.$refs.blockIntervalChart
      if (!canvas || !this.blockIntervals.length || !window.Chart) return
      if (this._blockIntervalChart) this._blockIntervalChart.destroy()
      const primary = this._themeColor('primary', '#21ba45')
      const secondary = this._themeColor('secondary', '#26a69a')
      this._blockIntervalChart = new Chart(canvas.getContext('2d'), {
        type: 'line',
        data: {
          labels: this.blockIntervals.map(block =>
            block.height.toLocaleString()
          ),
          datasets: [
            {
              label: this.$t('observed_block_time'),
              data: this.blockIntervals.map(block =>
                Number(block.minutes.toFixed(2))
              ),
              borderColor: primary,
              backgroundColor: primary,
              pointRadius: 3,
              tension: 0.3
            },
            {
              label: this.$t('target_block_time'),
              data: this.blockIntervals.map(() => 10),
              borderColor: secondary,
              backgroundColor: secondary,
              pointRadius: 0,
              borderDash: [6, 6]
            }
          ]
        },
        options: this._chartOptions(this.$t('minutes'), this.$t('block_height'))
      })
    },
    _renderMempoolChart() {
      const canvas = this.$refs.mempoolChart
      if (!canvas || !this.mempoolHistogram.length || !window.Chart) return
      if (this._mempoolChart) this._mempoolChart.destroy()
      const secondary = this._themeColor('secondary', '#26a69a')
      this._mempoolChart = new Chart(canvas.getContext('2d'), {
        type: 'bar',
        data: {
          labels: this.mempoolHistogram.map(bucket =>
            bucket.feeRate < 10
              ? bucket.feeRate.toFixed(1)
              : bucket.feeRate.toFixed(0)
          ),
          datasets: [
            {
              label: this.$t('mempool_virtual_size'),
              data: this.mempoolHistogram.map(bucket =>
                Number((bucket.vsize / 1000000).toFixed(3))
              ),
              backgroundColor: secondary,
              borderColor: secondary,
              borderWidth: 1
            }
          ]
        },
        options: this._chartOptions(
          this.$t('virtual_size_mb'),
          this.$t('fee_rate_axis')
        )
      })
    },
    openBlock(b) {
      this.$router.push(`${this.explorerPath}/block/${b.height}`)
    },
    closeBlock() {
      this.$router.push(this.explorerPath)
    },
    async loadBlockTransactions(height, offset) {
      this.blockTransactionsLoading = true
      this.blockTransactionsError = ''
      try {
        const r = await LNbits.api.request(
          'GET',
          `/blockexplorer/api/v1/block/${height}/transactions?offset=${offset}&limit=${this.blockTransactionPageSize}`
        )
        this.blockTransactions = r.data.transactions
        this.blockTransactionsOffset = r.data.offset
        this.blockTransactionsHasMore = r.data.has_more
      } catch (e) {
        this.blockTransactions = []
        this.blockTransactionsError =
          e.response?.data?.detail || this.$t('block_transactions_unavailable')
      } finally {
        this.blockTransactionsLoading = false
      }
    },
    previousBlockTransactions() {
      this.loadBlockTransactions(
        this.selectedBlock.height,
        Math.max(
          0,
          this.blockTransactionsOffset - this.blockTransactionPageSize
        )
      )
    },
    nextBlockTransactions() {
      this.loadBlockTransactions(
        this.selectedBlock.height,
        this.blockTransactionsOffset + this.blockTransactionPageSize
      )
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
      if (this.$route.path !== this.explorerPath) {
        this.$router.push(this.explorerPath)
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
      this.$router.push(`${this.explorerPath}/tx/${txid}`)
    },
    loadAddress(address) {
      this.$router.push(`${this.explorerPath}/address/${address}`)
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
      this.addressHistoryPage = 1
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
          if (!data.error) {
            this.addressResult = data
            this.addressHistoryPage = Math.min(
              this.addressHistoryPage,
              Math.max(1, this.addressHistoryPages)
            )
          }
        })
      } catch (e) {
        LNbits.utils.notifyApiError(e)
      } finally {
        this.loading = false
      }
    }
  }
}
