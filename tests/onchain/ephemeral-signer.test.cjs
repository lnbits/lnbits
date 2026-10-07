const assert = require('node:assert/strict')
const {test} = require('node:test')
const {readFileSync} = require('node:fs')
const {webcrypto} = require('node:crypto')
const flush = () => new Promise(resolve => setImmediate(resolve))
async function waitFor(check) {
  for (let i = 0; i < 1000; ++i) {
    if (check()) return
    await new Promise(r => setTimeout(r, 1))
  }
  throw new Error('Test request was not published')
}
async function harness(network = 'Testnet4', automatic = true) {
  const {NostrBitcoinSigner} =
    await import('../../lnbits/onchain/static/js/nostr-signer-client.js')
  const {EncryptionSession, ephemeralKey, initHash} =
    await import('../../lnbits/onchain/static/js/session-crypto.bundle.js')
  const tools = await import('nostr-tools')
  const device = tools.generateSecretKey(),
    phone = tools.generateSecretKey(),
    pubkey = tools.getPublicKey(device)
  let server, hello
  class Socket {
    constructor() {
      this.readyState = 1
      this.sent = []
    }
    send(wire) {
      this.sent.push(wire)
      const e = JSON.parse(wire)
      if (e[0] !== 'EVENT') return
      const value = JSON.parse(tools.nip44.v2.decrypt(e[1].content, key))
      if (value.method === 'session_init' && automatic && !server) {
        hello = value
        const b = ephemeralKey(n =>
          webcrypto.getRandomValues(new Uint8Array(n))
        )
        server = new EncryptionSession(
          hello,
          client.clientKey,
          pubkey,
          b.secret,
          b.publicKey,
          'signer'
        )
        respond(hello, {
          result: {
            init_hash: initHash(hello, client.clientKey, pubkey),
            signer_ephemeral_public_key: b.publicKey
          }
        })
      }
    }
    close() {
      this.readyState = 3
      this.onclose?.()
    }
  }
  const status = []
  const client = new NostrBitcoinSigner({
    tools,
    WebSocketClass: Socket,
    crypto: webcrypto,
    secret: phone,
    pubkey,
    relays: ['wss://example.invalid'],
    network,
    onStatus: s => status.push(s)
  })
  const key = tools.nip44.v2.utils.getConversationKey(device, client.clientKey)
  client.connect()
  client.sockets[0].onopen()
  const decoded = new Map()
  function outer() {
    return JSON.parse(
      tools.nip44.v2.decrypt(
        JSON.parse(
          client.sockets[0].sent.findLast(s => JSON.parse(s)[0] === 'EVENT')
        )[1].content,
        key
      )
    )
  }
  function request() {
    const p = outer()
    if (!p.ciphertext) return p
    const id = p.id + ':' + p.counter
    if (!decoded.has(id)) decoded.set(id, server.decrypt(p))
    return decoded.get(id)
  }
  function respond(r, extra, encrypt = true) {
    const {protocol, version, network, id, method, psbt_hash} = r
    let response = {protocol, version, network, id, method, psbt_hash, ...extra}
    if (encrypt && version === 2 && method !== 'session_init')
      response = server.encrypt(response)
    const event = tools.finalizeEvent(
      {
        kind: 24133,
        created_at: Math.floor(Date.now() / 1000),
        tags: [['p', client.clientKey]],
        content: tools.nip44.v2.encrypt(JSON.stringify(response), key)
      },
      device
    )
    void client.receive(JSON.stringify(['EVENT', 'remote-signer', event]))
  }
  const account = {
    descriptor: 'public-fixture',
    path: network === 'Mainnet' ? "m/84'/0'/0'" : "m/84'/1'/0'",
    session: 'e'.repeat(32),
    secure_session: 1
  }
  return {
    client,
    status,
    request,
    respond,
    outer,
    account,
    get hello() {
      return hello
    }
  }
}
for (const network of ['Mainnet', 'Testnet4']) {
  test(`${network}: browser signing uses an ephemeral session and rejects unprotected PIN progress`, async () => {
    const t = await harness(network)
    try {
      const signing = t.client.sign(
        Buffer.from('public synthetic psbt').toString('base64')
      )
      await waitFor(() => t.client.pending.size > 0)
      t.respond(t.request(), {result: t.account})
      await waitFor(() =>
        [...t.client.pending.values()].some(p => p.method === 'sign_psbt')
      )
      const request = t.request()
      assert.equal(request.method, 'sign_psbt')
      assert.equal(t.outer().params, undefined)
      assert.ok(t.outer().ciphertext)
      t.respond(request, {status: 'PIN required', sequence: 2}, false)
      assert.equal(t.status.at(-1), 'Establishing secure signing session')
      t.respond(request, {status: 'PIN required', sequence: 7})
      assert.notEqual(t.status.at(-1), 'PIN required')
      t.respond(request, {status: 'PIN required', sequence: 2})
      assert.equal(t.status.at(-1), 'PIN required')
      const pin = t.client.submitPin('123456'),
        unlock = t.request()
      assert.equal(unlock.params.request_id, request.id)
      assert.equal(unlock.params.pin, '123456')
      assert.equal(t.outer().params, undefined)
      assert.ok(!JSON.stringify(t.outer()).includes('123456'))
      const active = t.client.encryption,
        send = active.sendKey,
        receive = active.receiveKey
      t.respond(unlock, {result: {}})
      await pin
      t.respond(request, {result: {psbt: 'signed-public-fixture'}})
      assert.equal(await signing, 'signed-public-fixture')
      assert.ok(send.every(n => n === 0))
      assert.ok(receive.every(n => n === 0))
    } finally {
      t.client.close()
    }
  })
}
test('browser rejects legacy firmware before establishing a signing session', async () => {
  const t = await harness()
  try {
    const signing = t.client.sign(
        Buffer.from('public psbt').toString('base64')
      ),
      failure = assert.rejects(signing, /Update signer firmware/)
    await waitFor(() => t.client.pending.size > 0)
    t.respond(t.request(), {result: {...t.account, secure_session: undefined}})
    await failure
    assert.equal(t.outer().method, 'get_account')
  } finally {
    t.client.close()
  }
})
test('shared crypto vectors and exact replay rejection', async () => {
  const {EncryptionSession} =
    await import('../../lnbits/onchain/static/js/session-crypto.bundle.js')
  const vectors = JSON.parse(readFileSync('tests/session-vectors.json', 'utf8'))
  for (const v of vectors) {
    const client = new EncryptionSession(
      v.hello,
      v.client,
      v.signer,
      new Uint8Array(Buffer.from(v.mobile_private, 'hex')),
      v.signer_public
    )
    const signer = new EncryptionSession(
      v.hello,
      v.client,
      v.signer,
      new Uint8Array(Buffer.from(v.signer_private, 'hex')),
      v.signer_public,
      'signer'
    )
    assert.equal(client.transcript, v.transcript)
    assert.deepEqual(client.encrypt(v.message), v.packet)
    assert.deepEqual(signer.decrypt(v.packet), v.message)
    assert.throws(() => signer.decrypt(v.packet))
    client.close()
    signer.close()
  }
})

test('hidden browser pages clear PIN UI and disconnect session; unmount removes listener', () => {
  const vm = require('node:vm')
  const {readFileSync} = require('./source.cjs')
  let component,
    handler,
    closed = 0,
    removed = false
  const document = {
    hidden: true,
    addEventListener: (_, fn) => {
      handler = fn
    },
    removeEventListener: (_, fn) => {
      removed = fn === handler
    }
  }
  vm.runInNewContext(
    readFileSync('lnbits/onchain/static/components/nostr-signer.js', 'utf8'),
    {
      window: {
        app: {
          component: (_, c) => {
            component = c
          }
        }
      },
      document
    }
  )
  const instance = {
    ...component.data(),
    client: {
      close() {
        ++closed
      }
    },
    pin: '123456',
    pinRequired: true
  }
  instance.disconnect = component.methods.disconnect.bind(instance)
  component.mounted.call(instance)
  handler()
  assert.equal(closed, 1)
  assert.equal(instance.pin, '')
  assert.equal(instance.pinRequired, false)
  assert.equal(instance.client, null)
  component.beforeUnmount.call(instance)
  assert.equal(removed, true)
})
