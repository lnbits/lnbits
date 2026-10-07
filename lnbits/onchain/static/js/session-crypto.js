import {secp256k1} from '@noble/curves/secp256k1.js'
import {sha256} from '@noble/hashes/sha2.js'
import {hkdf} from '@noble/hashes/hkdf.js'
import {gcm} from '@noble/ciphers/aes.js'
const encoder = new TextEncoder()
const decoder = new TextDecoder('utf-8', {fatal: true})
export const sessionHex = b =>
  Array.from(b, n => n.toString(16).padStart(2, '0')).join('')
function unhex(s, length) {
  if (
    typeof s !== 'string' ||
    s.length !== length * 2 ||
    !/^[0-9a-f]+$/.test(s)
  )
    throw new Error('Invalid session encoding')
  return Uint8Array.from(s.match(/../g), n => parseInt(n, 16))
}
const alphabet =
  'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/'
function base64(b) {
  let out = ''
  for (let i = 0; i < b.length; i += 3) {
    const n = b[i] * 65536 + (b[i + 1] ?? 0) * 256 + (b[i + 2] ?? 0)
    out +=
      alphabet[n >>> 18] +
      alphabet[(n >>> 12) & 63] +
      (i + 1 < b.length ? alphabet[(n >>> 6) & 63] : '=') +
      (i + 2 < b.length ? alphabet[n & 63] : '=')
  }
  return out
}
function unbase64(s) {
  if (
    typeof s !== 'string' ||
    s.length > 64024 ||
    s.length % 4 ||
    !/^[A-Za-z0-9+/]*={0,2}$/.test(s)
  )
    throw new Error('Invalid session ciphertext')
  const bytes = []
  for (let i = 0; i < s.length; i += 4) {
    const n =
      alphabet.indexOf(s[i]) * 262144 +
      alphabet.indexOf(s[i + 1]) * 4096 +
      Math.max(0, alphabet.indexOf(s[i + 2])) * 64 +
      Math.max(0, alphabet.indexOf(s[i + 3]))
    bytes.push((n >>> 16) & 255)
    if (s[i + 2] !== '=') bytes.push((n >>> 8) & 255)
    if (s[i + 3] !== '=') bytes.push(n & 255)
  }
  const b = Uint8Array.from(bytes)
  if (base64(b) !== s || b.length < 16)
    throw new Error('Invalid session ciphertext')
  return b
}
export function ephemeralKey(random) {
  for (let i = 0; i < 128; ++i) {
    const secret = random(32)
    if (secp256k1.utils.isValidSecretKey(secret))
      return {secret, publicKey: sessionHex(secp256k1.getPublicKey(secret))}
    secret.fill(0)
  }
  throw new Error('Cannot generate session key')
}
function initContext(h, client, signer) {
  return [
    'remote-signer-init-v1',
    2,
    client,
    signer,
    h.params.mobile_ephemeral_public_key,
    h.params.session_id,
    h.id,
    h.network,
    h.params.session,
    h.psbt_hash,
    h.expires
  ]
}
export function initHash(h, client, signer) {
  return sessionHex(
    sha256(encoder.encode(JSON.stringify(initContext(h, client, signer))))
  )
}
export class EncryptionSession {
  id
  transcript
  sendKey = new Uint8Array(0)
  receiveKey = new Uint8Array(0)
  sent = 0
  received = new Set()
  closed = false
  hello
  constructor(hello, client, signer, secret, signerPublic, role = 'client') {
    this.hello = hello
    this.id = hello.params.session_id
    let shared
    let sharedPoint
    try {
      unhex(client, 32)
      unhex(signer, 32)
      unhex(hello.id, 16)
      unhex(hello.params.session, 16)
      unhex(hello.psbt_hash, 32)
      const salt = unhex(this.id, 32)
      const mobilePublic = unhex(hello.params.mobile_ephemeral_public_key, 33)
      const remotePublic = unhex(signerPublic, 33)
      secp256k1.Point.fromBytes(mobilePublic).assertValidity()
      secp256k1.Point.fromBytes(remotePublic).assertValidity()
      if (
        !Number.isSafeInteger(hello.expires) ||
        !['Mainnet', 'Testnet4'].includes(hello.network) ||
        hello.params.request_type !== 'sign_psbt'
      )
        throw new Error('Invalid session context')
      if (
        sessionHex(secp256k1.getPublicKey(secret)) !==
        (role === 'client'
          ? hello.params.mobile_ephemeral_public_key
          : signerPublic)
      )
        throw new Error('Session key mismatch')
      this.transcript = sessionHex(
        sha256(
          encoder.encode(
            JSON.stringify([
              'remote-signer-session-v1',
              2,
              client,
              signer,
              hello.params.mobile_ephemeral_public_key,
              signerPublic,
              this.id,
              hello.id,
              hello.network,
              hello.params.session,
              hello.psbt_hash,
              hello.expires
            ])
          )
        )
      )
      sharedPoint = secp256k1.getSharedSecret(
        secret,
        role === 'client' ? remotePublic : mobilePublic
      )
      shared = sharedPoint.subarray(1)
      const derive = direction =>
        hkdf(
          sha256,
          shared,
          salt,
          encoder.encode(
            JSON.stringify([
              'remote-signer-session-v1',
              this.transcript,
              direction
            ])
          ),
          32
        )
      this.sendKey = derive(role === 'client' ? 'c2s' : 's2c')
      this.receiveKey = derive(role === 'client' ? 's2c' : 'c2s')
      this.role = role
    } catch (error) {
      this.sendKey.fill(0)
      this.receiveKey.fill(0)
      throw error
    } finally {
      secret.fill(0)
      sharedPoint?.fill(0)
      shared?.fill(0)
    }
  }
  role
  nonce(counter) {
    const n = new Uint8Array(12)
    new DataView(n.buffer).setUint32(8, counter, false)
    return n
  }
  aad(packet, direction) {
    return encoder.encode(
      JSON.stringify([
        this.transcript,
        direction,
        packet.counter,
        packet.method,
        packet.id
      ])
    )
  }
  encrypt(message) {
    if (this.closed || this.sent >= 64)
      throw new Error('Session closed or message limit reached')
    const packet = {
      protocol: 'bitcoin-signer',
      version: 2,
      network: this.hello.network,
      id: message.id,
      method: message.method,
      expires: this.hello.expires,
      psbt_hash: this.hello.psbt_hash,
      session_id: this.id,
      counter: this.sent++,
      ciphertext: ''
    }
    const clear = encoder.encode(JSON.stringify({...message, version: 2}))
    try {
      if (clear.length > 48000)
        throw new Error('Signing message exceeds session limit')
      packet.ciphertext = base64(
        gcm(
          this.sendKey,
          this.nonce(packet.counter),
          this.aad(packet, this.role === 'client' ? 'c2s' : 's2c')
        ).encrypt(clear)
      )
    } finally {
      clear.fill(0)
    }
    return packet
  }
  decrypt(packet) {
    if (
      this.closed ||
      packet.protocol !== 'bitcoin-signer' ||
      packet.version !== 2 ||
      packet.session_id !== this.id ||
      packet.network !== this.hello.network ||
      packet.psbt_hash !== this.hello.psbt_hash ||
      packet.expires !== this.hello.expires ||
      !Number.isInteger(packet.counter) ||
      packet.counter < 0 ||
      packet.counter >= 64 ||
      this.received.has(packet.counter)
    )
      throw new Error('Unknown or replayed session message')
    const cipher = unbase64(packet.ciphertext)
    const clear = gcm(
      this.receiveKey,
      this.nonce(packet.counter),
      this.aad(packet, this.role === 'client' ? 's2c' : 'c2s')
    ).decrypt(cipher)
    try {
      const value = JSON.parse(decoder.decode(clear))
      if (
        value.protocol !== packet.protocol ||
        value.version !== 2 ||
        value.id !== packet.id ||
        value.method !== packet.method ||
        value.network !== packet.network ||
        value.psbt_hash !== packet.psbt_hash
      )
        throw new Error('Session binding mismatch')
      this.received.add(packet.counter)
      return value
    } finally {
      clear.fill(0)
    }
  }
  close() {
    this.closed = true
    this.sendKey.fill(0)
    this.receiveKey.fill(0)
    this.received.clear()
  }
}
