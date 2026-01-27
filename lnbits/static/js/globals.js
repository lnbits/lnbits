const localStore = (key, defaultValue) => {
  const value = Quasar.LocalStorage.getItem(key)
  return value !== null &&
    value !== 'null' &&
    value !== undefined &&
    value !== 'undefined'
    ? value
    : defaultValue
}

console.log('SETTINGS:', SETTINGS)

window.g = Vue.reactive({
  // vars from server
  settings: SETTINGS,
  currencies: CURRENCIES,
  extensions: SETTINGS.extensions,
  allowedCurrencies: SETTINGS.allowedCurrencies,
  denomination: SETTINGS.denomination,
  isSatsDenomination: SETTINGS.denomination == 'sats',
  // local storage vars
  themeChoice: localStore('lnbits.theme', SETTINGS.defaultTheme),
  borderChoice: localStore('lnbits.border', SETTINGS.defaultBorder),
  gradientChoice: localStore('lnbits.gradientBg', SETTINGS.defaultGradient),
  reactionChoice: localStore('lnbits.reactions', SETTINGS.defaultReaction),
  bgimageChoice: localStore(
    'lnbits.backgroundImage',
    SETTINGS.defaultBgimage || ''
  ),
  locale: localStore('lnbits.lang', navigator.languages[1] ?? 'en'),
  disclaimerShown: localStore('lnbits.disclaimerShown', false),
  isFiatPriority: localStore('lnbits.isFiatPriority', false),
  mobileSimple: localStore('lnbits.mobileSimple', true),
  walletFlip: localStore('lnbits.walletFlip', false),
  lastActiveWallet: localStore('lnbits.lastActiveWallet', null),
  darkChoice: localStore('lnbits.darkMode', true),
  // cookie vars
  isUserAuthorized: !!Quasar.Cookies.get('is_lnbits_user_authorized'),
  isUserImpersonated: !!Quasar.Cookies.get('is_lnbits_user_impersonated'),
  // frontend vars
  errorCode: null,
  errorMessage: null,
  user: null,
  wallet: null,
  isPublicPage: true,
  offline: !navigator.onLine,
  hasCamera: false,
  visibleDrawer: false,
  fiatBalance: 0,
  exchangeRate: 0,
  fiatTracking: false,
  payments: [],
  walletEventListeners: [],
  updatePayments: false, // used for updating the lnbits-payment-list
  updatePaymentsHash: false, // used for closing the receive dialog
  scanner: null,
  newWalletType: null
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

if (navigator.serviceWorker != null) {
  navigator.serviceWorker.register('/service-worker.js').then(registration => {
    console.log('Registered events at scope: ', registration.scope)
  })
}

if (navigator.mediaDevices && navigator.mediaDevices.enumerateDevices) {
  navigator.mediaDevices.enumerateDevices().then(devices => {
    window.g.hasCamera = devices.some(device => device.kind === 'videoinput')
  })
}
