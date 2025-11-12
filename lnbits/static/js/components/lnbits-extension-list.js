window.app.component('lnbits-extension-list', {
  mixins: [window.windowMixin],
  template: '#lnbits-extension-list',
  data() {
    return {
      extensions: [],
      userExtensions: [],
      searchTerm: ''
    }
  },
  watch: {
    'g.user.extensions': {
      async handler() {
        await this.loadExtensions()
      }
    },
    searchTerm() {
      this.filterUserExtensionsByTerm()
    }
  },
  methods: {
    map(data) {
      const obj = {...data}
      obj.url = ['/', obj.code, '/'].join('')
      return obj
    },
    async loadExtensions() {
      try {
        const {data} = await LNbits.api.request('GET', '/api/v1/extension')
        this.extensions = data
          .map(extension => this.map(extension))
          .sort((a, b) => a.name.localeCompare(b.name))
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
        .map(obj => {
          obj.isActive = window.location.pathname.startsWith(obj.url)
          return obj
        })
    }
  },
  async created() {
    await this.loadExtensions()
  }
})
