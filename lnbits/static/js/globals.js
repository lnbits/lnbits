const localStore = (key, defaultValue) => {
  const value = Quasar.LocalStorage.getItem(key)
  return value !== null &&
    value !== 'null' &&
    value !== undefined &&
    value !== 'undefined'
    ? value
    : defaultValue
}

window.g = Vue.reactive({
  isUserAuthorized: !!Quasar.Cookies.get('is_lnbits_user_authorized'),
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
  walletEventListeners: [],
  showNewWalletDialog: false,
  newWalletType: 'lightning',
  updatePayments: false,
  updatePaymentsHash: '',
  mobileSimple: localStore('lnbits.mobileSimple', true),
  walletFlip: localStore('lnbits.walletFlip', false),
  locale: localStore('lnbits.lang', navigator.languages[1] ?? 'en'),
  darkChoice: localStore('lnbits.darkMode', true),
  themeChoice: localStore('lnbits.theme', WINDOW_SETTINGS.LNBITS_DEFAULT_THEME),
  borderChoice: localStore(
    'lnbits.border',
    WINDOW_SETTINGS.LNBITS_DEFAULT_BORDER || 'hard-border'
  ),
  gradientChoice: localStore(
    'lnbits.gradientBg',
    WINDOW_SETTINGS.LNBITS_DEFAULT_GRADIENT || false
  ),
  reactionChoice: localStore(
    'lnbits.reactions',
    WINDOW_SETTINGS.LNBITS_DEFAULT_REACTION || 'confettiBothSides'
  ),
  bgimageChoice: localStore(
    'lnbits.backgroundImage',
    WINDOW_SETTINGS.LNBITS_DEFAULT_BGIMAGE || ''
  ),
  ads: WINDOW_SETTINGS.AD_SPACE.split(',').map(ad => ad.split(';'))
})

window.dateFormat = 'YYYY-MM-DD HH:mm'

const websocketPrefix =
  window.location.protocol === 'http:' ? 'ws://' : 'wss://'
const websocketUrl = `${websocketPrefix}${window.location.host}/api/v1/ws`

const _access_cookies_for_safari_refresh_do_not_delete = document.cookie

addEventListener('offline', event => {
  console.log('offline', event)
  this.g.offline = true
})

addEventListener('online', event => {
  console.log('back online', event)
  this.g.offline = false
})
