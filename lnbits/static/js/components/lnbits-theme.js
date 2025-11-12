window.app.component('lnbits-theme', {
  mixins: [window.windowMixin],
  watch: {
    'g.reactionChoice'(val) {
      this.$q.localStorage.set('lnbits.reactions', val)
    },
    'g.themeChoice'(val) {
      document.body.setAttribute('data-theme', val)
      this.$q.localStorage.set('lnbits.theme', val)
    },
    'g.darkChoice'(val) {
      this.$q.dark.set(val)
      this.$q.localStorage.set('lnbits.darkMode', val)
    },
    'g.borderChoice'(val) {
      document.body.classList.forEach(cls => {
        if (cls.endsWith('-border')) {
          document.body.classList.remove(cls)
        }
      })
      this.$q.localStorage.setItem('lnbits.border', val)
      document.body.classList.add(val)
    },
    'g.gradientChoice'(val) {
      this.$q.localStorage.set('lnbits.gradientBg', val)
      if (val === true) {
        document.body.classList.add('gradient-bg')
      } else {
        document.body.classList.remove('gradient-bg')
      }
    },
    'g.bgimageChoice'(val) {
      this.$q.localStorage.set('lnbits.backgroundImage', val)
      if (val === '') {
        document.body.classList.remove('bg-image')
      } else {
        document.body.classList.add('bg-image')
        document.body.style.setProperty('--background', `url(${val})`)
      }
    }
  },
  methods: {
    async checkUrlParams() {
      const params = new URLSearchParams(window.location.search)
      if (params.length === 0) {
        return
      }
      if (params.has('theme')) {
        const theme = params.get('theme').trim().toLowerCase()
        this.g.themeChoice = theme
        params.delete('theme')
      }
      if (params.has('border')) {
        const border = params.get('border').trim().toLowerCase()
        this.g.borderChoice = border
        params.delete('border')
      }
      if (params.has('gradient')) {
        const gradient = params.get('gradient').toLowerCase()
        this.g.gradientChoice = gradient === '1' || gradient === 'true'
        params.delete('gradient')
      }
      if (params.has('dark')) {
        const dark = params.get('dark').trim().toLowerCase()
        this.g.darkChoice = dark === '1' || dark === 'true'
        params.delete('dark')
      }

      if (params.has('usr')) {
        try {
          await LNbits.api.loginUsr(params.get('usr'))
          window.location.href = '/wallet'
        } catch (e) {
          LNbits.utils.notifyApiError(e)
        }
        params.delete('usr')
      }

      // cleanup url
      const cleanParams = params.size ? `?${params.toString()}` : ''
      const url = window.location.pathname + cleanParams

      // TODO state gets overridden somewhere else
      window.history.replaceState(null, null, url)
    }
  },
  created() {
    // TODO: fix Chart global import each chart has to take care of its own config
    // else there is no reactivity on theme change
    Chart.defaults.color = this.$q.dark.isActive ? '#fff' : '#000'

    this.$q.dark.set(this.g.darkChoice)
    document.body.setAttribute('data-theme', this.g.themeChoice)
    document.body.classList.add(this.g.borderChoice)
    if (this.g.gradientChoice === true) {
      document.body.classList.add('gradient-bg')
    }
    if (this.g.bgimageChoice !== '') {
      document.body.classList.add('bg-image')
      document.body.style.setProperty(
        '--background',
        `url(${this.g.bgimageChoice})`
      )
    }
    this.checkUrlParams()
  }
})
