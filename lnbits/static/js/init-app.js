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

window.app.mixin({
  computed: {
    isVueRoute() {
      const currentPath = window.location.pathname
      const matchedRoute = window.router.resolve(currentPath)
      const isVueRoute = matchedRoute?.matched?.length > 0
      return isVueRoute
    }
  }
})

window.app.use(VueQrcodeReader)
window.app.use(Quasar, {
  config: {
    loading: {
      spinner: Quasar.QSpinnerBars
    }
  }
})

window.i18n = new VueI18n.createI18n({
  locale: window.g.locale,
  fallbackLocale: 'en',
  messages: window.localisation
})

window.app.use(window.i18n)

window.app.provide('g', g)
window.app.use(window.router)
window.app.mount('#vue')
