// Reuse the block explorer's existing streams; cached state is a fallback.
export class OnchainLiveUpdates {
  constructor(options, browser = window) {
    this.options = options
    this.browser = browser
    this.sockets = new Map()
    this.pollTimer = null
    this.eventTimer = null
    this.clockTimer = null
    this.lastEventScan = -Infinity
    this.stopped = false
    this.refreshing = false
    this.visibility = () => {
      if (this.browser.document.hidden) {
        this.pause()
      } else {
        this.update()
        this.refresh()
      }
    }
  }

  start() {
    this.browser.document.addEventListener('visibilitychange', this.visibility)
    this.clockTimer = this.browser.setInterval(() => {
      if (!this.browser.document.hidden) this.options.clock()
    }, 15000)
    this.update()
  }

  update() {
    if (this.stopped || this.browser.document.hidden) return
    this.reconcileSockets()
    this.schedulePoll()
  }

  schedulePoll() {
    this.browser.clearTimeout(this.pollTimer)
    if (this.stopped || this.browser.document.hidden) return
    this.pollTimer = this.browser.setTimeout(
      () => this.refresh(),
      this.options.scanning() ? 10000 : 60000
    )
  }

  async refresh() {
    if (this.stopped || this.browser.document.hidden || this.refreshing) return
    this.refreshing = true
    try {
      await this.options.refresh()
    } finally {
      this.refreshing = false
      this.update()
    }
  }

  onActivity() {
    if (
      this.stopped ||
      this.browser.document.hidden ||
      this.eventTimer !== null
    )
      return
    const elapsed = this.browser.Date.now() - this.lastEventScan
    this.eventTimer = this.browser.setTimeout(
      async () => {
        this.eventTimer = null
        if (this.stopped || this.browser.document.hidden) return
        this.lastEventScan = this.browser.Date.now()
        try {
          await this.options.scan()
        } finally {
          this.update()
        }
      },
      Math.max(1000, 10000 - elapsed)
    )
  }

  reconcileSockets() {
    const paths = new Set()
    if (this.options.localExplorer()) {
      paths.add('/ws/blocks')
      // Existing address streams use one socket each. Bound browser connections;
      // the fallback still covers every address/account, including older ones.
      for (const address of [...new Set(this.options.addresses())].slice(
        0,
        8
      )) {
        paths.add(`/ws/address/${encodeURIComponent(address)}`)
      }
    }
    for (const [path, entry] of this.sockets) {
      if (!paths.has(path)) {
        this.closeSocket(entry)
        this.sockets.delete(path)
      }
    }
    for (const path of paths) {
      if (!this.sockets.has(path)) {
        const entry = {path, socket: null, timer: null, retry: 5000, last: null}
        this.sockets.set(path, entry)
        this.connect(entry)
      }
    }
  }

  connect(entry) {
    if (this.stopped || this.browser.document.hidden) return
    const {protocol, host} = this.browser.location
    const url = `${protocol === 'https:' ? 'wss:' : 'ws:'}//${host}/blockexplorer/api/v1${entry.path}`
    try {
      const socket = new this.browser.WebSocket(url)
      entry.socket = socket
      socket.onopen = () => {
        entry.retry = 5000
      }
      socket.onmessage = event => {
        let value
        try {
          value = JSON.stringify(JSON.parse(event.data))
        } catch (_) {
          return
        }
        if (value === entry.last) return
        const initialBlock = entry.last === null && entry.path === '/ws/blocks'
        entry.last = value
        if (!initialBlock) this.onActivity()
      }
      socket.onerror = () => socket.close()
      socket.onclose = event => {
        entry.socket = null
        // A disabled explorer rejects with 1008. Use the fallback until config
        // changes instead of repeatedly reconnecting to an unavailable service.
        if (event.code !== 1008) this.reconnect(entry)
      }
    } catch (_) {
      this.reconnect(entry)
    }
  }

  reconnect(entry) {
    if (
      this.stopped ||
      this.browser.document.hidden ||
      this.sockets.get(entry.path) !== entry
    )
      return
    entry.timer = this.browser.setTimeout(
      () => this.connect(entry),
      entry.retry
    )
    entry.retry = Math.min(entry.retry * 2, 60000)
  }

  closeSocket(entry) {
    this.browser.clearTimeout(entry.timer)
    if (entry.socket) {
      entry.socket.onclose = null
      entry.socket.onmessage = null
      entry.socket.onerror = null
      entry.socket.close()
    }
  }

  pause() {
    this.browser.clearTimeout(this.pollTimer)
    this.browser.clearTimeout(this.eventTimer)
    this.eventTimer = null
    for (const entry of this.sockets.values()) this.closeSocket(entry)
    this.sockets.clear()
  }

  stop() {
    this.stopped = true
    this.pause()
    this.browser.clearInterval(this.clockTimer)
    this.browser.document.removeEventListener(
      'visibilitychange',
      this.visibility
    )
  }
}
