window.app.component('lnbits-language-dropdown', {
  template: '#lnbits-language-dropdown',
  mixins: [window.windowMixin],
  methods: {
    activeLanguage(lang) {
      return window.i18n.global.locale === lang
    },
    changeLanguage(newValue) {
      this.g.locale = newValue
      window.i18n.global.locale = newValue
      this.$q.localStorage.set('lnbits.lang', newValue)
    }
  },
  data() {
    return {
      langs: [
        {value: 'en', label: 'English', display: '🇬🇧 EN'},
        {value: 'de', label: 'Deutsch', display: '🇩🇪 DE'},
        {value: 'es', label: 'Español', display: '🇪🇸 ES'},
        {value: 'jp', label: '日本語', display: '🇯🇵 JP'},
        {value: 'cn', label: '中文', display: '🇨🇳 CN'},
        {value: 'fr', label: 'Français', display: '🇫🇷 FR'},
        {value: 'it', label: 'Italiano', display: '🇮🇹 IT'},
        {value: 'pi', label: 'Pirate', display: '🏴‍☠️ PI'},
        {value: 'nl', label: 'Nederlands', display: '🇳🇱 NL'},
        {value: 'we', label: 'Cymraeg', display: '🏴󠁧󠁢󠁷󠁬󠁳󠁿 CY'},
        {value: 'pl', label: 'Polski', display: '🇵🇱 PL'},
        {value: 'pt', label: 'Português', display: '🇵🇹 PT'},
        {value: 'br', label: 'Português do Brasil', display: '🇧🇷 BR'},
        {value: 'cs', label: 'Česky', display: '🇨🇿 CS'},
        {value: 'sk', label: 'Slovensky', display: '🇸🇰 SK'},
        {value: 'kr', label: '한국어', display: '🇰🇷 KR'},
        {value: 'fi', label: 'Suomi', display: '🇫🇮 FI'}
      ]
    }
  }
})
