window.router = VueRouter.createRouter({
    history: VueRouter.createWebHistory(),
    routes: [  
      {
          path: '/wallet',
          name: 'Wallet',
          component: {
              template: '<div ref="content"></div>',
              async mounted() {
                  try {
                      const response = await fetch('/wallet', {
                          credentials: 'include',
                          headers: {
                              'Accept': 'text/html',
                              'X-Requested-With': 'XMLHttpRequest'
                          }
                      })
                      const html = await response.text()
                      this.$refs.content.innerHTML = html
                      this.$nextTick(() => {
                          if (this.$forceUpdate) {
                            this.$forceUpdate()
                          }
                      })
                  } catch (error) {
                      console.error('Error loading wallet:', error)
                  }
              }
          }
      }
    ]
  })
  
  window.router.beforeEach((to, from, next) => {
      console.log('Route changing from', from.path, 'to', to.path)
      next()
  })

window.app.use(VueQrcodeReader)
window.app.use(Quasar)
window.app.use(window.i18n)
window.app.use(window.router)
window.app.mount('#vue')
