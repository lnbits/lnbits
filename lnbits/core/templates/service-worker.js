/**
 * LNbits Service Worker - Hardened Production PWA
 *
 * Features:
 * - Forced update on deploy via skipWaiting + clients.claim()
 * - Network timeout (10s) with cache fallback
 * - Hashed API key cache keying for security
 * - TTL-based lazy cache expiry (7 days)
 * - In-memory metadata cache for performance
 * - Structured logging with diagnostics
 * - Open redirect prevention
 */

// ============================================================================
// Configuration
// ============================================================================

const CURRENT_CACHE = 'lnbits-{{ cache_version }}-'
const NETWORK_TIMEOUT_MS = 10000 // 10s timeout for network requests
const CACHE_TTL_MS = 7 * 24 * 60 * 60 * 1000 // 7-day TTL for cache entries
const CACHE_METADATA_KEY = '__lnbits_meta__'
const CACHE_SYNC_INTERVAL_MS = 60000 // Persist metadata every 60s

// In-memory metadata cache (TTL map: url -> timestamp)
let metadataCache = new Map()
let metadataSyncTimer = null

// ============================================================================
// Logging Utilities
// ============================================================================

/**
 * Structured logging with level and context.
 * @param {string} level - 'info', 'warn', or 'error'
 * @param {string} message - Log message
 * @param {Object} context - Optional context fields (url, error, etc.)
 */
const log = (level, message, context = {}) => {
  const timestamp = new Date().toISOString()
  const prefix = `[SW:${level.toUpperCase()}]`
  const fields = Object.entries(context)
    .map(([k, v]) => `${k}=${v}`)
    .join(' ')
  console.log(`${prefix} ${timestamp} ${message} ${fields}`.trim())
}

// ============================================================================
// Hashing and API Key Handling
// ============================================================================

/**
 * Compute SHA-256 hash of input string; falls back to simple prefix hash.
 * @param {string} str - Input string
 * @returns {Promise<string>} - Hex digest or fallback hash
 */
const hashString = async str => {
  try {
    if (!crypto?.subtle?.digest) {
      throw new Error('crypto.subtle.digest not available')
    }
    const encoder = new TextEncoder()
    const data = encoder.encode(str)
    const hashBuffer = await crypto.subtle.digest('SHA-256', data)
    const hashArray = Array.from(new Uint8Array(hashBuffer))
    return hashArray.map(b => b.toString(16).padStart(2, '0')).join('')
  } catch (err) {
    // Fallback: simple prefix hash (not cryptographic, but safe for cache keying)
    log('warn', 'crypto.subtle.digest unavailable; using fallback hash', {
      error: err.message
    })
    return btoa(str.substring(0, 32))
      .replace(/[^a-z0-9]/gi, '')
      .substring(0, 32)
  }
}

/**
 * Extract and normalize API key from request headers.
 * @param {Request} request - Fetch API request object
 * @returns {Promise<string>} - SHA-256 hash of API key or 'no_api_key'
 */
const getApiKeyHash = async request => {
  let apiKey = request.headers.get('X-Api-Key') || 'no_api_key'
  if (apiKey === 'undefined' || apiKey === '') {
    apiKey = 'no_api_key'
  }
  return hashString(apiKey)
}

// ============================================================================
// Timeout Utility
// ============================================================================

/**
 * Reject a promise after specified delay.
 * @param {number} ms - Milliseconds
 * @returns {Promise<never>}
 */
const timeout = ms => {
  return new Promise((_, reject) =>
    setTimeout(() => reject(new Error(`Network timeout after ${ms}ms`)), ms)
  )
}

// ============================================================================
// Cache Metadata Management
// ============================================================================

/**
 * Load TTL metadata for a cache store.
 * Tries in-memory cache first, then persistent cache.
 * @param {string} cacheName - Cache store name
 * @returns {Promise<Object>} - Map of URL -> timestamp
 */
const loadCacheMetadata = async cacheName => {
  // Check in-memory cache first
  if (metadataCache.has(cacheName)) {
    return metadataCache.get(cacheName)
  }

  // Load from persistent cache
  try {
    const cache = await caches.open(cacheName)
    const metaResp = await cache.match(CACHE_METADATA_KEY)
    if (metaResp) {
      const text = await metaResp.text()
      const metadata = JSON.parse(text)
      metadataCache.set(cacheName, metadata)
      return metadata
    }
  } catch (err) {
    log('warn', 'Failed to load cache metadata', {
      cache: cacheName,
      error: err.message
    })
  }

  return {}
}

/**
 * Save TTL metadata back to persistent cache.
 * Updates in-memory cache and schedules sync.
 * @param {string} cacheName - Cache store name
 * @param {Object} metadata - Map of URL -> timestamp
 * @returns {Promise<void>}
 */
const saveCacheMetadata = async (cacheName, metadata) => {
  // Update in-memory cache
  metadataCache.set(cacheName, metadata)

  // Schedule persistent sync (debounced every 60s)
  if (!metadataSyncTimer) {
    metadataSyncTimer = setTimeout(async () => {
      for (const [name, meta] of metadataCache.entries()) {
        try {
          const cache = await caches.open(name)
          const resp = new Response(JSON.stringify(meta), {
            headers: {'Content-Type': 'application/json'}
          })
          await cache.put(CACHE_METADATA_KEY, resp)
        } catch (err) {
          log('warn', 'Failed to persist cache metadata', {
            cache: name,
            error: err.message
          })
        }
      }
      metadataSyncTimer = null
    }, CACHE_SYNC_INTERVAL_MS)
  }
}

/**
 * Check if a cached response has expired based on TTL.
 * @param {string} cacheName - Cache store name
 * @param {string} url - Request URL
 * @returns {Promise<boolean>} - True if entry is expired
 */
const isCacheEntryExpired = async (cacheName, url) => {
  const metadata = await loadCacheMetadata(cacheName)
  const timestamp = metadata[url]
  if (!timestamp) return true // No metadata = expired
  return Date.now() - timestamp > CACHE_TTL_MS
}

/**
 * Prune expired entries from a cache store.
 * @param {string} cacheName - Cache store name
 * @returns {Promise<void>}
 */
const pruneExpiredEntries = async cacheName => {
  try {
    const cache = await caches.open(cacheName)
    const metadata = await loadCacheMetadata(cacheName)
    const now = Date.now()
    const entriesToDelete = []

    for (const [url, timestamp] of Object.entries(metadata)) {
      if (url === CACHE_METADATA_KEY) continue
      if (now - timestamp > CACHE_TTL_MS) {
        entriesToDelete.push(url)
      }
    }

    for (const url of entriesToDelete) {
      await cache.delete(url)
      delete metadata[url]
    }

    if (entriesToDelete.length > 0) {
      await saveCacheMetadata(cacheName, metadata)
      log('info', `Pruned expired cache entries`, {
        cache: cacheName,
        count: entriesToDelete.length
      })
    }
  } catch (err) {
    log('error', `Error pruning cache`, {cache: cacheName, error: err.message})
  }
}

/**
 * Delete all caches from previous service worker versions.
 * @returns {Promise<void>}
 */
const deleteOldCaches = async () => {
  try {
    const cacheNames = await caches.keys()
    const deletions = cacheNames
      .filter(name => !name.startsWith(CURRENT_CACHE))
      .map(async cacheName => {
        log('info', `Deleting old cache`, {cache: cacheName})
        await caches.delete(cacheName)
      })
    await Promise.all(deletions)
  } catch (err) {
    log('error', `Error deleting old caches`, {error: err.message})
  }
}

/**
 * Prune expired entries from all current cache stores.
 * @returns {Promise<void>}
 */
const pruneAllCurrentCaches = async () => {
  try {
    const cacheNames = await caches.keys()
    const currentCaches = cacheNames.filter(c => c.startsWith(CURRENT_CACHE))
    await Promise.all(currentCaches.map(pruneExpiredEntries))
  } catch (err) {
    log('error', `Error pruning all caches`, {error: err.message})
  }
}

// ============================================================================
// URL Validation
// ============================================================================

/**
 * Validate and normalize notification URL to prevent open redirects.
 * @param {string} url - URL to validate
 * @returns {string} - Safe URL or fallback
 */
const validateNotificationUrl = url => {
  if (!url) return '/'
  try {
    const parsed = new URL(url, self.location.origin)
    // Only allow same-origin URLs
    if (parsed.origin === self.location.origin) {
      return parsed.pathname + parsed.search + parsed.hash
    }
  } catch (err) {
    log('warn', `Invalid notification URL`, {url, error: err.message})
  }
  return '/'
}

// ============================================================================
// Service Worker Lifecycle Events
// ============================================================================

/**
 * Install event: declare intent to take over clients immediately.
 */
self.addEventListener('install', event => {
  log('info', 'Service worker installing')
  self.skipWaiting()
})

/**
 * Activate event: take control of all clients and clean up old caches.
 */
self.addEventListener('activate', event => {
  log('info', 'Service worker activating')
  event.waitUntil(
    (async () => {
      // Claim all clients immediately
      await self.clients.claim()
      log('info', 'Claimed all clients')

      // Delete old version caches
      await deleteOldCaches()

      // Prune expired entries from current caches
      await pruneAllCurrentCaches()

      log('info', 'Activation complete; controlling all clients')
    })()
  )
})

// ============================================================================
// Fetch Event Handler
// ============================================================================

/**
 * Fetch event: network-first strategy with timeout and cache fallback.
 * Applies only to same-origin GET requests.
 */
self.addEventListener('fetch', event => {
  const {request} = event
  const isGetRequest = request.method === 'GET'
  const isSameOrigin = request.url.startsWith(self.location.origin)

  if (!isSameOrigin || !isGetRequest) {
    // Let browser handle it
    return
  }

  event.respondWith(
    (async () => {
      const apiKeyHash = await getApiKeyHash(request)
      const cacheName = CURRENT_CACHE + apiKeyHash

      try {
        // Open cache for this API key
        const cache = await caches.open(cacheName)

        try {
          // Network-first: attempt fetch with timeout
          const fetchPromise = fetch(request)
          const response = await Promise.race([
            fetchPromise,
            timeout(NETWORK_TIMEOUT_MS)
          ])

          // Cache only successful responses (2xx status)
          if (response.ok) {
            try {
              const responseToCache = response.clone()
              await cache.put(request, responseToCache)
              const metadata = await loadCacheMetadata(cacheName)
              metadata[request.url] = Date.now()
              await saveCacheMetadata(cacheName, metadata)
            } catch (err) {
              log('warn', 'Failed to cache response', {
                url: request.url,
                error: err.message
              })
            }
          } else {
            // Do not cache error responses (4xx, 5xx)
            log('debug', 'Not caching error response', {
              url: request.url,
              status: response.status
            })
          }

          return response
        } catch (fetchErr) {
          // Network failed or timed out; try cache
          const expired = await isCacheEntryExpired(cacheName, request.url)
          const cachedResponse = await cache.match(request.url)

          if (cachedResponse && !expired) {
            log('info', 'Serving from cache', {
              url: request.url,
              reason: 'network_error'
            })
            return cachedResponse
          }

          if (cachedResponse && expired) {
            log('warn', 'Serving stale cache (expired)', {url: request.url})
            // Return stale but remove from cache soon
            return cachedResponse
          }

          log('error', 'Network error and no cache', {
            url: request.url,
            error: fetchErr.message
          })
          return new Response('Offline and no cached response available', {
            status: 503,
            statusText: 'Service Unavailable',
            headers: {'Content-Type': 'text/plain'}
          })
        }
      } catch (err) {
        log('error', 'Unexpected error in fetch handler', {
          url: request.url,
          error: err.message
        })
        return new Response('Internal service worker error', {
          status: 500,
          statusText: 'Internal Server Error',
          headers: {'Content-Type': 'text/plain'}
        })
      }
    })()
  )
})

// ============================================================================
// Push Notification Events
// ============================================================================

/**
 * Push event: handle incoming push notifications.
 */
self.addEventListener('push', event => {
  if (!(self.Notification && self.Notification.permission === 'granted')) {
    log('warn', 'Push received but notifications not permitted')
    return
  }

  let data
  try {
    data = event.data.json()
  } catch (err) {
    log('error', 'Failed to parse push event data', {error: err.message})
    return
  }

  const {title = 'LNbits', body = '', url = '/'} = data

  event.waitUntil(
    self.registration.showNotification(title, {
      body: body,
      icon: '/favicon.ico',
      data: {url},
      badge: '/favicon.ico',
      tag: 'lnbits-notification'
    })
  )
  log('info', 'Notification shown', {title})
})

/**
 * Notification click: open or focus the app window.
 */
self.addEventListener('notificationclick', event => {
  event.notification.close()
  event.waitUntil(
    (async () => {
      const url = validateNotificationUrl(event.notification.data.url)

      // Check if app is already open in a tab
      const clients = await self.clients.matchAll({type: 'window'})
      for (const client of clients) {
        if (client.url.startsWith(url) && 'focus' in client) {
          log('info', 'Focused existing client window', {url})
          return client.focus()
        }
      }

      // App not open; open a new window/tab
      if (self.clients.openWindow) {
        log('info', 'Opening new client window', {url})
        return self.clients.openWindow(url)
      }
    })()
  )
})
