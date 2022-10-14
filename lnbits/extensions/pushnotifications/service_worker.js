self.addEventListener('push', function (event) {
  if (!(self.Notification && self.Notification.permission === 'granted')) {
    return
  }

  let data = event.data.json()
  const title = data.title
  const body = data.body
  const url = data.url

  event.waitUntil(
    self.registration.showNotification(title, {
      body: body,
      icon: '/favicon.ico',
      data: {
        url: url
      }
    })
  )
})

self.addEventListener('notificationclick', function (event) {
  event.notification.close()
  event.waitUntil(clients.openWindow(event.notification.data.url))
})
