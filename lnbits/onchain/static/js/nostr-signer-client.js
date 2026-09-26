// Experimental Bitcoin signer v1. NIP-44 encryption; this is not NIP-46.
export const BITCOIN_SIGNER_KIND = 24134
export const MAX_PSBT_BYTES = 32768
const hex = bytes =>
  Array.from(bytes, b => b.toString(16).padStart(2, '0')).join('')
export function parsePairing(text) {
  const value = JSON.parse(text)
  if (
    value.protocol !== 'bitcoin-signer' ||
    value.version !== 1 ||
    !/^[0-9a-f]{64}$/.test(value.pubkey) ||
    !/^[0-9a-f]{32}$/.test(value.token) ||
    !Array.isArray(value.relays) ||
    !value.relays.length ||
    value.relays.length > 3
  )
    throw new Error('Invalid Bitcoin signer pairing code')
  value.relays = [
    ...new Set(
      value.relays.map(relay => {
        const url = new URL(relay)
        if (
          url.protocol !== 'wss:' ||
          url.username ||
          url.password ||
          url.hash ||
          (url.port && url.port !== '443') ||
          relay.length > 200
        )
          throw new Error('Use secure relay URLs on port 443')
        return url.href
      })
    )
  ]
  return value
}
export class NostrBitcoinSigner {
  constructor({
    tools = globalThis.NostrTools,
    WebSocketClass = globalThis.WebSocket,
    crypto = globalThis.crypto,
    secret,
    pubkey,
    relays,
    onStatus = () => {}
  }) {
    this.onStatus = onStatus
    this.retries = new Set()
    this.tools = tools
    this.WebSocketClass = WebSocketClass
    this.crypto = crypto
    this.secret = secret
    this.pubkey = pubkey
    this.relays = relays
    this.clientKey = tools.getPublicKey(secret)
    this.pending = new Map()
    this.sockets = []
    this.closed = false
  }
  connect() {
    if (this.sockets.length || this.retries.size) return
    this.closed = false
    for (const relay of this.relays) this.openRelay(relay)
  }
  openRelay(relay) {
    if (this.closed) return
    const socket = new this.WebSocketClass(relay)
    this.sockets.push(socket)
    socket.onopen = () => {
      socket.send(
        JSON.stringify([
          'REQ',
          'bitcoin-v1',
          {
            kinds: [BITCOIN_SIGNER_KIND],
            authors: [this.pubkey],
            '#p': [this.clientKey],
            since: Math.floor(Date.now() / 1000) - 180
          }
        ])
      )
      for (const p of this.pending.values())
        if (Date.now() < p.deadline) socket.send(p.wire)
    }
    socket.onmessage = event => {
      void this.receive(event.data)
    }
    socket.onerror = () => socket.close()
    socket.onclose = () => {
      this.sockets = this.sockets.filter(s => s !== socket)
      if (!this.closed) {
        const retry = setTimeout(() => {
          this.retries.delete(retry)
          this.openRelay(relay)
        }, 5000)
        this.retries.add(retry)
      }
    }
  }
  async receive(wire) {
    try {
      if (typeof wire !== 'string' || wire.length > 100000) return
      const envelope = JSON.parse(wire)
      if (envelope[0] !== 'EVENT' || envelope.length !== 3) return
      const event = envelope[2]
      const now = Math.floor(Date.now() / 1000)
      if (
        event.pubkey !== this.pubkey ||
        event.kind !== BITCOIN_SIGNER_KIND ||
        !Number.isInteger(event.created_at) ||
        event.created_at > now + 30 ||
        event.created_at < now - 180 ||
        JSON.stringify(event.tags) !==
          JSON.stringify([['p', this.clientKey]]) ||
        !this.tools.verifyEvent(event)
      )
        return
      const key = this.tools.nip44.v2.utils.getConversationKey(
        this.secret,
        this.pubkey
      )
      const response = JSON.parse(
        this.tools.nip44.v2.decrypt(event.content, key)
      )
      const pending = this.pending.get(response.id)
      if (
        !pending ||
        Date.now() >= pending.deadline ||
        response.protocol !== 'bitcoin-signer' ||
        response.version !== 1 ||
        response.network !== 'Testnet4' ||
        response.method !== pending.method ||
        response.psbt_hash !== pending.hash
      )
        return
      if (response.status !== undefined) {
        const statuses = new Set([
          'Ready to sign',
          'PIN required',
          'Decrypting wallet',
          'Validating transaction',
          'Ready to sign — approve on device',
          'Automatically approved',
          'Signing',
          'Signing complete'
        ])
        if (
          pending.method !== 'sign_psbt' ||
          !statuses.has(response.status) ||
          !Number.isInteger(response.sequence) ||
          response.sequence <= pending.sequence
        )
          return
        pending.sequence = response.sequence
        pending.status = response.status
        this.onStatus(response.status)
        return
      }
      clearTimeout(pending.timer)
      clearInterval(pending.retry)
      this.pending.delete(response.id)
      if (pending.method === 'sign_psbt') this.finishPinRequests(response.id)
      if (response.error) pending.reject(new Error(response.error))
      else pending.resolve(response.result)
    } catch (_) {
      /* Malformed, unauthenticated, or unrelated relay data is ignored. */
    }
  }
  request(method, params = {}, hash = '') {
    if (this.closed) return Promise.reject(new Error('Signer disconnected'))
    if (
      method === 'unlock' &&
      (!this.pending.has(params.request_id) ||
        this.pending.get(params.request_id).method !== 'sign_psbt')
    )
      return Promise.reject(new Error('No active PIN request'))
    if (this.pending.size && method !== 'unlock')
      return Promise.reject(new Error('A signing request is already active'))
    const now = Math.floor(Date.now() / 1000)
    const id = hex(this.crypto.getRandomValues(new Uint8Array(16)))
    const expires =
      method === 'unlock'
        ? Math.floor(this.pending.get(params.request_id).deadline / 1000)
        : now + 150
    const parentId = method === 'unlock' ? params.request_id : null
    const request = {
      protocol: 'bitcoin-signer',
      version: 1,
      id,
      method,
      network: 'Testnet4',
      expires,
      params,
      psbt_hash: hash
    }
    const key = this.tools.nip44.v2.utils.getConversationKey(
      this.secret,
      this.pubkey
    )
    const event = this.tools.finalizeEvent(
      {
        kind: BITCOIN_SIGNER_KIND,
        created_at: now,
        tags: [['p', this.pubkey]],
        content: this.tools.nip44.v2.encrypt(JSON.stringify(request), key)
      },
      this.secret
    )
    if (method === 'unlock') params.pin = ''
    const wire = JSON.stringify(['EVENT', event])
    return new Promise((resolve, reject) => {
      const publish = () => {
        if (Date.now() >= expires * 1000) return
        for (const socket of this.sockets)
          if (socket.readyState === 1) socket.send(wire)
      }
      // Ephemeral relays do not retain requests while the device is offline.
      // Repeat the same signed event; the device replay cache makes this idempotent.
      const retry = setInterval(publish, 5000)
      const timer = setTimeout(
        () => {
          this.pending.delete(id)
          clearInterval(retry)
          if (method === 'sign_psbt') this.finishPinRequests(id)
          reject(
            new Error('Signer timed out. Review and try a new signing request.')
          )
        },
        Math.max(0, expires * 1000 - Date.now())
      )
      this.pending.set(id, {
        resolve,
        reject,
        timer,
        retry,
        method,
        sequence: 0,
        status: null,
        hash,
        wire,
        parentId,
        deadline: expires * 1000
      })
      publish()
    })
  }
  async getAccount() {
    const account = await this.request('get_account')
    if (
      !account ||
      typeof account.descriptor !== 'string' ||
      account.path !== "m/84'/1'/0'" ||
      !/^[0-9a-f]{32}$/.test(account.session)
    )
      throw new Error('Unsupported signer account')
    this.account = account
    return account
  }
  async sign(psbt) {
    if (typeof psbt !== 'string' || psbt.length > 43692)
      throw new Error('PSBT exceeds 32 KiB')
    const bytes = Uint8Array.from(atob(psbt), c => c.charCodeAt(0))
    if (
      bytes.length > MAX_PSBT_BYTES ||
      btoa(String.fromCharCode(...bytes)) !== psbt
    )
      throw new Error('Invalid or oversized PSBT')
    const hash = hex(
      new Uint8Array(await this.crypto.subtle.digest('SHA-256', bytes))
    )
    // Refresh the boot session automatically before each signing request.
    await this.getAccount()
    const result = await this.request(
      'sign_psbt',
      {psbt, session: this.account.session},
      hash
    )
    if (typeof result?.psbt !== 'string' || result.psbt.length > 60000)
      throw new Error('Invalid signed PSBT response')
    return result.psbt
  }
  finishPinRequests(id) {
    for (const [key, pending] of this.pending) {
      if (pending.parentId !== id) continue
      clearTimeout(pending.timer)
      clearInterval(pending.retry)
      this.pending.delete(key)
      pending.resolve({})
    }
  }
  async submitPin(pin) {
    if (!/^[0-9]{6,32}$/.test(pin)) throw new Error('Use a PIN of 6–32 digits')
    const entry = [...this.pending.entries()].find(
      ([, p]) => p.method === 'sign_psbt'
    )
    if (
      !entry ||
      entry[1].status !== 'PIN required' ||
      [...this.pending.values()].some(p => p.method === 'unlock')
    )
      throw new Error('No active PIN request')
    const [id, pending] = entry
    try {
      return await this.request(
        'unlock',
        {
          pin,
          request_id: id,
          session: this.account.session
        },
        pending.hash
      )
    } finally {
      pin = ''
    }
  }
  close() {
    this.closed = true
    for (const retry of this.retries) clearTimeout(retry)
    this.retries.clear()
    for (const socket of this.sockets) {
      clearTimeout(socket.retry)
      socket.close()
    }
    this.sockets = []
    for (const p of this.pending.values()) {
      clearTimeout(p.timer)
      clearInterval(p.retry)
      p.reject(new Error('Signer disconnected'))
    }
    this.pending.clear()
    this.secret.fill(0)
    this.account = null
  }
}
