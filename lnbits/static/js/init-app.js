const quasarConfig = {
  config: {
    loading: {
      spinner: Quasar.QSpinnerBars
    }
  }
}

const routes = [
  {
    path: '/node',
    name: 'Node',
    component: PageNode
  },
  {
    path: '/node/public',
    name: 'NodePublic',
    component: PageNodePublic
  },
  {
    path: '/payments',
    name: 'Payments',
    component: PagePayments
  },
  {
    path: '/audit',
    name: 'Audit',
    component: PageAudit
  },
  {
    path: '/wallet',
    redirect: to => {
      const walletId = window.g?.lastActiveWallet || window.user?.wallets[0].id
      return `/wallet/${to.query.wal || walletId || 'default'}`
    }
  },
  {
    path: '/wallet/:id',
    name: 'Wallet',
    component: PageWallet
  },
  {
    path: '/wallets',
    name: 'Wallets',
    component: PageWallets
  },
  {
    path: '/users',
    name: 'Users',
    component: PageUsers
  },
  {
    path: '/admin',
    name: 'Admin',
    component: PageAdmin
  },
  {
    path: '/account',
    name: 'Account',
    component: PageAccount
  },
  {
    path: '/extensions/builder',
    name: 'ExtensionsBuilder',
    component: PageExtensionBuilder
  },
  {
    path: '/extensions',
    name: 'Extensions',
    component: PageExtensions
  },
  {
    path: '/first_install',
    name: 'FirstInstall',
    component: PageFirstInstall
  },
  {
    path: '/',
    name: 'PageHome',
    component: PageHome
  }
]

window.router = VueRouter.createRouter({
  history: VueRouter.createWebHistory(),
  routes
})

window.i18n = new VueI18n.createI18n({
  locale: window.g.locale,
  fallbackLocale: 'en',
  messages: window.localisation
})

window.app.mixin({
  data() {
    return {
      api: window._lnbitsApi,
      utils: window._lnbitsUtils,
      g: window.g,
      utils: window._lnbitsUtils,
      ...WINDOW_SETTINGS
    }
  },
  computed: {
    isVueRoute() {
      const currentPath = window.location.pathname
      const matchedRoute = window.router.resolve(currentPath)
      const isVueRoute = matchedRoute?.matched?.length > 0
      return isVueRoute
    }
  },
  // backwards compatibility for extensions, should not be used in the future
  methods: {
    copyText: window._lnbitsUtils.copyText,
    formatBalance: window._lnbitsUtils.formatBalance
  }
})

window.app.use(VueQrcodeReader)
window.app.use(Quasar, quasarConfig)

window.app.use(window.i18n)
window.app.use(window.router)
window.app.mount('#vue')
