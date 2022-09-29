// the cache version gets updated every time there is a new deployment
const CACHE_VERSION = 1
const CURRENT_CACHE = `lnbits-${CACHE_VERSION}-`

const getApiKey = request => {
  let api_key = request.headers.get('X-Api-Key')
  if (!api_key || api_key == 'undefined') {
    api_key = 'no_api_key'
  }
  return api_key
}

// on activation we clean up the previously registered service workers
self.addEventListener('activate', evt =>
  evt.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.map(cacheName => {
          const currentCacheVersion = cacheName.split('-').slice(-2, 2)
          if (currentCacheVersion !== CACHE_VERSION) {
            return caches.delete(cacheName)
          }
        })
      )
    })
  )
)

// The fetch handler serves responses for same-origin resources from a cache.
// If no response is found, it populates the runtime cache with the response
// from the network before returning it to the page.
self.addEventListener('fetch', event => {
  if (
    !event.request.url.startsWith(
      self.location.origin + '/api/v1/payments/sse'
    ) &&
    event.request.url.startsWith(self.location.origin) &&
    event.request.method == 'GET'
  ) {
    // Open the cache
    event.respondWith(
      caches.open(CURRENT_CACHE + getApiKey(event.request)).then(cache => {
        // Go to the network first
        return fetch(event.request)
          .then(fetchedResponse => {
            cache.put(event.request, fetchedResponse.clone())

            return fetchedResponse
          })
          .catch(() => {
            // If the network is unavailable, get
            return cache.match(event.request.url)
          })
      })
    )
  }
})
