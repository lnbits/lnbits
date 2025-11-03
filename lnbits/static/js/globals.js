window.langs = [
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
window.LOCALE = 'en'
window.dateFormat = 'YYYY-MM-DD HH:mm'
window.i18n = new VueI18n.createI18n({
  locale: window.LOCALE,
  fallbackLocale: window.LOCALE,
  messages: window.localisation
})
const websocketPrefix =
  window.location.protocol === 'http:' ? 'ws://' : 'wss://'
const websocketUrl = `${websocketPrefix}${window.location.host}/api/v1/ws`

window.g = Vue.reactive({
  offline: !navigator.onLine,
  visibleDrawer: false,
  extensions: [],
  user: null,
  wallet: {},
  fiatBalance: 0,
  exchangeRate: 0,
  fiatTracking: false,
  wallets: [],
  payments: [],
  langs: [],
  walletEventListeners: [],
  updatePayments: false,
  updatePaymentsHash: ''
})
