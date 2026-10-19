window.PageExtensionAIBuilder = {
  template: '#page-extension-ai-builder',
  components: {WasmExtension: window.WasmExtensionComponent},
  data() {
    const id = this.$route.params.extId
    const mode = this.$route.query.mode
    const savedExtension = this.$q.sessionStorage.getItem(
      `lnbits.aiBuilder.${window.g.user.id}.${mode}.${id}`
    )
    return {
      extension:
        typeof id === 'string' && /^[A-Za-z0-9_-]+$/.test(id)
          ? {
              id,
              name: savedExtension?.id === id ? savedExtension.name : id,
              description:
                savedExtension?.id === id ? savedExtension.description : ''
            }
          : {id: '', name: '', description: ''},
      prompt: '',
      previewRoute: null,
      workspaceLoading: false,
      workspaceError: '',
      workspaceRequest: 0,
      messages: [],
      models: [],
      selectedModel: null,
      busy: false,
      requestPending: false,
      build: null,
      checkpoints: [],
      events: null,
      previewVersion: '',
      review: null,
      reviewAction: '',
      reviewOpen: false,
      reviewApproved: false,
      footerHeight: 280,
      resizeStartHeight: null
    }
  },
  computed: {
    canSendMessage() {
      return Boolean(
        this.g.user?.admin &&
        this.extension.id &&
        this.prompt.trim() &&
        this.selectedModel &&
        !this.busy &&
        !this.requestPending &&
        !this.workspaceLoading &&
        !this.workspaceError
      )
    },
    isEditing() {
      return this.$route.query.mode !== 'new'
    },
    maxConversationHeight() {
      return Math.max(140, this.$q.screen.height - 140)
    },
    minConversationHeight() {
      return Math.min(220, this.maxConversationHeight)
    },
    conversationHeight() {
      return Math.min(
        this.maxConversationHeight,
        Math.max(this.minConversationHeight, this.footerHeight)
      )
    }
  },
  watch: {
    '$route.fullPath': {
      immediate: true,
      handler() {
        this.loadWorkspace()
      }
    },
    messages: {
      deep: true,
      flush: 'post',
      handler() {
        const messages = this.$refs.messages
        if (messages) messages.scrollTop = messages.scrollHeight
      }
    }
  },
  beforeUnmount() {
    this.workspaceRequest++
    this.events?.close()
  },
  methods: {
    studioUrl(suffix = '') {
      return `/api/v1/extension/studio/${encodeURIComponent(this.extension.id)}${suffix}`
    },
    async loadWorkspace() {
      const request = ++this.workspaceRequest
      this.events?.close()
      this.previewRoute = null
      this.workspaceError = ''
      const id = this.$route.params.extId
      this.extension.id =
        typeof id === 'string' && /^[A-Za-z0-9_-]+$/.test(id) ? id : ''
      if (!this.extension.id || !this.g.user?.admin) {
        this.workspaceLoading = false
        return
      }
      this.workspaceLoading = true
      try {
        const {data} = await LNbits.api.request(
          'POST',
          this.studioUrl(),
          null,
          {
            new: !this.isEditing,
            name: this.extension.name,
            description: this.extension.description
          }
        )
        if (request !== this.workspaceRequest) return
        this.applyState(data)
        const models = await LNbits.api.request(
          'GET',
          '/api/v1/extension/studio/models/configured'
        )
        if (request !== this.workspaceRequest) return
        this.models = models.data
        const savedModel = this.$q.localStorage.getItem('lnbits.studio.model')
        this.selectedModel =
          this.models.find(model => model.id === savedModel && !model.disable)
            ?.id ||
          this.models.find(model => !model.disable)?.id ||
          null
        this.events = new EventSource(this.studioUrl('/events'))
        this.events.onmessage = event => {
          if (request === this.workspaceRequest)
            this.applyState(JSON.parse(event.data))
        }
      } catch (error) {
        if (request !== this.workspaceRequest) return
        this.workspaceError =
          error.response?.data?.detail || this.$t('ai_builder_load_failed')
      } finally {
        if (request === this.workspaceRequest) this.workspaceLoading = false
      }
    },
    applyState(data) {
      this.messages = data.messages
      this.busy = data.busy
      this.build = data.build
      this.checkpoints = data.checkpoints
      const version = data.build?.id || 'initial'
      if (
        data.preview_path &&
        (!this.previewRoute || version !== this.previewVersion)
      ) {
        this.previewVersion = version
        this.previewRoute = {
          path: data.preview_path,
          params: {extId: data.id},
          query: {}
        }
      }
    },
    navigatePreview(path) {
      const route = this.$router.resolve(path)
      this.previewRoute = {
        path: route.path,
        params: this.previewRoute.params,
        query: route.query
      }
    },
    handlePromptEnter(event) {
      if (event.shiftKey || event.isComposing || event.keyCode === 229) return
      event.preventDefault()
      if (!event.repeat) this.sendMessage()
    },
    async sendMessage() {
      if (!this.canSendMessage) return
      const prompt = this.prompt
      this.$q.localStorage.set('lnbits.studio.model', this.selectedModel)
      if (await this.perform('/chat', {prompt, model: this.selectedModel})) {
        this.prompt = ''
        this.$nextTick(() => this.$refs.promptInput?.focus())
      }
    },
    async perform(action, data = {}) {
      this.requestPending = true
      try {
        await LNbits.api.request('POST', this.studioUrl(action), null, data)
        const response = await LNbits.api.request('GET', this.studioUrl())
        this.applyState(response.data)
        return true
      } catch (error) {
        LNbits.utils.notifyApiError(error)
        return false
      } finally {
        this.requestPending = false
      }
    },
    async openReview(action) {
      this.requestPending = true
      try {
        const {data} = await LNbits.api.request(
          'GET',
          this.studioUrl(`/review?built=${action === 'deploy'}`)
        )
        this.review = data
        this.reviewAction = action
        this.reviewApproved = false
        this.reviewOpen = true
      } catch (error) {
        LNbits.utils.notifyApiError(error)
      } finally {
        this.requestPending = false
      }
    },
    async approveReview() {
      if (!this.reviewApproved) return
      if (
        await this.perform('/' + this.reviewAction, {
          digest: this.review.digest,
          build_id: this.review.build_id || '',
          approved: true
        })
      )
        this.reviewOpen = false
    },
    undo(checkpoint) {
      this.$q
        .dialog({
          title: 'Restore checkpoint',
          message:
            'Restore these source files? Your current source will be saved as another checkpoint. Build again to refresh the preview.',
          cancel: true
        })
        .onOk(() => this.perform('/undo', {checkpoint: checkpoint.id}))
    },
    resizeConversation({isFirst, isFinal, offset}) {
      if (isFirst) this.resizeStartHeight = this.conversationHeight
      this.footerHeight = Math.min(
        this.maxConversationHeight,
        Math.max(this.minConversationHeight, this.resizeStartHeight - offset.y)
      )
      if (isFinal) this.resizeStartHeight = null
    },
    adjustConversationHeight(delta) {
      this.footerHeight = Math.min(
        this.maxConversationHeight,
        Math.max(this.minConversationHeight, this.conversationHeight + delta)
      )
    }
  }
}
