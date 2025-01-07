const DynamicComponent = {
  props: {
    fetchUrl: {
      type: String,
      required: true
    },
    scripts: {
      type: Array,
      default: () => []
    }
  },
  async mounted() {
    console.log('Component mounted.')
    await this.loadDynamicContent()
  },
  methods: {
    async loadScript(src) {
      return new Promise((resolve, reject) => {
        const existingScript = document.querySelector(`script[src="${src}"]`)
        if (existingScript) {
          existingScript.remove()
        }
        const script = document.createElement('script')
        script.src = src
        script.async = true
        script.onload = resolve
        script.onerror = () =>
          reject(new Error(`Failed to load script: ${src}`))
        document.head.appendChild(script)
      })
    },
    async loadDynamicContent() {
      try {
        console.log('Fetching content from:', this.fetchUrl)

        //grab page content, need to be before loading scripts
        const response = await fetch(this.fetchUrl, {
          credentials: 'include',
          headers: {
            Accept: 'text/html',
            'X-Requested-With': 'XMLHttpRequest'
          }
        })

        const html = await response.text()

        // load window variables
        const parser = new DOMParser()
        const htmlDocument = parser.parseFromString(html, 'text/html')
        const inlineScript = htmlDocument.querySelector('#window-vars-script')
        if (inlineScript) {
          console.log('Executing inline script:', inlineScript.innerHTML)
          new Function(inlineScript.innerHTML)() // Execute the script
        }

        //load scripts defined in the route
        for (const script of this.scripts) {
          await this.loadScript(script)
        }

        //housecleaning, remove old component
        const previousRouteName =
          this.$router.currentRoute.value.meta.previousRouteName
        if (
          previousRouteName &&
          window.app._context.components[previousRouteName]
        ) {
          console.log(
            `Removing component for previous route: ${previousRouteName}`
          )
          delete window.app._context.components[previousRouteName]
        }

        //load component logic
        const logicKey = `${this.$route.name}PageLogic`
        const componentLogic = window[logicKey]

        if (!componentLogic) {
          throw new Error(
            `Component logic '${logicKey}' not found. Ensure it is defined in the script.`
          )
        }

        //Add mixins
        componentLogic.mixins = componentLogic.mixins || []
        if (window.windowMixin) {
          componentLogic.mixins.push(window.windowMixin)
        }

        //Build component
        window.app.component(this.$route.name, {
          ...componentLogic,
          template: html // Use the fetched HTML as the template
        })
        this.$forceUpdate()
      } catch (error) {
        console.error('Error loading dynamic content:', error)
      }
    }
  },
  watch: {
    $route(to, from) {
      const validRouteNames = routes.map(route => route.name)
      if (validRouteNames.includes(to.name)) {
        this.$router.currentRoute.value.meta.previousRouteName = from.name
        this.loadDynamicContent()
      } else {
        console.warn(
          `Route '${to.name}' is not valid. Leave this one to ol'Fastapi.`
        )
      }
    }
  },
  template: '<component :is="$route.name"></component>'
}

//Routes, could be defined in a separate file and added to by extensions
const routes = [
  {
    path: '/wallet',
    name: 'Wallet',
    component: DynamicComponent,
    props: {
      fetchUrl: '/wallet',
      scripts: ['/static/js/wallet.js']
    }
  },
  {
    path: '/admin',
    name: 'Admin',
    component: DynamicComponent,
    props: {
      fetchUrl: '/admin',
      scripts: ['/static/js/admin.js']
    }
  },
  {
    path: '/users',
    name: 'Users',
    component: DynamicComponent,
    props: {
      fetchUrl: '/users',
      scripts: ['/static/js/users.js']
    }
  },
  {
    path: '/audit',
    name: 'Audit',
    component: DynamicComponent,
    props: {
      fetchUrl: '/audit',
      scripts: ['/static/js/audit.js']
    }
  },
  {
    path: '/extensions',
    name: 'Extensions',
    component: DynamicComponent,
    props: {
      fetchUrl: '/extensions',
      scripts: ['/static/js/extensions.js']
    }
  }
]

window.router = VueRouter.createRouter({
  history: VueRouter.createWebHistory(),
  routes
})

window.app.mixin({
  computed: {
    isVueRoute() {
      const vueRoutes = window.router.options.routes.map(route => route.path);
      return vueRoutes.includes(window.location.pathname);
    }
  }
});

window.app.use(VueQrcodeReader)
window.app.use(Quasar)
window.app.use(window.i18n)
window.app.use(window.router)
window.app.component('DynamicComponent', DynamicComponent)
window.app.mount('#vue')
