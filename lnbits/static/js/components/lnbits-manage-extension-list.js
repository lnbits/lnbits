window.app.component('lnbits-manage-extension-list', {
  mixins: [window.windowMixin],
  template: '#lnbits-manage-extension-list',
  data() {
    return {
      extensions: [],
      userExtensions: [],
      searchTerm: ''
    }
  },
  watch: {
    'g.user.extensions'() {
      this.loadExtensions()
    },
    searchTerm() {
      this.filterUserExtensionsByTerm()
    }
  },
  methods: {
    async loadExtensions() {
      try {
        res = await LNbits.api.request('GET', '/api/v1/extension')
        this.extensions = res.data.sort((a, b) => a.name.localeCompare(b.name))
        this.filterUserExtensionsByTerm()
      } catch (error) {
        LNbits.utils.notifyApiError(error)
      }
    },
    filterUserExtensionsByTerm() {
      const userExts = this.g.user.extensions
      this.userExtensions = this.extensions
        .filter(o => userExts.includes(o.code))
        .filter(o => {
          if (this.searchTerm === '') return true
          return `${o.code} ${o.name} ${o.short_description} ${o.url}`
            .toLocaleLowerCase()
            .includes(this.searchTerm.toLocaleLowerCase())
        })
    }
  },
  async created() {
    await this.loadExtensions()
  }
})
