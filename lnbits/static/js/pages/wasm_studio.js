window.PageWasmStudio = {
  template: '#page-wasm-studio',
  data() {
    return {
      formData: {lnbits_wasm_studio_models: []},
      providers: Object.entries({
        alibaba: 'Alibaba Cloud / Qwen',
        anthropic: 'Anthropic',
        bedrock: 'AWS Bedrock',
        azure: 'Azure / Foundry',
        cerebras: 'Cerebras',
        cohere: 'Cohere',
        crusoe: 'Crusoe',
        deepseek: 'DeepSeek',
        fireworks: 'Fireworks AI',
        'github-copilot': 'GitHub Copilot',
        google: 'Google Gemini',
        'google-cloud': 'Google Cloud / Vertex AI',
        groq: 'Groq',
        heroku: 'Heroku AI',
        huggingface: 'Hugging Face',
        litellm: 'LiteLLM',
        meta: 'Meta',
        mistral: 'Mistral',
        moonshotai: 'Moonshot AI / Kimi',
        nebius: 'Nebius AI Studio',
        ollama: 'Ollama',
        openai: 'OpenAI',
        'openai-codex': 'OpenAI Codex',
        'openai-decisions': 'OpenAI Decisions',
        openrouter: 'OpenRouter',
        ovhcloud: 'OVHcloud AI Endpoints',
        gateway: 'Pydantic AI Gateway',
        sambanova: 'SambaNova',
        snowflake: 'Snowflake Cortex',
        'system-one': 'System One API',
        together: 'Together AI',
        typesafe: 'TypeSafe',
        vercel: 'Vercel AI Gateway',
        vllm: 'vLLM',
        xai: 'xAI',
        zai: 'Z.AI',
        'openai-compatible': 'Other OpenAI-compatible API'
      }).map(([value, label]) => ({value, label})),
      loading: false,
      loadError: false,
      saving: false,
      removing: null,
      showAddDialog: false,
      form: {
        name: '',
        provider: null,
        model: '',
        api_key: '',
        base_url: ''
      }
    }
  },
  created() {
    if (this.g.user?.admin) this.loadSettings()
  },
  computed: {
    models() {
      return this.formData.lnbits_wasm_studio_models
    }
  },
  methods: {
    async loadSettings() {
      this.loading = true
      this.loadError = false
      try {
        const {data} = await LNbits.api.request('GET', '/admin/api/v1/settings')
        this.formData.lnbits_wasm_studio_models =
          data.lnbits_wasm_studio_models || []
      } catch (error) {
        this.loadError = true
        LNbits.utils.notifyApiError(error)
      } finally {
        this.loading = false
      }
    },
    providerName(provider) {
      return (
        this.providers.find(option => option.value === provider)?.label ||
        provider
      )
    },
    required(value) {
      return !!value?.trim() || this.$t('wasm_studio_required')
    },
    validateModel(value) {
      return !/\s/.test(value) || this.$t('wasm_studio_model_invalid')
    },
    validateBaseUrl(value) {
      if (!value) return true
      try {
        const url = new URL(value)
        if (
          ['http:', 'https:'].includes(url.protocol) &&
          url.hostname &&
          !url.username &&
          !url.password &&
          !url.search &&
          !url.hash &&
          !/\s/.test(value)
        )
          return true
      } catch {}
      return this.$t('wasm_studio_base_url_invalid')
    },
    resetForm() {
      this.form = {
        name: '',
        provider: null,
        model: '',
        api_key: '',
        base_url: ''
      }
    },
    async addModel() {
      if (this.saving) return
      if (await this.saveSettings([...this.models, {...this.form}])) {
        this.resetForm()
        this.showAddDialog = false
      }
    },
    confirmRemove(model, index) {
      LNbits.utils
        .confirmDialog(
          this.$t('wasm_studio_remove_confirm', {name: model.name})
        )
        .onOk(() => this.removeModel(index))
    },
    async removeModel(index) {
      if (this.saving) return
      this.removing = index
      try {
        await this.saveSettings(this.models.filter((_, i) => i !== index))
      } finally {
        this.removing = null
      }
    },
    async saveSettings(models) {
      this.saving = true
      try {
        await LNbits.api.request('PUT', '/admin/api/v1/settings', null, {
          lnbits_wasm_studio_models: models
        })
        this.formData.lnbits_wasm_studio_models = models
        return true
      } catch (error) {
        if (error.response) {
          LNbits.utils.notifyApiError({response: error.response})
        } else {
          this.$q.notify({
            type: 'negative',
            message: this.$t('wasm_studio_save_failed')
          })
        }
        return false
      } finally {
        this.saving = false
      }
    }
  }
}
