window.app.component('lnbits-admin-wasm-runtime', {
  props: ['form-data'],
  template: '#lnbits-admin-wasm-runtime',
  data() {
    return {
      wasmRuntimeLoading: false,
      wasmHistoryLoading: false,
      wasmRuntimeTimer: null,
      wasmStats: {},
      wasmCurrentInvocations: [],
      wasmInvocationHistory: [],
      wasmStatItems: [
        {key: 'total', label: 'Total', icon: 'data_usage', color: 'primary'},
        {key: 'running', label: 'Running', icon: 'play_circle', color: 'green'},
        {key: 'completed', label: 'Completed', icon: 'task_alt', color: 'teal'},
        {key: 'failed', label: 'Failed', icon: 'error', color: 'red'},
        {
          key: 'stopped',
          label: 'Stopped',
          icon: 'stop_circle',
          color: 'orange'
        },
        {key: 'timeout', label: 'Timeouts', icon: 'timer_off', color: 'purple'}
      ],
      wasmCurrentColumns: [
        {
          name: 'extension_id',
          label: 'Extension',
          field: 'extension_id',
          align: 'left',
          sortable: true
        },
        {
          name: 'export_name',
          label: 'Export',
          field: 'export_name',
          align: 'left',
          sortable: true
        },
        {
          name: 'trigger_type',
          label: 'Trigger',
          field: 'trigger_type',
          align: 'left',
          sortable: true
        },
        {
          name: 'status',
          label: 'Status',
          field: 'status',
          align: 'left',
          sortable: true
        },
        {
          name: 'user_id',
          label: 'User',
          field: 'user_id',
          align: 'left',
          sortable: true
        },
        {
          name: 'started_at',
          label: 'Started',
          field: 'started_at',
          align: 'left',
          sortable: true
        },
        {
          name: 'duration_ms',
          label: 'Duration',
          field: row => row.duration_ms || 0,
          align: 'right',
          sortable: true
        },
        {
          name: 'context',
          label: 'Context',
          field: row => this.wasmContextValue(row),
          align: 'left',
          sortable: true
        },
        {name: 'actions', label: '', field: 'actions', align: 'right'}
      ],
      wasmHistoryColumns: [
        {
          name: 'extension_id',
          label: 'Extension',
          field: 'extension_id',
          align: 'left',
          sortable: true
        },
        {
          name: 'export_name',
          label: 'Export',
          field: 'export_name',
          align: 'left',
          sortable: true
        },
        {
          name: 'trigger_type',
          label: 'Trigger',
          field: 'trigger_type',
          align: 'left',
          sortable: true
        },
        {
          name: 'status',
          label: 'Status',
          field: 'status',
          align: 'left',
          sortable: true
        },
        {
          name: 'user_id',
          label: 'User',
          field: 'user_id',
          align: 'left',
          sortable: true
        },
        {
          name: 'started_at',
          label: 'Started',
          field: 'started_at',
          align: 'left',
          sortable: true
        },
        {
          name: 'duration_ms',
          label: 'Duration',
          field: row => row.duration_ms || 0,
          align: 'right',
          sortable: true
        },
        {
          name: 'calls',
          label: 'Calls',
          field: row => this.wasmCallCount(row),
          align: 'left',
          sortable: true
        },
        {
          name: 'context',
          label: 'Context',
          field: row => this.wasmContextValue(row),
          align: 'left',
          sortable: true
        },
        {
          name: 'error_message',
          label: 'Error/Stop Reason',
          field: row => row.error_message || row.stop_reason || '',
          align: 'left',
          sortable: true
        }
      ]
    }
  },
  computed: {
    adminKey() {
      return this.g.user.wallets[0].adminkey
    },
    wasmExtensionId() {
      return this.$route.params.extId || null
    },
    wasmExtensionQuery() {
      if (!this.wasmExtensionId) {
        return ''
      }
      return `extension_id=${encodeURIComponent(this.wasmExtensionId)}`
    }
  },
  watch: {
    wasmExtensionId() {
      this.fetchWasmRuntime()
    }
  },
  methods: {
    async fetchWasmRuntime() {
      await Promise.all([
        this.fetchWasmCurrentInvocations(),
        this.fetchWasmInvocationHistory(),
        this.fetchWasmInvocationStats()
      ])
    },
    async fetchWasmCurrentInvocations() {
      this.wasmRuntimeLoading = true
      try {
        const query = this.wasmExtensionQuery
          ? `?${this.wasmExtensionQuery}`
          : ''
        const {data} = await LNbits.api.request(
          'GET',
          `/api/v1/extension/wasm/invocations/current${query}`,
          this.adminKey
        )
        this.wasmCurrentInvocations = data || []
      } catch (error) {
        LNbits.utils.notifyApiError(error)
      } finally {
        this.wasmRuntimeLoading = false
      }
    },
    async fetchWasmInvocationHistory() {
      this.wasmHistoryLoading = true
      try {
        const params = ['limit=50']
        if (this.wasmExtensionQuery) {
          params.push(this.wasmExtensionQuery)
        }
        const {data} = await LNbits.api.request(
          'GET',
          `/api/v1/extension/wasm/invocations?${params.join('&')}`,
          this.adminKey
        )
        this.wasmInvocationHistory = data || []
      } catch (error) {
        LNbits.utils.notifyApiError(error)
      } finally {
        this.wasmHistoryLoading = false
      }
    },
    async fetchWasmInvocationStats() {
      try {
        const params = ['hours=24']
        if (this.wasmExtensionQuery) {
          params.push(this.wasmExtensionQuery)
        }
        const {data} = await LNbits.api.request(
          'GET',
          `/api/v1/extension/wasm/invocations/stats?${params.join('&')}`,
          this.adminKey
        )
        this.wasmStats = data || {}
      } catch (error) {
        LNbits.utils.notifyApiError(error)
      }
    },
    async stopWasmInvocation(invocationId) {
      try {
        await LNbits.api.request(
          'POST',
          `/api/v1/extension/wasm/invocations/${encodeURIComponent(invocationId)}/stop`,
          this.adminKey
        )
        Quasar.Notify.create({
          type: 'positive',
          message: 'WASM invocation stop requested.'
        })
        await this.fetchWasmRuntime()
      } catch (error) {
        LNbits.utils.notifyApiError(error)
      }
    },
    deactivateWasmExtension(extensionId) {
      LNbits.utils
        .confirmDialog(
          `Deactivate extension '${extensionId}'?`,
          'Deactivate Extension'
        )
        .onOk(async () => {
          try {
            await LNbits.api.request(
              'PUT',
              `/api/v1/extension/${encodeURIComponent(extensionId)}/deactivate`,
              this.adminKey
            )
            Quasar.Notify.create({
              type: 'positive',
              message: `Extension '${extensionId}' deactivated.`
            })
            await this.fetchWasmRuntime()
          } catch (error) {
            LNbits.utils.notifyApiError(error)
          }
        })
    },
    formatWasmStat(key) {
      const value = this.wasmStats[key]
      return value === undefined || value === null ? '0' : String(value)
    },
    formatWasmDate(value) {
      return value ? this.utils.formatDate(value) : ''
    },
    wasmStatusColor(status) {
      return (
        {
          running: 'green',
          stopping: 'orange',
          completed: 'teal',
          failed: 'red',
          stopped: 'orange',
          timeout: 'purple',
          abandoned: 'grey'
        }[status] || 'grey'
      )
    },
    wasmTriggerColor(triggerType) {
      return (
        {
          http: 'primary',
          event: 'purple'
        }[triggerType] || 'grey'
      )
    },
    formatWasmDuration(row) {
      let duration = row.duration_ms
      if (
        (row.status === 'running' || row.status === 'stopping') &&
        row.started_at
      ) {
        duration = Date.now() - new Date(row.started_at).getTime()
      }
      if (duration === undefined || duration === null) {
        return ''
      }
      if (duration >= 1000) {
        return `${(duration / 1000).toFixed(1)}s`
      }
      return `${duration}ms`
    },
    formatWasmCalls(row) {
      return [
        `host ${row.host_call_count || 0}`,
        `http ${row.http_call_count || 0}`,
        `storage ${row.storage_call_count || 0}`,
        `wallet ${row.wallet_call_count || 0}`
      ].join(' / ')
    },
    wasmCallCount(row) {
      return (
        (row.host_call_count || 0) +
        (row.http_call_count || 0) +
        (row.storage_call_count || 0) +
        (row.wallet_call_count || 0)
      )
    },
    wasmContextValue(row) {
      return [
        row.method,
        row.path,
        row.event_type,
        row.wallet_id,
        row.payment_hash
      ]
        .filter(Boolean)
        .join(' ')
    },
    formatWasmContext(row) {
      const items = [
        row.method,
        row.path,
        row.event_type,
        row.wallet_id ? `wallet ${row.wallet_id}` : '',
        row.payment_hash ? `payment ${row.payment_hash.slice(0, 12)}...` : ''
      ].filter(Boolean)
      return items.join(' | ')
    },
    formatWasmUserId(userId) {
      if (!userId) {
        return '-'
      }
      const value = String(userId)
      if (value.length <= 12) {
        return value
      }
      return `${value.slice(0, 3)}...${value.slice(-3)}`
    }
  },
  created() {
    this.fetchWasmRuntime()
    this.wasmRuntimeTimer = setInterval(() => {
      this.fetchWasmCurrentInvocations()
    }, 5000)
  },
  unmounted() {
    if (this.wasmRuntimeTimer) {
      clearInterval(this.wasmRuntimeTimer)
    }
  }
})
