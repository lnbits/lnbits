const quasarConfig = {
  config: {
    loading: {
      spinner: Quasar.QSpinnerBars
    },
    table: {
      rowsPerPageOptions: [5, 10, 20, 50, 100, 200, 500, 0]
    }
  }
}

const DynamicComponent = {
  async created() {
    const name = this.$route.path.split('/')[1]
    const path = `/${name}/`
    const routesPath = `/${name}/static/routes.json`
    const hasPath = this.$router.getRoutes().some(r => r.path === path)
    if (hasPath) {
      console.log('Dynamic route already exists for extension:', name)
      return
    }
    fetch(routesPath)
      .then(async res => {
        if (!res.ok) {
          throw new Error('No dynamic routes found')
        }
        const routes = await res.json()
        routes.forEach(r => {
          console.log('Adding dynamic route:', r.path)
          window.router.addRoute({
            path: r.path,
            name: r.name,
            component: async () => {
              await LNbits.utils.loadTemplate(r.template)
              await LNbits.utils.loadScript(r.component)
              return window[r.name]
            }
          })
          window.router.push(this.$route.fullPath)
        })
      })
      .catch(() => {
        if (RENDERED_ROUTE !== path) {
          console.log('Redirecting to non-vue route:', path)
          window.location = path
          return
        }
      })
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
      const walletId =
        window.g?.lastActiveWallet || window.g?.user?.wallets[0].id
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
  },
  {
    path: '/error',
    name: 'PageError',
    component: PageError
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'DynamicComponent',
    component: DynamicComponent
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
      ...WINDOW_SETTINGS
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
