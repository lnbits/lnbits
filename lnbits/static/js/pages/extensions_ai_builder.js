window.PageExtensionAIBuilder = {
  template: '#page-extension-ai-builder',
  data() {
    const id = this.$route.query.id
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
      footerHeight: 280,
      resizeStartHeight: null
    }
  },
  computed: {
    isEditing() {
      return this.$route.query.mode === 'edit'
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
  methods: {
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
