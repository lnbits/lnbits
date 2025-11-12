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
  walletEventListeners: [],
  updatePayments: false,
  updatePaymentsHash: '',
  walletFlip: Quasar.LocalStorage.getItem('lnbits.walletFlip') ?? false,
  locale:
    Quasar.LocalStorage.getItem('lnbits.lang') ?? navigator.languages[1] ?? 'en'
})

window.dateFormat = 'YYYY-MM-DD HH:mm'

const websocketPrefix =
  window.location.protocol === 'http:' ? 'ws://' : 'wss://'
const websocketUrl = `${websocketPrefix}${window.location.host}/api/v1/ws`
