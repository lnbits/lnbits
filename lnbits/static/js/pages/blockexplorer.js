window.PageBlockExplorer = {
  template: '#page-blockexplorer',
  data() {
    return {
      query: '',
      loading: false,
      tip: null,
      fees: null,
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
    }
  },
  async created() {
    await Promise.all([this.loadTip(), this.loadFees()])
  },
  methods: {
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
        const r = await LNbits.api.request(
          'GET',
          '/blockexplorer/api/v1/tx/' + txid
        )
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
