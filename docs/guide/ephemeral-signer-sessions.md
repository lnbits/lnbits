# Ephemeral signing sessions

Signing and remote PIN unlock require `bitcoin-signer` version 2. Pairing and
`get_account` retain version 1 and existing pairing records. Public-account
responses advertise `secure_session: 1`; clients stop with an upgrade-required
error if absent. There is no legacy remote signing or PIN fallback.

Nostr kind `24133`, the exact recipient `p` tag, NIP-01 hash/Schnorr signature,
paired identities, timestamp checks and outer NIP-44 v2 remain unchanged. The
outer identity keys authenticate transport; they never derive the inner session
keys. Signer verifies the signed event before processing a handshake. Only paired
clients can initialize a session. Pairing still requires local confirmation.

## Handshake and bindings

Before sending a PSBT, refresh `get_account`, then create a random 16-byte request
ID, random 32-byte encryption session ID and independent random secp256k1 private
scalar. Private scalars use rejection sampling in `[1, n-1]`, never identity-key
derivation. Public keys use 33-byte compressed SEC1 encoding as lowercase hex;
validate encoding and curve membership before ECDH. All session IDs and existing
boot challenges are lowercase hex.

Send this JSON inside the signed NIP-44 event:

```json
{
  "protocol": "bitcoin-signer",
  "version": 2,
  "network": "Mainnet",
  "id": "<16 random bytes as hex>",
  "method": "session_init",
  "expires": 1800000150,
  "psbt_hash": "<original PSBT SHA-256 hex>",
  "params": {
    "session": "<current 16-byte signer boot challenge as hex>",
    "session_id": "<32 random bytes as hex>",
    "mobile_ephemeral_public_key": "<compressed ephemeral public key hex>",
    "request_type": "sign_psbt"
  }
}
```

`mobile_ephemeral_public_key` is also the field used by LNbits browsers. The
signer returns a version-2 `session_init` response with the same request binding
and `result: {signer_ephemeral_public_key, init_hash}`. The signed Nostr event
provides authentication; no second embedded signature is used. The client checks
`init_hash` and the signer public key before sending sensitive data or showing PIN
entry. The same request ID identifies the subsequent encrypted `sign_psbt`.

The deadline starts at initiation, normally 150 seconds. It cannot extend during
handshake, PIN entry or retries. Firmware enforces the existing freshness checks
and initiation expiry no later than event creation plus 150 seconds. One active
operation reserves the signer until completion or expiry, including a handshake
whose PSBT never arrives.

## Exact crypto encoding

Serialize these fixed-order JSON arrays as compact UTF-8, without spaces. Numeric
version/expiry fields are JSON integers; every other element is a string.

Initiation hash is SHA-256 of:

```text
["remote-signer-init-v1",2,client_identity,signer_identity,
 mobile_ephemeral_public_key,session_id,request_id,network,boot_challenge,
 psbt_hash,expires]
```

Transcript hash is SHA-256 of:

```text
["remote-signer-session-v1",2,client_identity,signer_identity,
 mobile_ephemeral_public_key,signer_ephemeral_public_key,session_id,
 request_id,network,boot_challenge,psbt_hash,expires]
```

Both identities are the existing 32-byte x-only Nostr public keys as hex. ECDH
returns the raw 32-byte shared-point X coordinate, without a preliminary hash.
Use HKDF-SHA-256 Extract-and-Expand with raw session-ID bytes as salt. Derive two
32-byte AES-256-GCM keys, with `info` equal to the compact UTF-8 JSON array:

```text
["remote-signer-session-v1",transcript_hash_hex,"c2s"]
["remote-signer-session-v1",transcript_hash_hex,"s2c"]
```

Each direction has an independent counter starting at zero, at most 64 distinct
messages per operation. Encode its nonce as four zero bytes followed by the
counter as an unsigned 64-bit big-endian integer. Associated data is compact
UTF-8 JSON:

```text
[transcript_hash_hex,direction,counter,method,inner_request_id]
```

AEAD plaintext is the complete existing request/response JSON with version 2.
The signing PSBT, PIN unlock, progress, errors and signed PSBT are all encrypted.
The outer NIP-44 JSON contains the following authenticated session packet:

```text
{protocol:"bitcoin-signer",version:2,network,id,method,expires,psbt_hash,
 session_id,counter,ciphertext}
```

`ciphertext` is canonical standard base64 of ciphertext followed by the complete
16-byte GCM tag. Check all outer session fields and the inner protocol, version,
network, ID, method and PSBT hash. Inner request expiry equals session expiry.
Do not confuse the boot challenge (`params.session`) with `session_id`.

## Delivery, lifetime and limits

Sign each outgoing event once. Retry that identical event every five seconds;
never re-encrypt new content using the same counter. Each recipient accepts an
unseen counter even if delivery is reordered, rejects consumed counters, and
retains existing monotonic signing-status handling. An exact duplicate signed
request may receive a cached ciphertext reply without repeating crypto, PIN
verification, approval, reservation or signing. Altered duplicates are rejected.
The existing eight-reply ciphertext cache remains bounded through request expiry.

Firmware retains separate bounded 64-entry request and session-ID replay windows,
refusing new work when full rather than evicting live entries. IDs remain recorded
for 180 seconds. Replay records and session keys are volatile: reboot changes the
boot challenge, rejects old handshakes, and makes old encrypted packets unknown.
No perpetual flash-backed history of session IDs is maintained.

Erase ephemeral private keys and raw ECDH immediately after key derivation.
Directional keys survive only this signing operation, including its bound unlock,
and are cleared on success, failure, expiry, rejection, revocation or locking.
Clients also clear on close/backgrounding; browser tab hiding disconnects the
client. Lost connections may retransmit existing ciphertext within the deadline;
they never restore a session after process restart. Terminal retries retain only
ciphertext. Ephemeral material bypasses the five-minute Nostr identity cache.

Firmware uses scoped wiping buffers and secret objects. JavaScript clients wipe
mutable byte buffers and clear PIN fields promptly, without persisting or logging
secrets. JavaScript strings, garbage collection and library intermediate copies
prevent a guarantee that all historical memory copies have been erased. This is
best-effort memory cleanup, not protection from live endpoint compromise.

Frames remain limited to 100,000 bytes. Inner AEAD messages are limited to 48,000
bytes; ciphertext plus tag to 48,016 bytes; outer decrypted JSON to 65,000 bytes.
Unsigned PSBTs remain limited to 32 KiB and 32 inputs/outputs. Before approval or
signature production, firmware conservatively bounds signed-response size using
110 added bytes per input and 1,024 bytes of JSON allowance. A near-limit PSBT
may require fewer inputs to fit the extra encryption layer. No fragmentation is
introduced. Size failures do not reserve daily spending or produce a signature.

Compromise of either or both long-term Nostr secrets later can expose the outer
handshake and metadata but cannot derive historical session keys. Live endpoint
compromise or capture of an active ephemeral private key/session key can expose
that operation. Routing metadata and traffic patterns remain visible to relays.
Shared synthetic vectors are in `tests/session-vectors.json` in each repository.

An identity private key compromised before or during a handshake can impersonate
that peer and compromise new sessions. Forward secrecy protects completed
sessions whose ephemeral material has been erased; it does not repair current
identity authentication.
