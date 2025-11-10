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
  },
  {
    path: '/wallet',
    name: 'Wallet',
    component: PageWallet
  }
]

window.router = VueRouter.createRouter({
  history: VueRouter.createWebHistory(),
  routes
})

window.app.use(VueQrcodeReader)
window.app.use(Quasar, {
  config: {
    loading: {
      spinner: Quasar.QSpinnerBars
    }
  }
})
window.app.use(window.i18n)
window.app.provide('g', g)
window.app.use(window.router)
window.app.mount('#vue')

if (navigator.serviceWorker != null) {
  navigator.serviceWorker.register('/service-worker.js').then(registration => {
    console.log('Registered events at scope: ', registration.scope)
  })
}
