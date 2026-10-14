window.PageScheduler = {
  template: '#page-scheduler',
  data() {
    return {
      jobs: [],
      sources: [],
      source: null,
      enabled: null,
      userId: '',
      loadError: false,
      requestId: 0,
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
        ['user_id', 'scheduler_user'],
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
        sortable: !['cron_expression', 'user_id'].includes(name)
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
    }
  },
  created() {
    this.fetchJobs()
  },
  beforeUnmount() {
    this.requestId++
  },
  methods: {
    userLabel(job) {
      if (!job.user_id) return '—'
      return (
        job.username ||
        job.email ||
        `${job.user_id.slice(0, 5)}...${job.user_id.slice(-5)}`
      )
    },
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
    openHistory(job = null) {
      const query = {}
      if (job) {
        query.job_id = job.id
        query.namespace = job.namespace
        if (job.user_id) query.user_id = job.user_id
      }
      this.$router.push({path: '/scheduler/runs', query})
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
      if (this.userId?.trim()) filters['user_id[like]'] = this.userId.trim()
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
