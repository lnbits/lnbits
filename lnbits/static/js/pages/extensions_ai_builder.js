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
      footerHeight: 280,
      resizeStartHeight: null
    }
  },
  computed: {
    canSendMessage() {
      return Boolean(
        this.g.user?.admin && this.extension.id && this.prompt.trim()
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
  methods: {
    async loadWorkspace() {
      const request = ++this.workspaceRequest
      this.previewRoute = null
      this.workspaceError = ''
      const id = this.$route.params.extId
      this.extension.id =
        typeof id === 'string' && /^[A-Za-z0-9_-]+$/.test(id) ? id : ''
      if (!this.isEditing || !this.extension.id || !this.g.user?.admin) {
        this.workspaceLoading = false
        return
      }
      this.workspaceLoading = true
      try {
        const {data} = await LNbits.api.request(
          'POST',
          `/api/v1/extension/${encodeURIComponent(id)}/studio`
        )
        if (request !== this.workspaceRequest) return
        this.extension = {id, name: data.name, description: data.description}
        this.previewRoute = {
          path: data.preview_path,
          params: {extId: data.id},
          query: {}
        }
      } catch (error) {
        if (request !== this.workspaceRequest) return
        this.workspaceError =
          error.response?.data?.detail || this.$t('ai_builder_load_failed')
      } finally {
        if (request === this.workspaceRequest) this.workspaceLoading = false
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
    sendMessage() {
      if (!this.canSendMessage) return
      this.messages.push({role: 'user', content: this.prompt})
      this.prompt = ''
      this.$nextTick(() => this.$refs.promptInput?.focus())
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
