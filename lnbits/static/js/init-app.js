function loadScript(src) {
    return new Promise((resolve, reject) => {
      const script = document.createElement('script');
      script.src = src;
      script.async = true;
      script.onload = resolve;
      script.onerror = reject;
      document.head.appendChild(script);
    });
  }
  
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
              // Fetch and inject the HTML
              const response = await fetch('/wallet', {
                credentials: 'include',
                headers: {
                  'Accept': 'text/html',
                  'X-Requested-With': 'XMLHttpRequest',
                },
              });
              const html = await response.text();
              this.$refs.content.innerHTML = html;
  
              // Dynamically load the wallet.js script
              await loadScript('/static/js/wallet.js');
  
              // Initialize the wallet app if necessary
              if (window.app && typeof window.app.mount === 'function') {
                window.app.mount(this.$refs.content); // Adjust the mount target if needed
              }
  
              this.$forceUpdate();
            } catch (error) {
              console.error('Error loading wallet:', error);
            }
          },
        },
      },
    ],
  });
  
  window.router.beforeEach((to, from, next) => {
    console.log('Route changing from', from.path, 'to', to.path);
    next();
  });
  
  // Initialize Vue app
  window.app.use(VueQrcodeReader);
  window.app.use(Quasar);
  window.app.use(window.i18n);
  window.app.use(window.router);
  window.app.mount('#vue');
  