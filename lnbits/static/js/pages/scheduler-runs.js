window.PageSchedulerRuns = {
  template: '#page-scheduler-runs',
  data() {
    return {
      runs: [],
      jobId: '',
      namespace: '',
      userId: '',
      status: null,
      loadError: false,
      requestId: 0,
      runsTable: {
        pagination: {
          sortBy: 'started_at',
          descending: true,
          page: 1,
          rowsPerPage: 10,
          rowsNumber: 0
        },
        search: '',
        loading: false
      }
    }
  },
  computed: {
    columns() {
      return [
        ['job_id', 'scheduler_job'],
        ['started_at', 'scheduler_started'],
        ['finished_at', 'scheduler_finished'],
        ['duration', 'scheduler_duration'],
        ['status', 'scheduler_result'],
        ['error_summary', 'scheduler_details']
      ].map(([name, label]) => ({
        name,
        field: name,
        label: this.$t(label),
        align: 'left',
        sortable: ['started_at', 'finished_at', 'status'].includes(name)
      }))
    },
    statusOptions() {
      return [
        'running',
        'succeeded',
        'failed',
        'cancelled',
        'interrupted',
        'skipped'
      ].map(value => ({value, label: this.$t('scheduler_run_' + value)}))
    }
  },
  watch: {
    '$route.query'() {
      this.applyQueryFilters()
      this.fetchRuns()
    }
  },
  created() {
    this.applyQueryFilters()
    this.fetchRuns()
  },
  beforeUnmount() {
    this.requestId++
  },
  methods: {
    applyQueryFilters() {
      const query = this.$route.query
      const value = name => (typeof query[name] === 'string' ? query[name] : '')
      this.jobId = value('job_id')
      this.namespace = value('namespace')
      this.userId = value('user_id')
      this.status = value('status') || null
      this.runsTable.search = value('search')
      this.runsTable.pagination.page = 1
    },
    runFilters() {
      const filters = {}
      if (this.jobId?.trim()) filters.job_id = this.jobId.trim()
      if (this.namespace?.trim()) filters.namespace = this.namespace.trim()
      if (this.userId?.trim()) filters.user_id = this.userId.trim()
      if (this.status) filters.status = this.status
      return filters
    },
    filterRuns() {
      const query = this.runFilters()
      if (this.runsTable.search?.trim())
        query.search = this.runsTable.search.trim()
      this.$router.replace({path: '/scheduler/runs', query})
    },
    async fetchRuns(props) {
      const requestId = ++this.requestId
      const params = LNbits.utils.prepareFilterQuery(
        this.runsTable,
        props,
        this.runFilters()
      )
      this.loadError = false
      try {
        const {data} = await LNbits.api.request(
          'GET',
          `/scheduler/api/v1/runs?${params}`
        )
        if (requestId !== this.requestId) return
        this.runs = data.data
        this.runsTable.pagination.rowsNumber = data.total
        if (!data.data.length && this.runsTable.pagination.page > 1) {
          this.runsTable.pagination.page = 1
          this.fetchRuns()
        }
      } catch (error) {
        if (requestId !== this.requestId) return
        this.runs = []
        this.runsTable.pagination.rowsNumber = 0
        this.loadError = true
        LNbits.utils.notifyApiError(error)
      } finally {
        if (requestId === this.requestId) this.runsTable.loading = false
      }
    },
    sourceLabel(namespace) {
      return namespace === 'core'
        ? this.$t('scheduler_core')
        : namespace.replace(/^extension:/, '')
    },
    formatTime(timestamp, timezone) {
      if (timestamp === null) return '—'
      const date = new Date(timestamp * 1000)
      try {
        return new Intl.DateTimeFormat(this.g.locale, {
          timeZone: timezone,
          year: 'numeric',
          month: 'short',
          day: 'numeric',
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit',
          timeZoneName: 'short'
        }).format(date)
      } catch {
        return date.toISOString()
      }
    },
    runColor(status) {
      return (
        {
          running: 'info',
          succeeded: 'positive',
          failed: 'negative',
          cancelled: 'warning',
          interrupted: 'warning',
          skipped: 'grey'
        }[status] || 'grey'
      )
    },
    runDuration(run) {
      if (run.finished_at === null) return '—'
      const ms = Math.max(0, (run.finished_at - run.started_at) * 1000)
      return ms < 1000 ? `${Math.round(ms)} ms` : `${(ms / 1000).toFixed(2)} s`
    }
  }
}
