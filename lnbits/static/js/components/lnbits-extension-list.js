window.app.component('lnbits-extension-list', {
  mixins: [window.windowMixin],
  template: '#lnbits-extension-list',
  data() {
    return {
      extensions: [],
      searchTerm: ''
    }
  },
  watch: {
    'g.user.extensions': {
      handler(newExtensions) {
        this.loadExtensions()
      },
      deep: true
    }
  },
  computed: {
    userExtensions() {
      return this.updateUserExtensions(this.searchTerm)
    }
  },
  methods: {
    async loadExtensions() {
      try {
        const {data} = await LNbits.api.request('GET', '/api/v1/extension')
        this.extensions = data
          .map(extension => LNbits.map.extension(extension))
          .sort((a, b) => a.name.localeCompare(b.name))
      } catch (error) {
        LNbits.utils.notifyApiError(error)
      }
    },
    updateUserExtensions(filterBy) {
      const path = window.location.pathname
      const userExtensions = this.g.user.extensions

      return this.extensions
        .filter(o => userExtensions.includes(o.code))
        .filter(o => {
          if (!filterBy) return true
          return `${o.code} ${o.name} ${o.short_description} ${o.url}`
            .toLocaleLowerCase()
            .includes(filterBy.toLocaleLowerCase())
        })
        .map(obj => {
          obj.isActive = path.startsWith(obj.url)
          return obj
        })
    }
  },
  async created() {
    await this.loadExtensions()
  }
})
