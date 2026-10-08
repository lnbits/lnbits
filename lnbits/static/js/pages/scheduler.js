window.PageScheduler = {
  template: '#page-scheduler',
  data() {
    return {
      jobs: [],
      sources: [],
      source: null,
      enabled: null,
      loadError: false,
      requestId: 0,
      history: {
        show: false,
        job: null,
        runs: [],
        status: null,
        loadError: false,
        requestId: 0,
        table: {
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
      },
      jobsTable: {
        pagination: {
          sortBy: 'next_run_at',
          descending: false,
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
        ['namespace', 'scheduler_source'],
        ['handler', 'scheduler_handler'],
        ['scope', 'scheduler_scope'],
        ['cron_expression', 'scheduler_schedule'],
        ['next_run_at', 'scheduler_next_run'],
        ['last_run_at', 'scheduler_last_run'],
        ['last_result', 'scheduler_last_result'],
        ['enabled', 'status']
      ].map(([name, label]) => ({
        name,
        field: name,
        label: this.$t(label),
        align: 'left',
        sortable: name !== 'cron_expression'
      }))
    },
    sourceOptions() {
      return this.sources.map(source => ({
        label: this.sourceLabel(source),
        value: source
      }))
    },
    statusOptions() {
      return [
        {label: this.$t('enabled'), value: true},
        {label: this.$t('scheduler_paused'), value: false}
      ]
    },
    runStatusOptions() {
      return [
        'running',
        'succeeded',
        'failed',
        'cancelled',
        'interrupted',
        'skipped'
      ].map(value => ({value, label: this.$t('scheduler_run_' + value)}))
    },
    historyColumns() {
      return [
        ...(!this.history.job ? [['job_id', 'scheduler_job']] : []),
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
    }
  },
  created() {
    this.fetchJobs()
  },
  beforeUnmount() {
    this.requestId++
    this.history.requestId++
  },
  methods: {
    sourceLabel(namespace) {
      return namespace === 'core'
        ? this.$t('scheduler_core')
        : namespace.replace(/^extension:/, '')
    },
    scheduleLabel(expression) {
      if (expression === '* * * * *') return this.$t('scheduler_every_minute')
      if (expression === '0 * * * *') return this.$t('scheduler_every_hour')
      const interval = expression.match(/^\*\/(\d+) \* \* \* \*$/)
      if (
        interval &&
        Number(interval[1]) > 1 &&
        60 % Number(interval[1]) === 0
      ) {
        return this.$t('scheduler_every_minutes', {count: Number(interval[1])})
      }
      const daily = expression.match(/^(\d{1,2}) (\d{1,2}) \* \* \*$/)
      if (daily) {
        return this.$t('scheduler_daily_at', {
          time: `${daily[2].padStart(2, '0')}:${daily[1].padStart(2, '0')}`
        })
      }
      return expression
    },
    formatNextRun(job) {
      return this.formatTime(job.next_run_at, job.timezone)
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
    relativeNextRun(job) {
      return moment.unix(job.next_run_at).fromNow()
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
    },
    openHistory(job = null) {
      this.history.job = job
      this.history.status = null
      this.history.table.search = ''
      this.history.table.pagination.page = 1
      this.history.runs = []
      this.history.show = true
      this.fetchHistory()
    },
    filterHistory() {
      this.history.table.pagination.page = 1
      this.fetchHistory()
    },
    async fetchHistory(props) {
      const requestId = ++this.history.requestId
      const filters = {}
      if (this.history.job) {
        filters.job_id = this.history.job.id
        filters.namespace = this.history.job.namespace
      }
      if (this.history.status) filters.status = this.history.status
      const params = LNbits.utils.prepareFilterQuery(
        this.history.table,
        props,
        filters
      )
      this.history.loadError = false
      try {
        const {data} = await LNbits.api.request(
          'GET',
          `/scheduler/api/v1/runs?${params}`
        )
        if (requestId !== this.history.requestId) return
        this.history.runs = data.data
        this.history.table.pagination.rowsNumber = data.total
        if (!data.data.length && this.history.table.pagination.page > 1)
          this.filterHistory()
      } catch (error) {
        if (requestId !== this.history.requestId) return
        this.history.runs = []
        this.history.table.pagination.rowsNumber = 0
        this.history.loadError = true
        LNbits.utils.notifyApiError(error)
      } finally {
        if (requestId === this.history.requestId)
          this.history.table.loading = false
      }
    },
    filterJobs() {
      this.jobsTable.pagination.page = 1
      this.fetchJobs()
    },
    async fetchJobs(props) {
      const requestId = ++this.requestId
      const filters = {}
      if (this.source) filters.namespace = this.source
      if (this.enabled !== null) filters.enabled = this.enabled
      const params = LNbits.utils.prepareFilterQuery(
        this.jobsTable,
        props,
        filters
      )
      this.loadError = false
      try {
        const [page, sources] = await Promise.all([
          LNbits.api.request('GET', `/scheduler/api/v1?${params}`),
          LNbits.api.request('GET', '/scheduler/api/v1/sources')
        ])
        if (requestId !== this.requestId) return
        this.jobs = page.data.data
        this.sources = sources.data
        this.jobsTable.pagination.rowsNumber = page.data.total
        if (!this.jobs.length && this.jobsTable.pagination.page > 1) {
          this.filterJobs()
        }
      } catch (error) {
        if (requestId !== this.requestId) return
        this.jobs = []
        this.jobsTable.pagination.rowsNumber = 0
        this.loadError = true
        LNbits.utils.notifyApiError(error)
      } finally {
        if (requestId === this.requestId) this.jobsTable.loading = false
      }
    }
  }
}
