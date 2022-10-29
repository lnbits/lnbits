const vm = new Vue({
  el: '#vue',
  mixins: [windowMixin],
  data: function () {
    return {
      vapidPublicKey: vapidPublicKey,
      canServiceWorkerApi: true,
      canNotificationApi: true,
      canPushApi: true,
      isSubscribed: true,
      hasPermission: true,
      isPermissionDenied: false,
      disableSubscribe: function () {
        return (
          !this.canServiceWorkerApi ||
          !this.canNotificationApi ||
          !this.canPushApi ||
          this.isPermissionDenied ||
          (this.isSubscribed && this.hasPermission)
        )
      },
      disableUnsubscribe: function () {
        return (
          !this.canServiceWorkerApi ||
          !this.canNotificationApi ||
          !this.canPushApi ||
          !this.isSubscribed
        )
      }
    }
  },
  methods: {
    urlB64ToUint8Array(base64String) {
      const padding = '='.repeat((4 - (base64String.length % 4)) % 4)
      const base64 = (base64String + padding)
        .replace(/\-/g, '+')
        .replace(/_/g, '/')
      const rawData = atob(base64)
      const outputArray = new Uint8Array(rawData.length)

      for (let i = 0; i < rawData.length; ++i) {
        outputArray[i] = rawData.charCodeAt(i)
      }

      return outputArray
    },
    subscribe() {
      if (!vm.canServiceWorkerApi || !vm.canNotificationApi || !vm.canPushApi) {
        return
      }

      vm.isPermissionDenied = Notification.permission === 'denied'

      if (Notification.permission !== 'granted') {
        Notification.requestPermission().then(permission => {
          updatePermissionStatus()
        })
      }

      navigator.serviceWorker
        .register('/pushnotifications/service_worker.js', {
          scope: '/pushnotifications/'
        })
        .then(registration => {
          let self = this

          navigator.serviceWorker.ready.then(registration => {
            registration.pushManager
              .getSubscription()
              .then(function (subscription) {
                if (subscription === null) {
                  const applicationServerKey = vm.urlB64ToUint8Array(
                    vm.vapidPublicKey
                  )
                  const options = {applicationServerKey, userVisibleOnly: true}

                  registration.pushManager
                    .subscribe(options)
                    .then(function (subscription) {
                      self.saveSubscription(subscription)
                      updateSubscriptionStatus()
                    })
                }
              })
          })
        })
    },
    saveSubscription(subscription) {
      LNbits.api
        .request(
          'POST',
          'api/v1/subscription?all_wallets=true',
          this.g.user.wallets[0].adminkey,
          {
            subscription: JSON.stringify(subscription)
          }
        )
        .catch(function (error) {
          clearInterval(self.checker)
          LNbits.utils.notifyApiError(error)
        })
    },
    deleteSubscription(endpoint, wallet) {
      LNbits.api
        .request(
          'DELETE',
          'api/v1/subscription?endpoint=' + btoa(endpoint) + '&all_wallets=true',
          this.g.user.wallets[0].adminkey
        )
        .catch(function (error) {
          clearInterval(self.checker)
          LNbits.utils.notifyApiError(error)
        })
    },
    unsubscribe() {
      try {
        navigator.serviceWorker.getRegistrations().then(registrations => {
          for (let registration of registrations) {
            registration.pushManager.getSubscription().then(subscription => {
              if (subscription) {
                subscription.unsubscribe().then(() => {
                  this.deleteSubscription(
                    encodeURIComponent(subscription.endpoint)
                  )
                  vm.isSubscribed = false
                })
              }
            })
          }
        })
      } catch (e) {
        console.error(e)
      }
    }
  }
})

const updateRequirementsStatus = () => {
  vm.canServiceWorkerApi = 'serviceWorker' in navigator
  vm.canPushApi = 'PushManager' in window
  vm.canNotificationApi = 'Notification' in window
}

const updatePermissionStatus = async () => {
  vm.isPermissionDenied =
    vm.canServiceWorkerApi && Notification.permission === 'denied'

  vm.hasPermission =
    !vm.canNotificationApi || Notification.permission === 'granted'
}

const updateSubscriptionStatus = async () => {
  try {
    if (vm.canServiceWorkerApi && vm.canPushApi) {
      await navigator.serviceWorker
        .getRegistration('/pushnotifications/service_worker.js')
        .then(function (registration) {
          vm.isSubscribed = false

          registration.pushManager.getSubscription().then(subscription => {
            vm.isSubscribed = !!subscription
          })
        })
    } else {
      vm.isSubscribed = false
    }
  } catch (e) {
    console.error(e)
  }
}

updateRequirementsStatus()
updatePermissionStatus()
updateSubscriptionStatus()
