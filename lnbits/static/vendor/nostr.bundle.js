"use strict";
var NostrTools = (() => {
  var __defProp = Object.defineProperty;
  var __getOwnPropDesc = Object.getOwnPropertyDescriptor;
  var __getOwnPropNames = Object.getOwnPropertyNames;
  var __hasOwnProp = Object.prototype.hasOwnProperty;
  var __export = (target, all) => {
    for (var name in all)
      __defProp(target, name, { get: all[name], enumerable: true });
  };
  var __copyProps = (to, from, except, desc) => {
    if (from && typeof from === "object" || typeof from === "function") {
      for (let key of __getOwnPropNames(from))
        if (!__hasOwnProp.call(to, key) && key !== except)
          __defProp(to, key, { get: () => from[key], enumerable: !(desc = __getOwnPropDesc(from, key)) || desc.enumerable });
    }
    return to;
  };
  var __toCommonJS = (mod2) => __copyProps(__defProp({}, "__esModule", { value: true }), mod2);

  // index.ts
  var nostr_tools_exports = {};
  __export(nostr_tools_exports, {
    Relay: () => Relay,
    SimplePool: () => SimplePool,
    finalizeEvent: () => finalizeEvent,
    fj: () => fakejson_exports,
    generateSecretKey: () => generateSecretKey,
    getEventHash: () => getEventHash,
    getFilterLimit: () => getFilterLimit,
    getPublicKey: () => getPublicKey,
    kinds: () => kinds_exports,
    matchFilter: () => matchFilter,
    matchFilters: () => matchFilters,
    mergeFilters: () => mergeFilters,
    nip04: () => nip04_exports,
    nip05: () => nip05_exports,
    nip10: () => nip10_exports,
    nip11: () => nip11_exports,
    nip13: () => nip13_exports,
    nip17: () => nip17_exports,
    nip18: () => nip18_exports,
    nip19: () => nip19_exports,
    nip21: () => nip21_exports,
    nip25: () => nip25_exports,
    nip27: () => nip27_exports,
    nip28: () => nip28_exports,
    nip30: () => nip30_exports,
    nip39: () => nip39_exports,
    nip42: () => nip42_exports,
    nip44: () => nip44_exports,
    nip47: () => nip47_exports,
    nip54: () => nip54_exports,
    nip57: () => nip57_exports,
    nip59: () => nip59_exports,
    nip77: () => nip77_exports,
    nip98: () => nip98_exports,
    parseReferences: () => parseReferences,
    serializeEvent: () => serializeEvent,
    sortEvents: () => sortEvents,
    utils: () => utils_exports,
    validateEvent: () => validateEvent,
    verifiedSymbol: () => verifiedSymbol,
    verifyEvent: () => verifyEvent
  });

  // node_modules/@noble/hashes/utils.js
  function isBytes(a) {
    return a instanceof Uint8Array || ArrayBuffer.isView(a) && a.constructor.name === "Uint8Array";
  }
  function anumber(n, title = "") {
    if (!Number.isSafeInteger(n) || n < 0) {
      const prefix = title && `"${title}" `;
      throw new Error(`${prefix}expected integer >= 0, got ${n}`);
    }
  }
  function abytes(value, length, title = "") {
    const bytes = isBytes(value);
    const len = value?.length;
    const needsLen = length !== void 0;
    if (!bytes || needsLen && len !== length) {
      const prefix = title && `"${title}" `;
      const ofLen = needsLen ? ` of length ${length}` : "";
      const got = bytes ? `length=${len}` : `type=${typeof value}`;
      throw new Error(prefix + "expected Uint8Array" + ofLen + ", got " + got);
    }
    return value;
  }
  function ahash(h) {
    if (typeof h !== "function" || typeof h.create !== "function")
      throw new Error("Hash must wrapped by utils.createHasher");
    anumber(h.outputLen);
    anumber(h.blockLen);
  }
  function aexists(instance, checkFinished = true) {
    if (instance.destroyed)
      throw new Error("Hash instance has been destroyed");
    if (checkFinished && instance.finished)
      throw new Error("Hash#digest() has already been called");
  }
  function aoutput(out, instance) {
    abytes(out, void 0, "digestInto() output");
    const min = instance.outputLen;
    if (out.length < min) {
      throw new Error('"digestInto() output" expected to be of length >=' + min);
    }
  }
  function clean(...arrays) {
    for (let i2 = 0; i2 < arrays.length; i2++) {
      arrays[i2].fill(0);
    }
  }
  function createView(arr) {
    return new DataView(arr.buffer, arr.byteOffset, arr.byteLength);
  }
  function rotr(word, shift) {
    return word << 32 - shift | word >>> shift;
  }
  var hasHexBuiltin = /* @__PURE__ */ (() => typeof Uint8Array.from([]).toHex === "function" && typeof Uint8Array.fromHex === "function")();
  var hexes = /* @__PURE__ */ Array.from({ length: 256 }, (_, i2) => i2.toString(16).padStart(2, "0"));
  function bytesToHex(bytes) {
    abytes(bytes);
    if (hasHexBuiltin)
      return bytes.toHex();
    let hex2 = "";
    for (let i2 = 0; i2 < bytes.length; i2++) {
      hex2 += hexes[bytes[i2]];
    }
    return hex2;
  }
  var asciis = { _0: 48, _9: 57, A: 65, F: 70, a: 97, f: 102 };
  function asciiToBase16(ch) {
    if (ch >= asciis._0 && ch <= asciis._9)
      return ch - asciis._0;
    if (ch >= asciis.A && ch <= asciis.F)
      return ch - (asciis.A - 10);
    if (ch >= asciis.a && ch <= asciis.f)
      return ch - (asciis.a - 10);
    return;
  }
  function hexToBytes(hex2) {
    if (typeof hex2 !== "string")
      throw new Error("hex string expected, got " + typeof hex2);
    if (hasHexBuiltin)
      return Uint8Array.fromHex(hex2);
    const hl = hex2.length;
    const al = hl / 2;
    if (hl % 2)
      throw new Error("hex string expected, got unpadded hex of length " + hl);
    const array = new Uint8Array(al);
    for (let ai = 0, hi = 0; ai < al; ai++, hi += 2) {
      const n1 = asciiToBase16(hex2.charCodeAt(hi));
      const n2 = asciiToBase16(hex2.charCodeAt(hi + 1));
      if (n1 === void 0 || n2 === void 0) {
        const char = hex2[hi] + hex2[hi + 1];
        throw new Error('hex string expected, got non-hex character "' + char + '" at index ' + hi);
      }
      array[ai] = n1 * 16 + n2;
    }
    return array;
  }
  function concatBytes(...arrays) {
    let sum = 0;
    for (let i2 = 0; i2 < arrays.length; i2++) {
      const a = arrays[i2];
      abytes(a);
      sum += a.length;
    }
    const res = new Uint8Array(sum);
    for (let i2 = 0, pad2 = 0; i2 < arrays.length; i2++) {
      const a = arrays[i2];
      res.set(a, pad2);
      pad2 += a.length;
    }
    return res;
  }
  function createHasher(hashCons, info = {}) {
    const hashC = (msg, opts) => hashCons(opts).update(msg).digest();
    const tmp = hashCons(void 0);
    hashC.outputLen = tmp.outputLen;
    hashC.blockLen = tmp.blockLen;
    hashC.create = (opts) => hashCons(opts);
    Object.assign(hashC, info);
    return Object.freeze(hashC);
  }
  function randomBytes(bytesLength = 32) {
    const cr = typeof globalThis === "object" ? globalThis.crypto : null;
    if (typeof cr?.getRandomValues !== "function")
      throw new Error("crypto.getRandomValues must be defined");
    return cr.getRandomValues(new Uint8Array(bytesLength));
  }
  var oidNist = (suffix) => ({
    oid: Uint8Array.from([6, 9, 96, 134, 72, 1, 101, 3, 4, 2, suffix])
  });

  // node_modules/@noble/hashes/_md.js
  function Chi(a, b, c) {
    return a & b ^ ~a & c;
  }
  function Maj(a, b, c) {
    return a & b ^ a & c ^ b & c;
  }
  var HashMD = class {
    blockLen;
    outputLen;
    padOffset;
    isLE;
    buffer;
    view;
    finished = false;
    length = 0;
    pos = 0;
    destroyed = false;
    constructor(blockLen, outputLen, padOffset, isLE2) {
      this.blockLen = blockLen;
      this.outputLen = outputLen;
      this.padOffset = padOffset;
      this.isLE = isLE2;
      this.buffer = new Uint8Array(blockLen);
      this.view = createView(this.buffer);
    }
    update(data) {
      aexists(this);
      abytes(data);
      const { view, buffer, blockLen } = this;
      const len = data.length;
      for (let pos = 0; pos < len; ) {
        const take = Math.min(blockLen - this.pos, len - pos);
        if (take === blockLen) {
          const dataView = createView(data);
          for (; blockLen <= len - pos; pos += blockLen)
            this.process(dataView, pos);
          continue;
        }
        buffer.set(data.subarray(pos, pos + take), this.pos);
        this.pos += take;
        pos += take;
        if (this.pos === blockLen) {
          this.process(view, 0);
          this.pos = 0;
        }
      }
      this.length += data.length;
      this.roundClean();
      return this;
    }
    digestInto(out) {
      aexists(this);
      aoutput(out, this);
      this.finished = true;
      const { buffer, view, blockLen, isLE: isLE2 } = this;
      let { pos } = this;
      buffer[pos++] = 128;
      clean(this.buffer.subarray(pos));
      if (this.padOffset > blockLen - pos) {
        this.process(view, 0);
        pos = 0;
      }
      for (let i2 = pos; i2 < blockLen; i2++)
        buffer[i2] = 0;
      view.setBigUint64(blockLen - 8, BigInt(this.length * 8), isLE2);
      this.process(view, 0);
      const oview = createView(out);
      const len = this.outputLen;
      if (len % 4)
        throw new Error("_sha2: outputLen must be aligned to 32bit");
      const outLen = len / 4;
      const state = this.get();
      if (outLen > state.length)
        throw new Error("_sha2: outputLen bigger than state");
      for (let i2 = 0; i2 < outLen; i2++)
        oview.setUint32(4 * i2, state[i2], isLE2);
    }
    digest() {
      const { buffer, outputLen } = this;
      this.digestInto(buffer);
      const res = buffer.slice(0, outputLen);
      this.destroy();
      return res;
    }
    _cloneInto(to) {
      to ||= new this.constructor();
      to.set(...this.get());
      const { blockLen, buffer, length, finished, destroyed, pos } = this;
      to.destroyed = destroyed;
      to.finished = finished;
      to.length = length;
      to.pos = pos;
      if (length % blockLen)
        to.buffer.set(buffer);
      return to;
    }
    clone() {
      return this._cloneInto();
    }
  };
  var SHA256_IV = /* @__PURE__ */ Uint32Array.from([
    1779033703,
    3144134277,
    1013904242,
    2773480762,
    1359893119,
    2600822924,
    528734635,
    1541459225
  ]);

  // node_modules/@noble/hashes/sha2.js
  var SHA256_K = /* @__PURE__ */ Uint32Array.from([
    1116352408,
    1899447441,
    3049323471,
    3921009573,
    961987163,
    1508970993,
    2453635748,
    2870763221,
    3624381080,
    310598401,
    607225278,
    1426881987,
    1925078388,
    2162078206,
    2614888103,
    3248222580,
    3835390401,
    4022224774,
    264347078,
    604807628,
    770255983,
    1249150122,
    1555081692,
    1996064986,
    2554220882,
    2821834349,
    2952996808,
    3210313671,
    3336571891,
    3584528711,
    113926993,
    338241895,
    666307205,
    773529912,
    1294757372,
    1396182291,
    1695183700,
    1986661051,
    2177026350,
    2456956037,
    2730485921,
    2820302411,
    3259730800,
    3345764771,
    3516065817,
    3600352804,
    4094571909,
    275423344,
    430227734,
    506948616,
    659060556,
    883997877,
    958139571,
    1322822218,
    1537002063,
    1747873779,
    1955562222,
    2024104815,
    2227730452,
    2361852424,
    2428436474,
    2756734187,
    3204031479,
    3329325298
  ]);
  var SHA256_W = /* @__PURE__ */ new Uint32Array(64);
  var SHA2_32B = class extends HashMD {
    constructor(outputLen) {
      super(64, outputLen, 8, false);
    }
    get() {
      const { A, B, C, D, E, F, G, H } = this;
      return [A, B, C, D, E, F, G, H];
    }
    set(A, B, C, D, E, F, G, H) {
      this.A = A | 0;
      this.B = B | 0;
      this.C = C | 0;
      this.D = D | 0;
      this.E = E | 0;
      this.F = F | 0;
      this.G = G | 0;
      this.H = H | 0;
    }
    process(view, offset) {
      for (let i2 = 0; i2 < 16; i2++, offset += 4)
        SHA256_W[i2] = view.getUint32(offset, false);
      for (let i2 = 16; i2 < 64; i2++) {
        const W15 = SHA256_W[i2 - 15];
        const W2 = SHA256_W[i2 - 2];
        const s0 = rotr(W15, 7) ^ rotr(W15, 18) ^ W15 >>> 3;
        const s1 = rotr(W2, 17) ^ rotr(W2, 19) ^ W2 >>> 10;
        SHA256_W[i2] = s1 + SHA256_W[i2 - 7] + s0 + SHA256_W[i2 - 16] | 0;
      }
      let { A, B, C, D, E, F, G, H } = this;
      for (let i2 = 0; i2 < 64; i2++) {
        const sigma1 = rotr(E, 6) ^ rotr(E, 11) ^ rotr(E, 25);
        const T1 = H + sigma1 + Chi(E, F, G) + SHA256_K[i2] + SHA256_W[i2] | 0;
        const sigma0 = rotr(A, 2) ^ rotr(A, 13) ^ rotr(A, 22);
        const T2 = sigma0 + Maj(A, B, C) | 0;
        H = G;
        G = F;
        F = E;
        E = D + T1 | 0;
        D = C;
        C = B;
        B = A;
        A = T1 + T2 | 0;
      }
      A = A + this.A | 0;
      B = B + this.B | 0;
      C = C + this.C | 0;
      D = D + this.D | 0;
      E = E + this.E | 0;
      F = F + this.F | 0;
      G = G + this.G | 0;
      H = H + this.H | 0;
      this.set(A, B, C, D, E, F, G, H);
    }
    roundClean() {
      clean(SHA256_W);
    }
    destroy() {
      this.set(0, 0, 0, 0, 0, 0, 0, 0);
      clean(this.buffer);
    }
  };
  var _SHA256 = class extends SHA2_32B {
    A = SHA256_IV[0] | 0;
    B = SHA256_IV[1] | 0;
    C = SHA256_IV[2] | 0;
    D = SHA256_IV[3] | 0;
    E = SHA256_IV[4] | 0;
    F = SHA256_IV[5] | 0;
    G = SHA256_IV[6] | 0;
    H = SHA256_IV[7] | 0;
    constructor() {
      super(32);
    }
  };
  var sha256 = /* @__PURE__ */ createHasher(
    () => new _SHA256(),
    /* @__PURE__ */ oidNist(1)
  );

  // node_modules/@noble/curves/utils.js
  var _0n = /* @__PURE__ */ BigInt(0);
  var _1n = /* @__PURE__ */ BigInt(1);
  function abool(value, title = "") {
    if (typeof value !== "boolean") {
      const prefix = title && `"${title}" `;
      throw new Error(prefix + "expected boolean, got type=" + typeof value);
    }
    return value;
  }
  function abignumber(n) {
    if (typeof n === "bigint") {
      if (!isPosBig(n))
        throw new Error("positive bigint expected, got " + n);
    } else
      anumber(n);
    return n;
  }
  function numberToHexUnpadded(num2) {
    const hex2 = abignumber(num2).toString(16);
    return hex2.length & 1 ? "0" + hex2 : hex2;
  }
  function hexToNumber(hex2) {
    if (typeof hex2 !== "string")
      throw new Error("hex string expected, got " + typeof hex2);
    return hex2 === "" ? _0n : BigInt("0x" + hex2);
  }
  function bytesToNumberBE(bytes) {
    return hexToNumber(bytesToHex(bytes));
  }
  function bytesToNumberLE(bytes) {
    return hexToNumber(bytesToHex(copyBytes(abytes(bytes)).reverse()));
  }
  function numberToBytesBE(n, len) {
    anumber(len);
    n = abignumber(n);
    const res = hexToBytes(n.toString(16).padStart(len * 2, "0"));
    if (res.length !== len)
      throw new Error("number too large");
    return res;
  }
  function numberToBytesLE(n, len) {
    return numberToBytesBE(n, len).reverse();
  }
  function copyBytes(bytes) {
    return Uint8Array.from(bytes);
  }
  function asciiToBytes(ascii) {
    return Uint8Array.from(ascii, (c, i2) => {
      const charCode = c.charCodeAt(0);
      if (c.length !== 1 || charCode > 127) {
        throw new Error(`string contains non-ASCII character "${ascii[i2]}" with code ${charCode} at position ${i2}`);
      }
      return charCode;
    });
  }
  var isPosBig = (n) => typeof n === "bigint" && _0n <= n;
  function inRange(n, min, max) {
    return isPosBig(n) && isPosBig(min) && isPosBig(max) && min <= n && n < max;
  }
  function aInRange(title, n, min, max) {
    if (!inRange(n, min, max))
      throw new Error("expected valid " + title + ": " + min + " <= n < " + max + ", got " + n);
  }
  function bitLen(n) {
    let len;
    for (len = 0; n > _0n; n >>= _1n, len += 1)
      ;
    return len;
  }
  var bitMask = (n) => (_1n << BigInt(n)) - _1n;
  function createHmacDrbg(hashLen, qByteLen, hmacFn) {
    anumber(hashLen, "hashLen");
    anumber(qByteLen, "qByteLen");
    if (typeof hmacFn !== "function")
      throw new Error("hmacFn must be a function");
    const u8n = (len) => new Uint8Array(len);
    const NULL = Uint8Array.of();
    const byte0 = Uint8Array.of(0);
    const byte1 = Uint8Array.of(1);
    const _maxDrbgIters = 1e3;
    let v = u8n(hashLen);
    let k = u8n(hashLen);
    let i2 = 0;
    const reset = () => {
      v.fill(1);
      k.fill(0);
      i2 = 0;
    };
    const h = (...msgs) => hmacFn(k, concatBytes(v, ...msgs));
    const reseed = (seed = NULL) => {
      k = h(byte0, seed);
      v = h();
      if (seed.length === 0)
        return;
      k = h(byte1, seed);
      v = h();
    };
    const gen = () => {
      if (i2++ >= _maxDrbgIters)
        throw new Error("drbg: tried max amount of iterations");
      let len = 0;
      const out = [];
      while (len < qByteLen) {
        v = h();
        const sl = v.slice();
        out.push(sl);
        len += v.length;
      }
      return concatBytes(...out);
    };
    const genUntil = (seed, pred) => {
      reset();
      reseed(seed);
      let res = void 0;
      while (!(res = pred(gen())))
        reseed();
      reset();
      return res;
    };
    return genUntil;
  }
  function validateObject(object, fields = {}, optFields = {}) {
    if (!object || typeof object !== "object")
      throw new Error("expected valid options object");
    function checkField(fieldName, expectedType, isOpt) {
      const val = object[fieldName];
      if (isOpt && val === void 0)
        return;
      const current = typeof val;
      if (current !== expectedType || val === null)
        throw new Error(`param "${fieldName}" is invalid: expected ${expectedType}, got ${current}`);
    }
    const iter = (f, isOpt) => Object.entries(f).forEach(([k, v]) => checkField(k, v, isOpt));
    iter(fields, false);
    iter(optFields, true);
  }
  function memoized(fn) {
    const map = /* @__PURE__ */ new WeakMap();
    return (arg, ...args) => {
      const val = map.get(arg);
      if (val !== void 0)
        return val;
      const computed = fn(arg, ...args);
      map.set(arg, computed);
      return computed;
    };
  }

  // node_modules/@noble/curves/abstract/modular.js
  var _0n2 = /* @__PURE__ */ BigInt(0);
  var _1n2 = /* @__PURE__ */ BigInt(1);
  var _2n = /* @__PURE__ */ BigInt(2);
  var _3n = /* @__PURE__ */ BigInt(3);
  var _4n = /* @__PURE__ */ BigInt(4);
  var _5n = /* @__PURE__ */ BigInt(5);
  var _7n = /* @__PURE__ */ BigInt(7);
  var _8n = /* @__PURE__ */ BigInt(8);
  var _9n = /* @__PURE__ */ BigInt(9);
  var _16n = /* @__PURE__ */ BigInt(16);
  function mod(a, b) {
    const result = a % b;
    return result >= _0n2 ? result : b + result;
  }
  function pow2(x, power, modulo) {
    let res = x;
    while (power-- > _0n2) {
      res *= res;
      res %= modulo;
    }
    return res;
  }
  function invert(number, modulo) {
    if (number === _0n2)
      throw new Error("invert: expected non-zero number");
    if (modulo <= _0n2)
      throw new Error("invert: expected positive modulus, got " + modulo);
    let a = mod(number, modulo);
    let b = modulo;
    let x = _0n2, y = _1n2, u = _1n2, v = _0n2;
    while (a !== _0n2) {
      const q = b / a;
      const r = b % a;
      const m = x - u * q;
      const n = y - v * q;
      b = a, a = r, x = u, y = v, u = m, v = n;
    }
    const gcd2 = b;
    if (gcd2 !== _1n2)
      throw new Error("invert: does not exist");
    return mod(x, modulo);
  }
  function assertIsSquare(Fp, root, n) {
    if (!Fp.eql(Fp.sqr(root), n))
      throw new Error("Cannot find square root");
  }
  function sqrt3mod4(Fp, n) {
    const p1div4 = (Fp.ORDER + _1n2) / _4n;
    const root = Fp.pow(n, p1div4);
    assertIsSquare(Fp, root, n);
    return root;
  }
  function sqrt5mod8(Fp, n) {
    const p5div8 = (Fp.ORDER - _5n) / _8n;
    const n2 = Fp.mul(n, _2n);
    const v = Fp.pow(n2, p5div8);
    const nv = Fp.mul(n, v);
    const i2 = Fp.mul(Fp.mul(nv, _2n), v);
    const root = Fp.mul(nv, Fp.sub(i2, Fp.ONE));
    assertIsSquare(Fp, root, n);
    return root;
  }
  function sqrt9mod16(P) {
    const Fp_ = Field(P);
    const tn = tonelliShanks(P);
    const c1 = tn(Fp_, Fp_.neg(Fp_.ONE));
    const c2 = tn(Fp_, c1);
    const c3 = tn(Fp_, Fp_.neg(c1));
    const c4 = (P + _7n) / _16n;
    return (Fp, n) => {
      let tv1 = Fp.pow(n, c4);
      let tv2 = Fp.mul(tv1, c1);
      const tv3 = Fp.mul(tv1, c2);
      const tv4 = Fp.mul(tv1, c3);
      const e1 = Fp.eql(Fp.sqr(tv2), n);
      const e2 = Fp.eql(Fp.sqr(tv3), n);
      tv1 = Fp.cmov(tv1, tv2, e1);
      tv2 = Fp.cmov(tv4, tv3, e2);
      const e3 = Fp.eql(Fp.sqr(tv2), n);
      const root = Fp.cmov(tv1, tv2, e3);
      assertIsSquare(Fp, root, n);
      return root;
    };
  }
  function tonelliShanks(P) {
    if (P < _3n)
      throw new Error("sqrt is not defined for small field");
    let Q = P - _1n2;
    let S = 0;
    while (Q % _2n === _0n2) {
      Q /= _2n;
      S++;
    }
    let Z = _2n;
    const _Fp = Field(P);
    while (FpLegendre(_Fp, Z) === 1) {
      if (Z++ > 1e3)
        throw new Error("Cannot find square root: probably non-prime P");
    }
    if (S === 1)
      return sqrt3mod4;
    let cc = _Fp.pow(Z, Q);
    const Q1div2 = (Q + _1n2) / _2n;
    return function tonelliSlow(Fp, n) {
      if (Fp.is0(n))
        return n;
      if (FpLegendre(Fp, n) !== 1)
        throw new Error("Cannot find square root");
      let M = S;
      let c = Fp.mul(Fp.ONE, cc);
      let t = Fp.pow(n, Q);
      let R = Fp.pow(n, Q1div2);
      while (!Fp.eql(t, Fp.ONE)) {
        if (Fp.is0(t))
          return Fp.ZERO;
        let i2 = 1;
        let t_tmp = Fp.sqr(t);
        while (!Fp.eql(t_tmp, Fp.ONE)) {
          i2++;
          t_tmp = Fp.sqr(t_tmp);
          if (i2 === M)
            throw new Error("Cannot find square root");
        }
        const exponent = _1n2 << BigInt(M - i2 - 1);
        const b = Fp.pow(c, exponent);
        M = i2;
        c = Fp.sqr(b);
        t = Fp.mul(t, c);
        R = Fp.mul(R, b);
      }
      return R;
    };
  }
  function FpSqrt(P) {
    if (P % _4n === _3n)
      return sqrt3mod4;
    if (P % _8n === _5n)
      return sqrt5mod8;
    if (P % _16n === _9n)
      return sqrt9mod16(P);
    return tonelliShanks(P);
  }
  var FIELD_FIELDS = [
    "create",
    "isValid",
    "is0",
    "neg",
    "inv",
    "sqrt",
    "sqr",
    "eql",
    "add",
    "sub",
    "mul",
    "pow",
    "div",
    "addN",
    "subN",
    "mulN",
    "sqrN"
  ];
  function validateField(field) {
    const initial = {
      ORDER: "bigint",
      BYTES: "number",
      BITS: "number"
    };
    const opts = FIELD_FIELDS.reduce((map, val) => {
      map[val] = "function";
      return map;
    }, initial);
    validateObject(field, opts);
    return field;
  }
  function FpPow(Fp, num2, power) {
    if (power < _0n2)
      throw new Error("invalid exponent, negatives unsupported");
    if (power === _0n2)
      return Fp.ONE;
    if (power === _1n2)
      return num2;
    let p = Fp.ONE;
    let d = num2;
    while (power > _0n2) {
      if (power & _1n2)
        p = Fp.mul(p, d);
      d = Fp.sqr(d);
      power >>= _1n2;
    }
    return p;
  }
  function FpInvertBatch(Fp, nums, passZero = false) {
    const inverted = new Array(nums.length).fill(passZero ? Fp.ZERO : void 0);
    const multipliedAcc = nums.reduce((acc, num2, i2) => {
      if (Fp.is0(num2))
        return acc;
      inverted[i2] = acc;
      return Fp.mul(acc, num2);
    }, Fp.ONE);
    const invertedAcc = Fp.inv(multipliedAcc);
    nums.reduceRight((acc, num2, i2) => {
      if (Fp.is0(num2))
        return acc;
      inverted[i2] = Fp.mul(acc, inverted[i2]);
      return Fp.mul(acc, num2);
    }, invertedAcc);
    return inverted;
  }
  function FpLegendre(Fp, n) {
    const p1mod2 = (Fp.ORDER - _1n2) / _2n;
    const powered = Fp.pow(n, p1mod2);
    const yes = Fp.eql(powered, Fp.ONE);
    const zero = Fp.eql(powered, Fp.ZERO);
    const no = Fp.eql(powered, Fp.neg(Fp.ONE));
    if (!yes && !zero && !no)
      throw new Error("invalid Legendre symbol result");
    return yes ? 1 : zero ? 0 : -1;
  }
  function nLength(n, nBitLength) {
    if (nBitLength !== void 0)
      anumber(nBitLength);
    const _nBitLength = nBitLength !== void 0 ? nBitLength : n.toString(2).length;
    const nByteLength = Math.ceil(_nBitLength / 8);
    return { nBitLength: _nBitLength, nByteLength };
  }
  var _Field = class {
    ORDER;
    BITS;
    BYTES;
    isLE;
    ZERO = _0n2;
    ONE = _1n2;
    _lengths;
    _sqrt;
    _mod;
    constructor(ORDER, opts = {}) {
      if (ORDER <= _0n2)
        throw new Error("invalid field: expected ORDER > 0, got " + ORDER);
      let _nbitLength = void 0;
      this.isLE = false;
      if (opts != null && typeof opts === "object") {
        if (typeof opts.BITS === "number")
          _nbitLength = opts.BITS;
        if (typeof opts.sqrt === "function")
          this.sqrt = opts.sqrt;
        if (typeof opts.isLE === "boolean")
          this.isLE = opts.isLE;
        if (opts.allowedLengths)
          this._lengths = opts.allowedLengths?.slice();
        if (typeof opts.modFromBytes === "boolean")
          this._mod = opts.modFromBytes;
      }
      const { nBitLength, nByteLength } = nLength(ORDER, _nbitLength);
      if (nByteLength > 2048)
        throw new Error("invalid field: expected ORDER of <= 2048 bytes");
      this.ORDER = ORDER;
      this.BITS = nBitLength;
      this.BYTES = nByteLength;
      this._sqrt = void 0;
      Object.preventExtensions(this);
    }
    create(num2) {
      return mod(num2, this.ORDER);
    }
    isValid(num2) {
      if (typeof num2 !== "bigint")
        throw new Error("invalid field element: expected bigint, got " + typeof num2);
      return _0n2 <= num2 && num2 < this.ORDER;
    }
    is0(num2) {
      return num2 === _0n2;
    }
    isValidNot0(num2) {
      return !this.is0(num2) && this.isValid(num2);
    }
    isOdd(num2) {
      return (num2 & _1n2) === _1n2;
    }
    neg(num2) {
      return mod(-num2, this.ORDER);
    }
    eql(lhs, rhs) {
      return lhs === rhs;
    }
    sqr(num2) {
      return mod(num2 * num2, this.ORDER);
    }
    add(lhs, rhs) {
      return mod(lhs + rhs, this.ORDER);
    }
    sub(lhs, rhs) {
      return mod(lhs - rhs, this.ORDER);
    }
    mul(lhs, rhs) {
      return mod(lhs * rhs, this.ORDER);
    }
    pow(num2, power) {
      return FpPow(this, num2, power);
    }
    div(lhs, rhs) {
      return mod(lhs * invert(rhs, this.ORDER), this.ORDER);
    }
    sqrN(num2) {
      return num2 * num2;
    }
    addN(lhs, rhs) {
      return lhs + rhs;
    }
    subN(lhs, rhs) {
      return lhs - rhs;
    }
    mulN(lhs, rhs) {
      return lhs * rhs;
    }
    inv(num2) {
      return invert(num2, this.ORDER);
    }
    sqrt(num2) {
      if (!this._sqrt)
        this._sqrt = FpSqrt(this.ORDER);
      return this._sqrt(this, num2);
    }
    toBytes(num2) {
      return this.isLE ? numberToBytesLE(num2, this.BYTES) : numberToBytesBE(num2, this.BYTES);
    }
    fromBytes(bytes, skipValidation = false) {
      abytes(bytes);
      const { _lengths: allowedLengths, BYTES, isLE: isLE2, ORDER, _mod: modFromBytes } = this;
      if (allowedLengths) {
        if (!allowedLengths.includes(bytes.length) || bytes.length > BYTES) {
          throw new Error("Field.fromBytes: expected " + allowedLengths + " bytes, got " + bytes.length);
        }
        const padded = new Uint8Array(BYTES);
        padded.set(bytes, isLE2 ? 0 : padded.length - bytes.length);
        bytes = padded;
      }
      if (bytes.length !== BYTES)
        throw new Error("Field.fromBytes: expected " + BYTES + " bytes, got " + bytes.length);
      let scalar = isLE2 ? bytesToNumberLE(bytes) : bytesToNumberBE(bytes);
      if (modFromBytes)
        scalar = mod(scalar, ORDER);
      if (!skipValidation) {
        if (!this.isValid(scalar))
          throw new Error("invalid field element: outside of range 0..ORDER");
      }
      return scalar;
    }
    invertBatch(lst) {
      return FpInvertBatch(this, lst);
    }
    cmov(a, b, condition) {
      return condition ? b : a;
    }
  };
  function Field(ORDER, opts = {}) {
    return new _Field(ORDER, opts);
  }
  function getFieldBytesLength(fieldOrder) {
    if (typeof fieldOrder !== "bigint")
      throw new Error("field order must be bigint");
    const bitLength = fieldOrder.toString(2).length;
    return Math.ceil(bitLength / 8);
  }
  function getMinHashLength(fieldOrder) {
    const length = getFieldBytesLength(fieldOrder);
    return length + Math.ceil(length / 2);
  }
  function mapHashToField(key, fieldOrder, isLE2 = false) {
    abytes(key);
    const len = key.length;
    const fieldLen = getFieldBytesLength(fieldOrder);
    const minLen = getMinHashLength(fieldOrder);
    if (len < 16 || len < minLen || len > 1024)
      throw new Error("expected " + minLen + "-1024 bytes of input, got " + len);
    const num2 = isLE2 ? bytesToNumberLE(key) : bytesToNumberBE(key);
    const reduced = mod(num2, fieldOrder - _1n2) + _1n2;
    return isLE2 ? numberToBytesLE(reduced, fieldLen) : numberToBytesBE(reduced, fieldLen);
  }

  // node_modules/@noble/curves/abstract/curve.js
  var _0n3 = /* @__PURE__ */ BigInt(0);
  var _1n3 = /* @__PURE__ */ BigInt(1);
  function negateCt(condition, item) {
    const neg = item.negate();
    return condition ? neg : item;
  }
  function normalizeZ(c, points) {
    const invertedZs = FpInvertBatch(c.Fp, points.map((p) => p.Z));
    return points.map((p, i2) => c.fromAffine(p.toAffine(invertedZs[i2])));
  }
  function validateW(W, bits) {
    if (!Number.isSafeInteger(W) || W <= 0 || W > bits)
      throw new Error("invalid window size, expected [1.." + bits + "], got W=" + W);
  }
  function calcWOpts(W, scalarBits) {
    validateW(W, scalarBits);
    const windows = Math.ceil(scalarBits / W) + 1;
    const windowSize = 2 ** (W - 1);
    const maxNumber = 2 ** W;
    const mask = bitMask(W);
    const shiftBy = BigInt(W);
    return { windows, windowSize, mask, maxNumber, shiftBy };
  }
  function calcOffsets(n, window, wOpts) {
    const { windowSize, mask, maxNumber, shiftBy } = wOpts;
    let wbits = Number(n & mask);
    let nextN = n >> shiftBy;
    if (wbits > windowSize) {
      wbits -= maxNumber;
      nextN += _1n3;
    }
    const offsetStart = window * windowSize;
    const offset = offsetStart + Math.abs(wbits) - 1;
    const isZero = wbits === 0;
    const isNeg = wbits < 0;
    const isNegF = window % 2 !== 0;
    const offsetF = offsetStart;
    return { nextN, offset, isZero, isNeg, isNegF, offsetF };
  }
  var pointPrecomputes = /* @__PURE__ */ new WeakMap();
  var pointWindowSizes = /* @__PURE__ */ new WeakMap();
  function getW(P) {
    return pointWindowSizes.get(P) || 1;
  }
  function assert0(n) {
    if (n !== _0n3)
      throw new Error("invalid wNAF");
  }
  var wNAF = class {
    BASE;
    ZERO;
    Fn;
    bits;
    constructor(Point, bits) {
      this.BASE = Point.BASE;
      this.ZERO = Point.ZERO;
      this.Fn = Point.Fn;
      this.bits = bits;
    }
    _unsafeLadder(elm, n, p = this.ZERO) {
      let d = elm;
      while (n > _0n3) {
        if (n & _1n3)
          p = p.add(d);
        d = d.double();
        n >>= _1n3;
      }
      return p;
    }
    precomputeWindow(point, W) {
      const { windows, windowSize } = calcWOpts(W, this.bits);
      const points = [];
      let p = point;
      let base = p;
      for (let window = 0; window < windows; window++) {
        base = p;
        points.push(base);
        for (let i2 = 1; i2 < windowSize; i2++) {
          base = base.add(p);
          points.push(base);
        }
        p = base.double();
      }
      return points;
    }
    wNAF(W, precomputes, n) {
      if (!this.Fn.isValid(n))
        throw new Error("invalid scalar");
      let p = this.ZERO;
      let f = this.BASE;
      const wo = calcWOpts(W, this.bits);
      for (let window = 0; window < wo.windows; window++) {
        const { nextN, offset, isZero, isNeg, isNegF, offsetF } = calcOffsets(n, window, wo);
        n = nextN;
        if (isZero) {
          f = f.add(negateCt(isNegF, precomputes[offsetF]));
        } else {
          p = p.add(negateCt(isNeg, precomputes[offset]));
        }
      }
      assert0(n);
      return { p, f };
    }
    wNAFUnsafe(W, precomputes, n, acc = this.ZERO) {
      const wo = calcWOpts(W, this.bits);
      for (let window = 0; window < wo.windows; window++) {
        if (n === _0n3)
          break;
        const { nextN, offset, isZero, isNeg } = calcOffsets(n, window, wo);
        n = nextN;
        if (isZero) {
          continue;
        } else {
          const item = precomputes[offset];
          acc = acc.add(isNeg ? item.negate() : item);
        }
      }
      assert0(n);
      return acc;
    }
    getPrecomputes(W, point, transform) {
      let comp = pointPrecomputes.get(point);
      if (!comp) {
        comp = this.precomputeWindow(point, W);
        if (W !== 1) {
          if (typeof transform === "function")
            comp = transform(comp);
          pointPrecomputes.set(point, comp);
        }
      }
      return comp;
    }
    cached(point, scalar, transform) {
      const W = getW(point);
      return this.wNAF(W, this.getPrecomputes(W, point, transform), scalar);
    }
    unsafe(point, scalar, transform, prev) {
      const W = getW(point);
      if (W === 1)
        return this._unsafeLadder(point, scalar, prev);
      return this.wNAFUnsafe(W, this.getPrecomputes(W, point, transform), scalar, prev);
    }
    createCache(P, W) {
      validateW(W, this.bits);
      pointWindowSizes.set(P, W);
      pointPrecomputes.delete(P);
    }
    hasCache(elm) {
      return getW(elm) !== 1;
    }
  };
  function mulEndoUnsafe(Point, point, k1, k2) {
    let acc = point;
    let p1 = Point.ZERO;
    let p2 = Point.ZERO;
    while (k1 > _0n3 || k2 > _0n3) {
      if (k1 & _1n3)
        p1 = p1.add(acc);
      if (k2 & _1n3)
        p2 = p2.add(acc);
      acc = acc.double();
      k1 >>= _1n3;
      k2 >>= _1n3;
    }
    return { p1, p2 };
  }
  function createField(order, field, isLE2) {
    if (field) {
      if (field.ORDER !== order)
        throw new Error("Field.ORDER must match order: Fp == p, Fn == n");
      validateField(field);
      return field;
    } else {
      return Field(order, { isLE: isLE2 });
    }
  }
  function createCurveFields(type, CURVE, curveOpts = {}, FpFnLE) {
    if (FpFnLE === void 0)
      FpFnLE = type === "edwards";
    if (!CURVE || typeof CURVE !== "object")
      throw new Error(`expected valid ${type} CURVE object`);
    for (const p of ["p", "n", "h"]) {
      const val = CURVE[p];
      if (!(typeof val === "bigint" && val > _0n3))
        throw new Error(`CURVE.${p} must be positive bigint`);
    }
    const Fp = createField(CURVE.p, curveOpts.Fp, FpFnLE);
    const Fn = createField(CURVE.n, curveOpts.Fn, FpFnLE);
    const _b = type === "weierstrass" ? "b" : "d";
    const params = ["Gx", "Gy", "a", _b];
    for (const p of params) {
      if (!Fp.isValid(CURVE[p]))
        throw new Error(`CURVE.${p} must be valid field element of CURVE.Fp`);
    }
    CURVE = Object.freeze(Object.assign({}, CURVE));
    return { CURVE, Fp, Fn };
  }
  function createKeygen(randomSecretKey, getPublicKey2) {
    return function keygen(seed) {
      const secretKey = randomSecretKey(seed);
      return { secretKey, publicKey: getPublicKey2(secretKey) };
    };
  }

  // node_modules/@noble/hashes/hmac.js
  var _HMAC = class {
    oHash;
    iHash;
    blockLen;
    outputLen;
    finished = false;
    destroyed = false;
    constructor(hash, key) {
      ahash(hash);
      abytes(key, void 0, "key");
      this.iHash = hash.create();
      if (typeof this.iHash.update !== "function")
        throw new Error("Expected instance of class which extends utils.Hash");
      this.blockLen = this.iHash.blockLen;
      this.outputLen = this.iHash.outputLen;
      const blockLen = this.blockLen;
      const pad2 = new Uint8Array(blockLen);
      pad2.set(key.length > blockLen ? hash.create().update(key).digest() : key);
      for (let i2 = 0; i2 < pad2.length; i2++)
        pad2[i2] ^= 54;
      this.iHash.update(pad2);
      this.oHash = hash.create();
      for (let i2 = 0; i2 < pad2.length; i2++)
        pad2[i2] ^= 54 ^ 92;
      this.oHash.update(pad2);
      clean(pad2);
    }
    update(buf) {
      aexists(this);
      this.iHash.update(buf);
      return this;
    }
    digestInto(out) {
      aexists(this);
      abytes(out, this.outputLen, "output");
      this.finished = true;
      this.iHash.digestInto(out);
      this.oHash.update(out);
      this.oHash.digestInto(out);
      this.destroy();
    }
    digest() {
      const out = new Uint8Array(this.oHash.outputLen);
      this.digestInto(out);
      return out;
    }
    _cloneInto(to) {
      to ||= Object.create(Object.getPrototypeOf(this), {});
      const { oHash, iHash, finished, destroyed, blockLen, outputLen } = this;
      to = to;
      to.finished = finished;
      to.destroyed = destroyed;
      to.blockLen = blockLen;
      to.outputLen = outputLen;
      to.oHash = oHash._cloneInto(to.oHash);
      to.iHash = iHash._cloneInto(to.iHash);
      return to;
    }
    clone() {
      return this._cloneInto();
    }
    destroy() {
      this.destroyed = true;
      this.oHash.destroy();
      this.iHash.destroy();
    }
  };
  var hmac = (hash, key, message) => new _HMAC(hash, key).update(message).digest();
  hmac.create = (hash, key) => new _HMAC(hash, key);

  // node_modules/@noble/curves/abstract/weierstrass.js
  var divNearest = (num2, den) => (num2 + (num2 >= 0 ? den : -den) / _2n2) / den;
  function _splitEndoScalar(k, basis, n) {
    const [[a1, b1], [a2, b2]] = basis;
    const c1 = divNearest(b2 * k, n);
    const c2 = divNearest(-b1 * k, n);
    let k1 = k - c1 * a1 - c2 * a2;
    let k2 = -c1 * b1 - c2 * b2;
    const k1neg = k1 < _0n4;
    const k2neg = k2 < _0n4;
    if (k1neg)
      k1 = -k1;
    if (k2neg)
      k2 = -k2;
    const MAX_NUM = bitMask(Math.ceil(bitLen(n) / 2)) + _1n4;
    if (k1 < _0n4 || k1 >= MAX_NUM || k2 < _0n4 || k2 >= MAX_NUM) {
      throw new Error("splitScalar (endomorphism): failed, k=" + k);
    }
    return { k1neg, k1, k2neg, k2 };
  }
  function validateSigFormat(format) {
    if (!["compact", "recovered", "der"].includes(format))
      throw new Error('Signature format must be "compact", "recovered", or "der"');
    return format;
  }
  function validateSigOpts(opts, def) {
    const optsn = {};
    for (let optName of Object.keys(def)) {
      optsn[optName] = opts[optName] === void 0 ? def[optName] : opts[optName];
    }
    abool(optsn.lowS, "lowS");
    abool(optsn.prehash, "prehash");
    if (optsn.format !== void 0)
      validateSigFormat(optsn.format);
    return optsn;
  }
  var DERErr = class extends Error {
    constructor(m = "") {
      super(m);
    }
  };
  var DER = {
    Err: DERErr,
    _tlv: {
      encode: (tag, data) => {
        const { Err: E } = DER;
        if (tag < 0 || tag > 256)
          throw new E("tlv.encode: wrong tag");
        if (data.length & 1)
          throw new E("tlv.encode: unpadded data");
        const dataLen = data.length / 2;
        const len = numberToHexUnpadded(dataLen);
        if (len.length / 2 & 128)
          throw new E("tlv.encode: long form length too big");
        const lenLen = dataLen > 127 ? numberToHexUnpadded(len.length / 2 | 128) : "";
        const t = numberToHexUnpadded(tag);
        return t + lenLen + len + data;
      },
      decode(tag, data) {
        const { Err: E } = DER;
        let pos = 0;
        if (tag < 0 || tag > 256)
          throw new E("tlv.encode: wrong tag");
        if (data.length < 2 || data[pos++] !== tag)
          throw new E("tlv.decode: wrong tlv");
        const first = data[pos++];
        const isLong = !!(first & 128);
        let length = 0;
        if (!isLong)
          length = first;
        else {
          const lenLen = first & 127;
          if (!lenLen)
            throw new E("tlv.decode(long): indefinite length not supported");
          if (lenLen > 4)
            throw new E("tlv.decode(long): byte length is too big");
          const lengthBytes = data.subarray(pos, pos + lenLen);
          if (lengthBytes.length !== lenLen)
            throw new E("tlv.decode: length bytes not complete");
          if (lengthBytes[0] === 0)
            throw new E("tlv.decode(long): zero leftmost byte");
          for (const b of lengthBytes)
            length = length << 8 | b;
          pos += lenLen;
          if (length < 128)
            throw new E("tlv.decode(long): not minimal encoding");
        }
        const v = data.subarray(pos, pos + length);
        if (v.length !== length)
          throw new E("tlv.decode: wrong value length");
        return { v, l: data.subarray(pos + length) };
      }
    },
    _int: {
      encode(num2) {
        const { Err: E } = DER;
        if (num2 < _0n4)
          throw new E("integer: negative integers are not allowed");
        let hex2 = numberToHexUnpadded(num2);
        if (Number.parseInt(hex2[0], 16) & 8)
          hex2 = "00" + hex2;
        if (hex2.length & 1)
          throw new E("unexpected DER parsing assertion: unpadded hex");
        return hex2;
      },
      decode(data) {
        const { Err: E } = DER;
        if (data[0] & 128)
          throw new E("invalid signature integer: negative");
        if (data[0] === 0 && !(data[1] & 128))
          throw new E("invalid signature integer: unnecessary leading zero");
        return bytesToNumberBE(data);
      }
    },
    toSig(bytes) {
      const { Err: E, _int: int, _tlv: tlv } = DER;
      const data = abytes(bytes, void 0, "signature");
      const { v: seqBytes, l: seqLeftBytes } = tlv.decode(48, data);
      if (seqLeftBytes.length)
        throw new E("invalid signature: left bytes after parsing");
      const { v: rBytes, l: rLeftBytes } = tlv.decode(2, seqBytes);
      const { v: sBytes, l: sLeftBytes } = tlv.decode(2, rLeftBytes);
      if (sLeftBytes.length)
        throw new E("invalid signature: left bytes after parsing");
      return { r: int.decode(rBytes), s: int.decode(sBytes) };
    },
    hexFromSig(sig) {
      const { _tlv: tlv, _int: int } = DER;
      const rs = tlv.encode(2, int.encode(sig.r));
      const ss = tlv.encode(2, int.encode(sig.s));
      const seq = rs + ss;
      return tlv.encode(48, seq);
    }
  };
  var _0n4 = BigInt(0);
  var _1n4 = BigInt(1);
  var _2n2 = BigInt(2);
  var _3n2 = BigInt(3);
  var _4n2 = BigInt(4);
  function weierstrass(params, extraOpts = {}) {
    const validated = createCurveFields("weierstrass", params, extraOpts);
    const { Fp, Fn } = validated;
    let CURVE = validated.CURVE;
    const { h: cofactor, n: CURVE_ORDER } = CURVE;
    validateObject(extraOpts, {}, {
      allowInfinityPoint: "boolean",
      clearCofactor: "function",
      isTorsionFree: "function",
      fromBytes: "function",
      toBytes: "function",
      endo: "object"
    });
    const { endo } = extraOpts;
    if (endo) {
      if (!Fp.is0(CURVE.a) || typeof endo.beta !== "bigint" || !Array.isArray(endo.basises)) {
        throw new Error('invalid endo: expected "beta": bigint and "basises": array');
      }
    }
    const lengths = getWLengths(Fp, Fn);
    function assertCompressionIsSupported() {
      if (!Fp.isOdd)
        throw new Error("compression is not supported: Field does not have .isOdd()");
    }
    function pointToBytes2(_c, point, isCompressed) {
      const { x, y } = point.toAffine();
      const bx = Fp.toBytes(x);
      abool(isCompressed, "isCompressed");
      if (isCompressed) {
        assertCompressionIsSupported();
        const hasEvenY = !Fp.isOdd(y);
        return concatBytes(pprefix(hasEvenY), bx);
      } else {
        return concatBytes(Uint8Array.of(4), bx, Fp.toBytes(y));
      }
    }
    function pointFromBytes(bytes) {
      abytes(bytes, void 0, "Point");
      const { publicKey: comp, publicKeyUncompressed: uncomp } = lengths;
      const length = bytes.length;
      const head = bytes[0];
      const tail = bytes.subarray(1);
      if (length === comp && (head === 2 || head === 3)) {
        const x = Fp.fromBytes(tail);
        if (!Fp.isValid(x))
          throw new Error("bad point: is not on curve, wrong x");
        const y2 = weierstrassEquation(x);
        let y;
        try {
          y = Fp.sqrt(y2);
        } catch (sqrtError) {
          const err = sqrtError instanceof Error ? ": " + sqrtError.message : "";
          throw new Error("bad point: is not on curve, sqrt error" + err);
        }
        assertCompressionIsSupported();
        const evenY = Fp.isOdd(y);
        const evenH = (head & 1) === 1;
        if (evenH !== evenY)
          y = Fp.neg(y);
        return { x, y };
      } else if (length === uncomp && head === 4) {
        const L = Fp.BYTES;
        const x = Fp.fromBytes(tail.subarray(0, L));
        const y = Fp.fromBytes(tail.subarray(L, L * 2));
        if (!isValidXY(x, y))
          throw new Error("bad point: is not on curve");
        return { x, y };
      } else {
        throw new Error(`bad point: got length ${length}, expected compressed=${comp} or uncompressed=${uncomp}`);
      }
    }
    const encodePoint = extraOpts.toBytes || pointToBytes2;
    const decodePoint = extraOpts.fromBytes || pointFromBytes;
    function weierstrassEquation(x) {
      const x2 = Fp.sqr(x);
      const x3 = Fp.mul(x2, x);
      return Fp.add(Fp.add(x3, Fp.mul(x, CURVE.a)), CURVE.b);
    }
    function isValidXY(x, y) {
      const left = Fp.sqr(y);
      const right = weierstrassEquation(x);
      return Fp.eql(left, right);
    }
    if (!isValidXY(CURVE.Gx, CURVE.Gy))
      throw new Error("bad curve params: generator point");
    const _4a3 = Fp.mul(Fp.pow(CURVE.a, _3n2), _4n2);
    const _27b2 = Fp.mul(Fp.sqr(CURVE.b), BigInt(27));
    if (Fp.is0(Fp.add(_4a3, _27b2)))
      throw new Error("bad curve params: a or b");
    function acoord(title, n, banZero = false) {
      if (!Fp.isValid(n) || banZero && Fp.is0(n))
        throw new Error(`bad point coordinate ${title}`);
      return n;
    }
    function aprjpoint(other) {
      if (!(other instanceof Point))
        throw new Error("Weierstrass Point expected");
    }
    function splitEndoScalarN(k) {
      if (!endo || !endo.basises)
        throw new Error("no endo");
      return _splitEndoScalar(k, endo.basises, Fn.ORDER);
    }
    const toAffineMemo = memoized((p, iz) => {
      const { X, Y, Z } = p;
      if (Fp.eql(Z, Fp.ONE))
        return { x: X, y: Y };
      const is0 = p.is0();
      if (iz == null)
        iz = is0 ? Fp.ONE : Fp.inv(Z);
      const x = Fp.mul(X, iz);
      const y = Fp.mul(Y, iz);
      const zz = Fp.mul(Z, iz);
      if (is0)
        return { x: Fp.ZERO, y: Fp.ZERO };
      if (!Fp.eql(zz, Fp.ONE))
        throw new Error("invZ was invalid");
      return { x, y };
    });
    const assertValidMemo = memoized((p) => {
      if (p.is0()) {
        if (extraOpts.allowInfinityPoint && !Fp.is0(p.Y))
          return;
        throw new Error("bad point: ZERO");
      }
      const { x, y } = p.toAffine();
      if (!Fp.isValid(x) || !Fp.isValid(y))
        throw new Error("bad point: x or y not field elements");
      if (!isValidXY(x, y))
        throw new Error("bad point: equation left != right");
      if (!p.isTorsionFree())
        throw new Error("bad point: not in prime-order subgroup");
      return true;
    });
    function finishEndo(endoBeta, k1p, k2p, k1neg, k2neg) {
      k2p = new Point(Fp.mul(k2p.X, endoBeta), k2p.Y, k2p.Z);
      k1p = negateCt(k1neg, k1p);
      k2p = negateCt(k2neg, k2p);
      return k1p.add(k2p);
    }
    class Point {
      static BASE = new Point(CURVE.Gx, CURVE.Gy, Fp.ONE);
      static ZERO = new Point(Fp.ZERO, Fp.ONE, Fp.ZERO);
      static Fp = Fp;
      static Fn = Fn;
      X;
      Y;
      Z;
      constructor(X, Y, Z) {
        this.X = acoord("x", X);
        this.Y = acoord("y", Y, true);
        this.Z = acoord("z", Z);
        Object.freeze(this);
      }
      static CURVE() {
        return CURVE;
      }
      static fromAffine(p) {
        const { x, y } = p || {};
        if (!p || !Fp.isValid(x) || !Fp.isValid(y))
          throw new Error("invalid affine point");
        if (p instanceof Point)
          throw new Error("projective point not allowed");
        if (Fp.is0(x) && Fp.is0(y))
          return Point.ZERO;
        return new Point(x, y, Fp.ONE);
      }
      static fromBytes(bytes) {
        const P = Point.fromAffine(decodePoint(abytes(bytes, void 0, "point")));
        P.assertValidity();
        return P;
      }
      static fromHex(hex2) {
        return Point.fromBytes(hexToBytes(hex2));
      }
      get x() {
        return this.toAffine().x;
      }
      get y() {
        return this.toAffine().y;
      }
      precompute(windowSize = 8, isLazy = true) {
        wnaf.createCache(this, windowSize);
        if (!isLazy)
          this.multiply(_3n2);
        return this;
      }
      assertValidity() {
        assertValidMemo(this);
      }
      hasEvenY() {
        const { y } = this.toAffine();
        if (!Fp.isOdd)
          throw new Error("Field doesn't support isOdd");
        return !Fp.isOdd(y);
      }
      equals(other) {
        aprjpoint(other);
        const { X: X1, Y: Y1, Z: Z1 } = this;
        const { X: X2, Y: Y2, Z: Z2 } = other;
        const U1 = Fp.eql(Fp.mul(X1, Z2), Fp.mul(X2, Z1));
        const U2 = Fp.eql(Fp.mul(Y1, Z2), Fp.mul(Y2, Z1));
        return U1 && U2;
      }
      negate() {
        return new Point(this.X, Fp.neg(this.Y), this.Z);
      }
      double() {
        const { a, b } = CURVE;
        const b3 = Fp.mul(b, _3n2);
        const { X: X1, Y: Y1, Z: Z1 } = this;
        let X3 = Fp.ZERO, Y3 = Fp.ZERO, Z3 = Fp.ZERO;
        let t0 = Fp.mul(X1, X1);
        let t1 = Fp.mul(Y1, Y1);
        let t2 = Fp.mul(Z1, Z1);
        let t3 = Fp.mul(X1, Y1);
        t3 = Fp.add(t3, t3);
        Z3 = Fp.mul(X1, Z1);
        Z3 = Fp.add(Z3, Z3);
        X3 = Fp.mul(a, Z3);
        Y3 = Fp.mul(b3, t2);
        Y3 = Fp.add(X3, Y3);
        X3 = Fp.sub(t1, Y3);
        Y3 = Fp.add(t1, Y3);
        Y3 = Fp.mul(X3, Y3);
        X3 = Fp.mul(t3, X3);
        Z3 = Fp.mul(b3, Z3);
        t2 = Fp.mul(a, t2);
        t3 = Fp.sub(t0, t2);
        t3 = Fp.mul(a, t3);
        t3 = Fp.add(t3, Z3);
        Z3 = Fp.add(t0, t0);
        t0 = Fp.add(Z3, t0);
        t0 = Fp.add(t0, t2);
        t0 = Fp.mul(t0, t3);
        Y3 = Fp.add(Y3, t0);
        t2 = Fp.mul(Y1, Z1);
        t2 = Fp.add(t2, t2);
        t0 = Fp.mul(t2, t3);
        X3 = Fp.sub(X3, t0);
        Z3 = Fp.mul(t2, t1);
        Z3 = Fp.add(Z3, Z3);
        Z3 = Fp.add(Z3, Z3);
        return new Point(X3, Y3, Z3);
      }
      add(other) {
        aprjpoint(other);
        const { X: X1, Y: Y1, Z: Z1 } = this;
        const { X: X2, Y: Y2, Z: Z2 } = other;
        let X3 = Fp.ZERO, Y3 = Fp.ZERO, Z3 = Fp.ZERO;
        const a = CURVE.a;
        const b3 = Fp.mul(CURVE.b, _3n2);
        let t0 = Fp.mul(X1, X2);
        let t1 = Fp.mul(Y1, Y2);
        let t2 = Fp.mul(Z1, Z2);
        let t3 = Fp.add(X1, Y1);
        let t4 = Fp.add(X2, Y2);
        t3 = Fp.mul(t3, t4);
        t4 = Fp.add(t0, t1);
        t3 = Fp.sub(t3, t4);
        t4 = Fp.add(X1, Z1);
        let t5 = Fp.add(X2, Z2);
        t4 = Fp.mul(t4, t5);
        t5 = Fp.add(t0, t2);
        t4 = Fp.sub(t4, t5);
        t5 = Fp.add(Y1, Z1);
        X3 = Fp.add(Y2, Z2);
        t5 = Fp.mul(t5, X3);
        X3 = Fp.add(t1, t2);
        t5 = Fp.sub(t5, X3);
        Z3 = Fp.mul(a, t4);
        X3 = Fp.mul(b3, t2);
        Z3 = Fp.add(X3, Z3);
        X3 = Fp.sub(t1, Z3);
        Z3 = Fp.add(t1, Z3);
        Y3 = Fp.mul(X3, Z3);
        t1 = Fp.add(t0, t0);
        t1 = Fp.add(t1, t0);
        t2 = Fp.mul(a, t2);
        t4 = Fp.mul(b3, t4);
        t1 = Fp.add(t1, t2);
        t2 = Fp.sub(t0, t2);
        t2 = Fp.mul(a, t2);
        t4 = Fp.add(t4, t2);
        t0 = Fp.mul(t1, t4);
        Y3 = Fp.add(Y3, t0);
        t0 = Fp.mul(t5, t4);
        X3 = Fp.mul(t3, X3);
        X3 = Fp.sub(X3, t0);
        t0 = Fp.mul(t3, t1);
        Z3 = Fp.mul(t5, Z3);
        Z3 = Fp.add(Z3, t0);
        return new Point(X3, Y3, Z3);
      }
      subtract(other) {
        return this.add(other.negate());
      }
      is0() {
        return this.equals(Point.ZERO);
      }
      multiply(scalar) {
        const { endo: endo2 } = extraOpts;
        if (!Fn.isValidNot0(scalar))
          throw new Error("invalid scalar: out of range");
        let point, fake;
        const mul3 = (n) => wnaf.cached(this, n, (p) => normalizeZ(Point, p));
        if (endo2) {
          const { k1neg, k1, k2neg, k2 } = splitEndoScalarN(scalar);
          const { p: k1p, f: k1f } = mul3(k1);
          const { p: k2p, f: k2f } = mul3(k2);
          fake = k1f.add(k2f);
          point = finishEndo(endo2.beta, k1p, k2p, k1neg, k2neg);
        } else {
          const { p, f } = mul3(scalar);
          point = p;
          fake = f;
        }
        return normalizeZ(Point, [point, fake])[0];
      }
      multiplyUnsafe(sc) {
        const { endo: endo2 } = extraOpts;
        const p = this;
        if (!Fn.isValid(sc))
          throw new Error("invalid scalar: out of range");
        if (sc === _0n4 || p.is0())
          return Point.ZERO;
        if (sc === _1n4)
          return p;
        if (wnaf.hasCache(this))
          return this.multiply(sc);
        if (endo2) {
          const { k1neg, k1, k2neg, k2 } = splitEndoScalarN(sc);
          const { p1, p2 } = mulEndoUnsafe(Point, p, k1, k2);
          return finishEndo(endo2.beta, p1, p2, k1neg, k2neg);
        } else {
          return wnaf.unsafe(p, sc);
        }
      }
      toAffine(invertedZ) {
        return toAffineMemo(this, invertedZ);
      }
      isTorsionFree() {
        const { isTorsionFree } = extraOpts;
        if (cofactor === _1n4)
          return true;
        if (isTorsionFree)
          return isTorsionFree(Point, this);
        return wnaf.unsafe(this, CURVE_ORDER).is0();
      }
      clearCofactor() {
        const { clearCofactor } = extraOpts;
        if (cofactor === _1n4)
          return this;
        if (clearCofactor)
          return clearCofactor(Point, this);
        return this.multiplyUnsafe(cofactor);
      }
      isSmallOrder() {
        return this.multiplyUnsafe(cofactor).is0();
      }
      toBytes(isCompressed = true) {
        abool(isCompressed, "isCompressed");
        this.assertValidity();
        return encodePoint(Point, this, isCompressed);
      }
      toHex(isCompressed = true) {
        return bytesToHex(this.toBytes(isCompressed));
      }
      toString() {
        return `<Point ${this.is0() ? "ZERO" : this.toHex()}>`;
      }
    }
    const bits = Fn.BITS;
    const wnaf = new wNAF(Point, extraOpts.endo ? Math.ceil(bits / 2) : bits);
    Point.BASE.precompute(8);
    return Point;
  }
  function pprefix(hasEvenY) {
    return Uint8Array.of(hasEvenY ? 2 : 3);
  }
  function getWLengths(Fp, Fn) {
    return {
      secretKey: Fn.BYTES,
      publicKey: 1 + Fp.BYTES,
      publicKeyUncompressed: 1 + 2 * Fp.BYTES,
      publicKeyHasPrefix: true,
      signature: 2 * Fn.BYTES
    };
  }
  function ecdh(Point, ecdhOpts = {}) {
    const { Fn } = Point;
    const randomBytes_ = ecdhOpts.randomBytes || randomBytes;
    const lengths = Object.assign(getWLengths(Point.Fp, Fn), { seed: getMinHashLength(Fn.ORDER) });
    function isValidSecretKey(secretKey) {
      try {
        const num2 = Fn.fromBytes(secretKey);
        return Fn.isValidNot0(num2);
      } catch (error) {
        return false;
      }
    }
    function isValidPublicKey(publicKey, isCompressed) {
      const { publicKey: comp, publicKeyUncompressed } = lengths;
      try {
        const l = publicKey.length;
        if (isCompressed === true && l !== comp)
          return false;
        if (isCompressed === false && l !== publicKeyUncompressed)
          return false;
        return !!Point.fromBytes(publicKey);
      } catch (error) {
        return false;
      }
    }
    function randomSecretKey(seed = randomBytes_(lengths.seed)) {
      return mapHashToField(abytes(seed, lengths.seed, "seed"), Fn.ORDER);
    }
    function getPublicKey2(secretKey, isCompressed = true) {
      return Point.BASE.multiply(Fn.fromBytes(secretKey)).toBytes(isCompressed);
    }
    function isProbPub(item) {
      const { secretKey, publicKey, publicKeyUncompressed } = lengths;
      if (!isBytes(item))
        return void 0;
      if ("_lengths" in Fn && Fn._lengths || secretKey === publicKey)
        return void 0;
      const l = abytes(item, void 0, "key").length;
      return l === publicKey || l === publicKeyUncompressed;
    }
    function getSharedSecret(secretKeyA, publicKeyB, isCompressed = true) {
      if (isProbPub(secretKeyA) === true)
        throw new Error("first arg must be private key");
      if (isProbPub(publicKeyB) === false)
        throw new Error("second arg must be public key");
      const s = Fn.fromBytes(secretKeyA);
      const b = Point.fromBytes(publicKeyB);
      return b.multiply(s).toBytes(isCompressed);
    }
    const utils = {
      isValidSecretKey,
      isValidPublicKey,
      randomSecretKey
    };
    const keygen = createKeygen(randomSecretKey, getPublicKey2);
    return Object.freeze({ getPublicKey: getPublicKey2, getSharedSecret, keygen, Point, utils, lengths });
  }
  function ecdsa(Point, hash, ecdsaOpts = {}) {
    ahash(hash);
    validateObject(ecdsaOpts, {}, {
      hmac: "function",
      lowS: "boolean",
      randomBytes: "function",
      bits2int: "function",
      bits2int_modN: "function"
    });
    ecdsaOpts = Object.assign({}, ecdsaOpts);
    const randomBytes3 = ecdsaOpts.randomBytes || randomBytes;
    const hmac2 = ecdsaOpts.hmac || ((key, msg) => hmac(hash, key, msg));
    const { Fp, Fn } = Point;
    const { ORDER: CURVE_ORDER, BITS: fnBits } = Fn;
    const { keygen, getPublicKey: getPublicKey2, getSharedSecret, utils, lengths } = ecdh(Point, ecdsaOpts);
    const defaultSigOpts = {
      prehash: true,
      lowS: typeof ecdsaOpts.lowS === "boolean" ? ecdsaOpts.lowS : true,
      format: "compact",
      extraEntropy: false
    };
    const hasLargeCofactor = CURVE_ORDER * _2n2 < Fp.ORDER;
    function isBiggerThanHalfOrder(number) {
      const HALF = CURVE_ORDER >> _1n4;
      return number > HALF;
    }
    function validateRS(title, num2) {
      if (!Fn.isValidNot0(num2))
        throw new Error(`invalid signature ${title}: out of range 1..Point.Fn.ORDER`);
      return num2;
    }
    function assertSmallCofactor() {
      if (hasLargeCofactor)
        throw new Error('"recovered" sig type is not supported for cofactor >2 curves');
    }
    function validateSigLength(bytes, format) {
      validateSigFormat(format);
      const size = lengths.signature;
      const sizer = format === "compact" ? size : format === "recovered" ? size + 1 : void 0;
      return abytes(bytes, sizer);
    }
    class Signature {
      r;
      s;
      recovery;
      constructor(r, s, recovery) {
        this.r = validateRS("r", r);
        this.s = validateRS("s", s);
        if (recovery != null) {
          assertSmallCofactor();
          if (![0, 1, 2, 3].includes(recovery))
            throw new Error("invalid recovery id");
          this.recovery = recovery;
        }
        Object.freeze(this);
      }
      static fromBytes(bytes, format = defaultSigOpts.format) {
        validateSigLength(bytes, format);
        let recid;
        if (format === "der") {
          const { r: r2, s: s2 } = DER.toSig(abytes(bytes));
          return new Signature(r2, s2);
        }
        if (format === "recovered") {
          recid = bytes[0];
          format = "compact";
          bytes = bytes.subarray(1);
        }
        const L = lengths.signature / 2;
        const r = bytes.subarray(0, L);
        const s = bytes.subarray(L, L * 2);
        return new Signature(Fn.fromBytes(r), Fn.fromBytes(s), recid);
      }
      static fromHex(hex2, format) {
        return this.fromBytes(hexToBytes(hex2), format);
      }
      assertRecovery() {
        const { recovery } = this;
        if (recovery == null)
          throw new Error("invalid recovery id: must be present");
        return recovery;
      }
      addRecoveryBit(recovery) {
        return new Signature(this.r, this.s, recovery);
      }
      recoverPublicKey(messageHash) {
        const { r, s } = this;
        const recovery = this.assertRecovery();
        const radj = recovery === 2 || recovery === 3 ? r + CURVE_ORDER : r;
        if (!Fp.isValid(radj))
          throw new Error("invalid recovery id: sig.r+curve.n != R.x");
        const x = Fp.toBytes(radj);
        const R = Point.fromBytes(concatBytes(pprefix((recovery & 1) === 0), x));
        const ir = Fn.inv(radj);
        const h = bits2int_modN(abytes(messageHash, void 0, "msgHash"));
        const u1 = Fn.create(-h * ir);
        const u2 = Fn.create(s * ir);
        const Q = Point.BASE.multiplyUnsafe(u1).add(R.multiplyUnsafe(u2));
        if (Q.is0())
          throw new Error("invalid recovery: point at infinify");
        Q.assertValidity();
        return Q;
      }
      hasHighS() {
        return isBiggerThanHalfOrder(this.s);
      }
      toBytes(format = defaultSigOpts.format) {
        validateSigFormat(format);
        if (format === "der")
          return hexToBytes(DER.hexFromSig(this));
        const { r, s } = this;
        const rb = Fn.toBytes(r);
        const sb = Fn.toBytes(s);
        if (format === "recovered") {
          assertSmallCofactor();
          return concatBytes(Uint8Array.of(this.assertRecovery()), rb, sb);
        }
        return concatBytes(rb, sb);
      }
      toHex(format) {
        return bytesToHex(this.toBytes(format));
      }
    }
    const bits2int = ecdsaOpts.bits2int || function bits2int_def(bytes) {
      if (bytes.length > 8192)
        throw new Error("input is too large");
      const num2 = bytesToNumberBE(bytes);
      const delta = bytes.length * 8 - fnBits;
      return delta > 0 ? num2 >> BigInt(delta) : num2;
    };
    const bits2int_modN = ecdsaOpts.bits2int_modN || function bits2int_modN_def(bytes) {
      return Fn.create(bits2int(bytes));
    };
    const ORDER_MASK = bitMask(fnBits);
    function int2octets(num2) {
      aInRange("num < 2^" + fnBits, num2, _0n4, ORDER_MASK);
      return Fn.toBytes(num2);
    }
    function validateMsgAndHash(message, prehash) {
      abytes(message, void 0, "message");
      return prehash ? abytes(hash(message), void 0, "prehashed message") : message;
    }
    function prepSig(message, secretKey, opts) {
      const { lowS, prehash, extraEntropy } = validateSigOpts(opts, defaultSigOpts);
      message = validateMsgAndHash(message, prehash);
      const h1int = bits2int_modN(message);
      const d = Fn.fromBytes(secretKey);
      if (!Fn.isValidNot0(d))
        throw new Error("invalid private key");
      const seedArgs = [int2octets(d), int2octets(h1int)];
      if (extraEntropy != null && extraEntropy !== false) {
        const e = extraEntropy === true ? randomBytes3(lengths.secretKey) : extraEntropy;
        seedArgs.push(abytes(e, void 0, "extraEntropy"));
      }
      const seed = concatBytes(...seedArgs);
      const m = h1int;
      function k2sig(kBytes) {
        const k = bits2int(kBytes);
        if (!Fn.isValidNot0(k))
          return;
        const ik = Fn.inv(k);
        const q = Point.BASE.multiply(k).toAffine();
        const r = Fn.create(q.x);
        if (r === _0n4)
          return;
        const s = Fn.create(ik * Fn.create(m + r * d));
        if (s === _0n4)
          return;
        let recovery = (q.x === r ? 0 : 2) | Number(q.y & _1n4);
        let normS = s;
        if (lowS && isBiggerThanHalfOrder(s)) {
          normS = Fn.neg(s);
          recovery ^= 1;
        }
        return new Signature(r, normS, hasLargeCofactor ? void 0 : recovery);
      }
      return { seed, k2sig };
    }
    function sign(message, secretKey, opts = {}) {
      const { seed, k2sig } = prepSig(message, secretKey, opts);
      const drbg = createHmacDrbg(hash.outputLen, Fn.BYTES, hmac2);
      const sig = drbg(seed, k2sig);
      return sig.toBytes(opts.format);
    }
    function verify(signature, message, publicKey, opts = {}) {
      const { lowS, prehash, format } = validateSigOpts(opts, defaultSigOpts);
      publicKey = abytes(publicKey, void 0, "publicKey");
      message = validateMsgAndHash(message, prehash);
      if (!isBytes(signature)) {
        const end = signature instanceof Signature ? ", use sig.toBytes()" : "";
        throw new Error("verify expects Uint8Array signature" + end);
      }
      validateSigLength(signature, format);
      try {
        const sig = Signature.fromBytes(signature, format);
        const P = Point.fromBytes(publicKey);
        if (lowS && sig.hasHighS())
          return false;
        const { r, s } = sig;
        const h = bits2int_modN(message);
        const is = Fn.inv(s);
        const u1 = Fn.create(h * is);
        const u2 = Fn.create(r * is);
        const R = Point.BASE.multiplyUnsafe(u1).add(P.multiplyUnsafe(u2));
        if (R.is0())
          return false;
        const v = Fn.create(R.x);
        return v === r;
      } catch (e) {
        return false;
      }
    }
    function recoverPublicKey(signature, message, opts = {}) {
      const { prehash } = validateSigOpts(opts, defaultSigOpts);
      message = validateMsgAndHash(message, prehash);
      return Signature.fromBytes(signature, "recovered").recoverPublicKey(message).toBytes();
    }
    return Object.freeze({
      keygen,
      getPublicKey: getPublicKey2,
      getSharedSecret,
      utils,
      lengths,
      Point,
      sign,
      verify,
      recoverPublicKey,
      Signature,
      hash
    });
  }

  // node_modules/@noble/curves/secp256k1.js
  var secp256k1_CURVE = {
    p: BigInt("0xfffffffffffffffffffffffffffffffffffffffffffffffffffffffefffffc2f"),
    n: BigInt("0xfffffffffffffffffffffffffffffffebaaedce6af48a03bbfd25e8cd0364141"),
    h: BigInt(1),
    a: BigInt(0),
    b: BigInt(7),
    Gx: BigInt("0x79be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798"),
    Gy: BigInt("0x483ada7726a3c4655da4fbfc0e1108a8fd17b448a68554199c47d08ffb10d4b8")
  };
  var secp256k1_ENDO = {
    beta: BigInt("0x7ae96a2b657c07106e64479eac3434e99cf0497512f58995c1396c28719501ee"),
    basises: [
      [BigInt("0x3086d221a7d46bcde86c90e49284eb15"), -BigInt("0xe4437ed6010e88286f547fa90abfe4c3")],
      [BigInt("0x114ca50f7a8e2f3f657c1108d9d44cfd8"), BigInt("0x3086d221a7d46bcde86c90e49284eb15")]
    ]
  };
  var _0n5 = /* @__PURE__ */ BigInt(0);
  var _2n3 = /* @__PURE__ */ BigInt(2);
  function sqrtMod(y) {
    const P = secp256k1_CURVE.p;
    const _3n3 = BigInt(3), _6n = BigInt(6), _11n = BigInt(11), _22n = BigInt(22);
    const _23n = BigInt(23), _44n = BigInt(44), _88n = BigInt(88);
    const b2 = y * y * y % P;
    const b3 = b2 * b2 * y % P;
    const b6 = pow2(b3, _3n3, P) * b3 % P;
    const b9 = pow2(b6, _3n3, P) * b3 % P;
    const b11 = pow2(b9, _2n3, P) * b2 % P;
    const b22 = pow2(b11, _11n, P) * b11 % P;
    const b44 = pow2(b22, _22n, P) * b22 % P;
    const b88 = pow2(b44, _44n, P) * b44 % P;
    const b176 = pow2(b88, _88n, P) * b88 % P;
    const b220 = pow2(b176, _44n, P) * b44 % P;
    const b223 = pow2(b220, _3n3, P) * b3 % P;
    const t1 = pow2(b223, _23n, P) * b22 % P;
    const t2 = pow2(t1, _6n, P) * b2 % P;
    const root = pow2(t2, _2n3, P);
    if (!Fpk1.eql(Fpk1.sqr(root), y))
      throw new Error("Cannot find square root");
    return root;
  }
  var Fpk1 = Field(secp256k1_CURVE.p, { sqrt: sqrtMod });
  var Pointk1 = /* @__PURE__ */ weierstrass(secp256k1_CURVE, {
    Fp: Fpk1,
    endo: secp256k1_ENDO
  });
  var secp256k1 = /* @__PURE__ */ ecdsa(Pointk1, sha256);
  var TAGGED_HASH_PREFIXES = {};
  function taggedHash(tag, ...messages) {
    let tagP = TAGGED_HASH_PREFIXES[tag];
    if (tagP === void 0) {
      const tagH = sha256(asciiToBytes(tag));
      tagP = concatBytes(tagH, tagH);
      TAGGED_HASH_PREFIXES[tag] = tagP;
    }
    return sha256(concatBytes(tagP, ...messages));
  }
  var pointToBytes = (point) => point.toBytes(true).slice(1);
  var hasEven = (y) => y % _2n3 === _0n5;
  function schnorrGetExtPubKey(priv) {
    const { Fn, BASE } = Pointk1;
    const d_ = Fn.fromBytes(priv);
    const p = BASE.multiply(d_);
    const scalar = hasEven(p.y) ? d_ : Fn.neg(d_);
    return { scalar, bytes: pointToBytes(p) };
  }
  function lift_x(x) {
    const Fp = Fpk1;
    if (!Fp.isValidNot0(x))
      throw new Error("invalid x: Fail if x \u2265 p");
    const xx = Fp.create(x * x);
    const c = Fp.create(xx * x + BigInt(7));
    let y = Fp.sqrt(c);
    if (!hasEven(y))
      y = Fp.neg(y);
    const p = Pointk1.fromAffine({ x, y });
    p.assertValidity();
    return p;
  }
  var num = bytesToNumberBE;
  function challenge(...args) {
    return Pointk1.Fn.create(num(taggedHash("BIP0340/challenge", ...args)));
  }
  function schnorrGetPublicKey(secretKey) {
    return schnorrGetExtPubKey(secretKey).bytes;
  }
  function schnorrSign(message, secretKey, auxRand = randomBytes(32)) {
    const { Fn } = Pointk1;
    const m = abytes(message, void 0, "message");
    const { bytes: px, scalar: d } = schnorrGetExtPubKey(secretKey);
    const a = abytes(auxRand, 32, "auxRand");
    const t = Fn.toBytes(d ^ num(taggedHash("BIP0340/aux", a)));
    const rand = taggedHash("BIP0340/nonce", t, px, m);
    const { bytes: rx, scalar: k } = schnorrGetExtPubKey(rand);
    const e = challenge(rx, px, m);
    const sig = new Uint8Array(64);
    sig.set(rx, 0);
    sig.set(Fn.toBytes(Fn.create(k + e * d)), 32);
    if (!schnorrVerify(sig, m, px))
      throw new Error("sign: Invalid signature produced");
    return sig;
  }
  function schnorrVerify(signature, message, publicKey) {
    const { Fp, Fn, BASE } = Pointk1;
    const sig = abytes(signature, 64, "signature");
    const m = abytes(message, void 0, "message");
    const pub = abytes(publicKey, 32, "publicKey");
    try {
      const P = lift_x(num(pub));
      const r = num(sig.subarray(0, 32));
      if (!Fp.isValidNot0(r))
        return false;
      const s = num(sig.subarray(32, 64));
      if (!Fn.isValidNot0(s))
        return false;
      const e = challenge(Fn.toBytes(r), pointToBytes(P), m);
      const R = BASE.multiplyUnsafe(s).add(P.multiplyUnsafe(Fn.neg(e)));
      const { x, y } = R.toAffine();
      if (R.is0() || !hasEven(y) || x !== r)
        return false;
      return true;
    } catch (error) {
      return false;
    }
  }
  var schnorr = /* @__PURE__ */ (() => {
    const size = 32;
    const seedLength = 48;
    const randomSecretKey = (seed = randomBytes(seedLength)) => {
      return mapHashToField(seed, secp256k1_CURVE.n);
    };
    return {
      keygen: createKeygen(randomSecretKey, schnorrGetPublicKey),
      getPublicKey: schnorrGetPublicKey,
      sign: schnorrSign,
      verify: schnorrVerify,
      Point: Pointk1,
      utils: {
        randomSecretKey,
        taggedHash,
        lift_x,
        pointToBytes
      },
      lengths: {
        secretKey: size,
        publicKey: size,
        publicKeyHasPrefix: false,
        signature: size * 2,
        seed: seedLength
      }
    };
  })();

  // core.ts
  var verifiedSymbol = Symbol("verified");
  var isRecord = (obj) => obj instanceof Object;
  function validateEvent(event) {
    if (!isRecord(event))
      return false;
    if (typeof event.kind !== "number")
      return false;
    if (typeof event.content !== "string")
      return false;
    if (typeof event.created_at !== "number")
      return false;
    if (typeof event.pubkey !== "string")
      return false;
    if (!event.pubkey.match(/^[a-f0-9]{64}$/))
      return false;
    if (!Array.isArray(event.tags))
      return false;
    for (let i2 = 0; i2 < event.tags.length; i2++) {
      let tag = event.tags[i2];
      if (!Array.isArray(tag))
        return false;
      for (let j = 0; j < tag.length; j++) {
        if (typeof tag[j] !== "string")
          return false;
      }
    }
    return true;
  }
  function sortEvents(events) {
    return events.sort((a, b) => {
      if (a.created_at !== b.created_at) {
        return b.created_at - a.created_at;
      }
      return a.id.localeCompare(b.id);
    });
  }

  // utils.ts
  var utils_exports = {};
  __export(utils_exports, {
    binarySearch: () => binarySearch,
    bytesToHex: () => bytesToHex,
    hexToBytes: () => hexToBytes,
    insertEventIntoAscendingList: () => insertEventIntoAscendingList,
    insertEventIntoDescendingList: () => insertEventIntoDescendingList,
    mergeReverseSortedLists: () => mergeReverseSortedLists,
    normalizeURL: () => normalizeURL,
    utf8Decoder: () => utf8Decoder,
    utf8Encoder: () => utf8Encoder
  });
  var utf8Decoder = new TextDecoder("utf-8");
  var utf8Encoder = new TextEncoder();
  function normalizeURL(url) {
    try {
      if (url.indexOf("://") === -1)
        url = "wss://" + url;
      let p = new URL(url);
      if (p.protocol === "http:")
        p.protocol = "ws:";
      else if (p.protocol === "https:")
        p.protocol = "wss:";
      p.pathname = p.pathname.replace(/\/+/g, "/");
      if (p.pathname.endsWith("/"))
        p.pathname = p.pathname.slice(0, -1);
      if (p.port === "80" && p.protocol === "ws:" || p.port === "443" && p.protocol === "wss:")
        p.port = "";
      p.searchParams.sort();
      p.hash = "";
      return p.toString();
    } catch (e) {
      throw new Error(`Invalid URL: ${url}`);
    }
  }
  function insertEventIntoDescendingList(sortedArray, event) {
    const [idx, found] = binarySearch(sortedArray, (b) => {
      if (event.id === b.id)
        return 0;
      if (event.created_at === b.created_at)
        return -1;
      return b.created_at - event.created_at;
    });
    if (!found) {
      sortedArray.splice(idx, 0, event);
    }
    return sortedArray;
  }
  function insertEventIntoAscendingList(sortedArray, event) {
    const [idx, found] = binarySearch(sortedArray, (b) => {
      if (event.id === b.id)
        return 0;
      if (event.created_at === b.created_at)
        return -1;
      return event.created_at - b.created_at;
    });
    if (!found) {
      sortedArray.splice(idx, 0, event);
    }
    return sortedArray;
  }
  function binarySearch(arr, compare) {
    let start = 0;
    let end = arr.length - 1;
    while (start <= end) {
      const mid = Math.floor((start + end) / 2);
      const cmp = compare(arr[mid]);
      if (cmp === 0) {
        return [mid, true];
      }
      if (cmp < 0) {
        end = mid - 1;
      } else {
        start = mid + 1;
      }
    }
    return [start, false];
  }
  function mergeReverseSortedLists(list1, list2) {
    const result = new Array(list1.length + list2.length);
    result.length = 0;
    let i1 = 0;
    let i2 = 0;
    let sameTimestampIds = [];
    while (i1 < list1.length && i2 < list2.length) {
      let next;
      if (list1[i1]?.created_at > list2[i2]?.created_at) {
        next = list1[i1];
        i1++;
      } else {
        next = list2[i2];
        i2++;
      }
      if (result.length > 0 && result[result.length - 1].created_at === next.created_at) {
        if (sameTimestampIds.includes(next.id))
          continue;
      } else {
        sameTimestampIds.length = 0;
      }
      result.push(next);
      sameTimestampIds.push(next.id);
    }
    while (i1 < list1.length) {
      const next = list1[i1];
      i1++;
      if (result.length > 0 && result[result.length - 1].created_at === next.created_at) {
        if (sameTimestampIds.includes(next.id))
          continue;
      } else {
        sameTimestampIds.length = 0;
      }
      result.push(next);
      sameTimestampIds.push(next.id);
    }
    while (i2 < list2.length) {
      const next = list2[i2];
      i2++;
      if (result.length > 0 && result[result.length - 1].created_at === next.created_at) {
        if (sameTimestampIds.includes(next.id))
          continue;
      } else {
        sameTimestampIds.length = 0;
      }
      result.push(next);
      sameTimestampIds.push(next.id);
    }
    return result;
  }

  // pure.ts
  var JS = class {
    generateSecretKey() {
      return schnorr.utils.randomSecretKey();
    }
    getPublicKey(secretKey) {
      return bytesToHex(schnorr.getPublicKey(secretKey));
    }
    finalizeEvent(t, secretKey) {
      const event = t;
      event.pubkey = bytesToHex(schnorr.getPublicKey(secretKey));
      event.id = getEventHash(event);
      event.sig = bytesToHex(schnorr.sign(hexToBytes(getEventHash(event)), secretKey));
      event[verifiedSymbol] = true;
      return event;
    }
    verifyEvent(event) {
      if (typeof event[verifiedSymbol] === "boolean")
        return event[verifiedSymbol];
      try {
        const hash = getEventHash(event);
        if (hash !== event.id) {
          event[verifiedSymbol] = false;
          return false;
        }
        const valid = schnorr.verify(hexToBytes(event.sig), hexToBytes(hash), hexToBytes(event.pubkey));
        event[verifiedSymbol] = valid;
        return valid;
      } catch (err) {
        event[verifiedSymbol] = false;
        return false;
      }
    }
  };
  function serializeEvent(evt) {
    if (!validateEvent(evt))
      throw new Error("can't serialize event with wrong or missing properties");
    return JSON.stringify([0, evt.pubkey, evt.created_at, evt.kind, evt.tags, evt.content]);
  }
  function getEventHash(event) {
    let eventHash = sha256(utf8Encoder.encode(serializeEvent(event)));
    return bytesToHex(eventHash);
  }
  var i = new JS();
  var generateSecretKey = i.generateSecretKey;
  var getPublicKey = i.getPublicKey;
  var finalizeEvent = i.finalizeEvent;
  var verifyEvent = i.verifyEvent;

  // kinds.ts
  var kinds_exports = {};
  __export(kinds_exports, {
    Application: () => Application,
    BadgeAward: () => BadgeAward,
    BadgeDefinition: () => BadgeDefinition,
    BlockedRelaysList: () => BlockedRelaysList,
    BlossomServerList: () => BlossomServerList,
    BookmarkList: () => BookmarkList,
    Bookmarksets: () => Bookmarksets,
    Calendar: () => Calendar,
    CalendarEventRSVP: () => CalendarEventRSVP,
    ChannelCreation: () => ChannelCreation,
    ChannelHideMessage: () => ChannelHideMessage,
    ChannelMessage: () => ChannelMessage,
    ChannelMetadata: () => ChannelMetadata,
    ChannelMuteUser: () => ChannelMuteUser,
    ChatMessage: () => ChatMessage,
    ClassifiedListing: () => ClassifiedListing,
    ClientAuth: () => ClientAuth,
    Comment: () => Comment,
    CommunitiesList: () => CommunitiesList,
    CommunityDefinition: () => CommunityDefinition,
    CommunityPostApproval: () => CommunityPostApproval,
    Contacts: () => Contacts,
    CreateOrUpdateProduct: () => CreateOrUpdateProduct,
    CreateOrUpdateStall: () => CreateOrUpdateStall,
    Curationsets: () => Curationsets,
    Date: () => Date2,
    DirectMessageRelaysList: () => DirectMessageRelaysList,
    DraftClassifiedListing: () => DraftClassifiedListing,
    DraftLong: () => DraftLong,
    Emojisets: () => Emojisets,
    EncryptedDirectMessage: () => EncryptedDirectMessage,
    EventDeletion: () => EventDeletion,
    FavoriteRelays: () => FavoriteRelays,
    FileMessage: () => FileMessage,
    FileMetadata: () => FileMetadata,
    FileServerPreference: () => FileServerPreference,
    Followsets: () => Followsets,
    ForumThread: () => ForumThread,
    GenericRepost: () => GenericRepost,
    Genericlists: () => Genericlists,
    GiftWrap: () => GiftWrap,
    GroupMetadata: () => GroupMetadata,
    HTTPAuth: () => HTTPAuth,
    Handlerinformation: () => Handlerinformation,
    Handlerrecommendation: () => Handlerrecommendation,
    Highlights: () => Highlights,
    InterestsList: () => InterestsList,
    Interestsets: () => Interestsets,
    JobFeedback: () => JobFeedback,
    JobRequest: () => JobRequest,
    JobResult: () => JobResult,
    Label: () => Label,
    LightningPubRPC: () => LightningPubRPC,
    LiveChatMessage: () => LiveChatMessage,
    LiveEvent: () => LiveEvent,
    LongFormArticle: () => LongFormArticle,
    Metadata: () => Metadata,
    Mutelist: () => Mutelist,
    NWCWalletInfo: () => NWCWalletInfo,
    NWCWalletRequest: () => NWCWalletRequest,
    NWCWalletResponse: () => NWCWalletResponse,
    NormalVideo: () => NormalVideo,
    NostrConnect: () => NostrConnect,
    OpenTimestamps: () => OpenTimestamps,
    Photo: () => Photo,
    Pinlist: () => Pinlist,
    Poll: () => Poll,
    PollResponse: () => PollResponse,
    PrivateDirectMessage: () => PrivateDirectMessage,
    ProblemTracker: () => ProblemTracker,
    ProfileBadges: () => ProfileBadges,
    PublicChatsList: () => PublicChatsList,
    Reaction: () => Reaction,
    RecommendRelay: () => RecommendRelay,
    RelayList: () => RelayList,
    RelayReview: () => RelayReview,
    Relaysets: () => Relaysets,
    Report: () => Report,
    Reporting: () => Reporting,
    Repost: () => Repost,
    Seal: () => Seal,
    SearchRelaysList: () => SearchRelaysList,
    ShortTextNote: () => ShortTextNote,
    ShortVideo: () => ShortVideo,
    Time: () => Time,
    UserEmojiList: () => UserEmojiList,
    UserStatuses: () => UserStatuses,
    Voice: () => Voice,
    VoiceComment: () => VoiceComment,
    Zap: () => Zap,
    ZapGoal: () => ZapGoal,
    ZapRequest: () => ZapRequest,
    classifyKind: () => classifyKind,
    isAddressableKind: () => isAddressableKind,
    isEphemeralKind: () => isEphemeralKind,
    isKind: () => isKind,
    isRegularKind: () => isRegularKind,
    isReplaceableKind: () => isReplaceableKind
  });
  function isRegularKind(kind) {
    return kind < 1e4 && kind !== 0 && kind !== 3;
  }
  function isReplaceableKind(kind) {
    return kind === 0 || kind === 3 || 1e4 <= kind && kind < 2e4;
  }
  function isEphemeralKind(kind) {
    return 2e4 <= kind && kind < 3e4;
  }
  function isAddressableKind(kind) {
    return 3e4 <= kind && kind < 4e4;
  }
  function classifyKind(kind) {
    if (isRegularKind(kind))
      return "regular";
    if (isReplaceableKind(kind))
      return "replaceable";
    if (isEphemeralKind(kind))
      return "ephemeral";
    if (isAddressableKind(kind))
      return "parameterized";
    return "unknown";
  }
  function isKind(event, kind) {
    const kindAsArray = kind instanceof Array ? kind : [kind];
    return validateEvent(event) && kindAsArray.includes(event.kind) || false;
  }
  var Metadata = 0;
  var ShortTextNote = 1;
  var RecommendRelay = 2;
  var Contacts = 3;
  var EncryptedDirectMessage = 4;
  var EventDeletion = 5;
  var Repost = 6;
  var Reaction = 7;
  var BadgeAward = 8;
  var ChatMessage = 9;
  var ForumThread = 11;
  var Seal = 13;
  var PrivateDirectMessage = 14;
  var FileMessage = 15;
  var GenericRepost = 16;
  var Photo = 20;
  var NormalVideo = 21;
  var ShortVideo = 22;
  var ChannelCreation = 40;
  var ChannelMetadata = 41;
  var ChannelMessage = 42;
  var ChannelHideMessage = 43;
  var ChannelMuteUser = 44;
  var OpenTimestamps = 1040;
  var GiftWrap = 1059;
  var Poll = 1068;
  var FileMetadata = 1063;
  var Comment = 1111;
  var LiveChatMessage = 1311;
  var Voice = 1222;
  var VoiceComment = 1244;
  var ProblemTracker = 1971;
  var Report = 1984;
  var Reporting = 1984;
  var Label = 1985;
  var CommunityPostApproval = 4550;
  var JobRequest = 5999;
  var JobResult = 6999;
  var JobFeedback = 7e3;
  var ZapGoal = 9041;
  var ZapRequest = 9734;
  var Zap = 9735;
  var Highlights = 9802;
  var PollResponse = 1018;
  var Mutelist = 1e4;
  var Pinlist = 10001;
  var RelayList = 10002;
  var BookmarkList = 10003;
  var CommunitiesList = 10004;
  var PublicChatsList = 10005;
  var BlockedRelaysList = 10006;
  var SearchRelaysList = 10007;
  var FavoriteRelays = 10012;
  var InterestsList = 10015;
  var UserEmojiList = 10030;
  var DirectMessageRelaysList = 10050;
  var FileServerPreference = 10096;
  var BlossomServerList = 10063;
  var NWCWalletInfo = 13194;
  var LightningPubRPC = 21e3;
  var ClientAuth = 22242;
  var NWCWalletRequest = 23194;
  var NWCWalletResponse = 23195;
  var NostrConnect = 24133;
  var HTTPAuth = 27235;
  var Followsets = 3e4;
  var Genericlists = 30001;
  var Relaysets = 30002;
  var Bookmarksets = 30003;
  var Curationsets = 30004;
  var ProfileBadges = 30008;
  var BadgeDefinition = 30009;
  var Interestsets = 30015;
  var CreateOrUpdateStall = 30017;
  var CreateOrUpdateProduct = 30018;
  var LongFormArticle = 30023;
  var DraftLong = 30024;
  var Emojisets = 30030;
  var Application = 30078;
  var LiveEvent = 30311;
  var UserStatuses = 30315;
  var ClassifiedListing = 30402;
  var DraftClassifiedListing = 30403;
  var Date2 = 31922;
  var Time = 31923;
  var Calendar = 31924;
  var CalendarEventRSVP = 31925;
  var RelayReview = 31987;
  var Handlerrecommendation = 31989;
  var Handlerinformation = 31990;
  var CommunityDefinition = 34550;
  var GroupMetadata = 39e3;

  // filter.ts
  function matchFilter(filter, event) {
    if (filter.ids && filter.ids.indexOf(event.id) === -1) {
      return false;
    }
    if (filter.kinds && filter.kinds.indexOf(event.kind) === -1) {
      return false;
    }
    if (filter.authors && filter.authors.indexOf(event.pubkey) === -1) {
      return false;
    }
    for (let f in filter) {
      if (f[0] === "#") {
        let tagName = f.slice(1);
        let values = filter[`#${tagName}`];
        if (values && !event.tags.find(([t, v]) => t === f.slice(1) && values.indexOf(v) !== -1))
          return false;
      }
    }
    if (filter.since && event.created_at < filter.since)
      return false;
    if (filter.until && event.created_at > filter.until)
      return false;
    return true;
  }
  function matchFilters(filters, event) {
    for (let i2 = 0; i2 < filters.length; i2++) {
      if (matchFilter(filters[i2], event)) {
        return true;
      }
    }
    return false;
  }
  function mergeFilters(...filters) {
    let result = {};
    for (let i2 = 0; i2 < filters.length; i2++) {
      let filter = filters[i2];
      Object.entries(filter).forEach(([property, values]) => {
        if (property === "kinds" || property === "ids" || property === "authors" || property[0] === "#") {
          result[property] = result[property] || [];
          for (let v = 0; v < values.length; v++) {
            let value = values[v];
            if (!result[property].includes(value))
              result[property].push(value);
          }
        }
      });
      if (filter.limit && (!result.limit || filter.limit > result.limit))
        result.limit = filter.limit;
      if (filter.until && (!result.until || filter.until > result.until))
        result.until = filter.until;
      if (filter.since && (!result.since || filter.since < result.since))
        result.since = filter.since;
    }
    return result;
  }
  function getFilterLimit(filter) {
    if (filter.ids && !filter.ids.length)
      return 0;
    if (filter.kinds && !filter.kinds.length)
      return 0;
    if (filter.authors && !filter.authors.length)
      return 0;
    for (const [key, value] of Object.entries(filter)) {
      if (key[0] === "#" && Array.isArray(value) && !value.length)
        return 0;
    }
    return Math.min(
      Math.max(0, filter.limit ?? Infinity),
      filter.ids?.length ?? Infinity,
      filter.authors?.length && filter.kinds?.every((kind) => isReplaceableKind(kind)) ? filter.authors.length * filter.kinds.length : Infinity,
      filter.authors?.length && filter.kinds?.every((kind) => isAddressableKind(kind)) && filter["#d"]?.length ? filter.authors.length * filter.kinds.length * filter["#d"].length : Infinity
    );
  }

  // fakejson.ts
  var fakejson_exports = {};
  __export(fakejson_exports, {
    getHex64: () => getHex64,
    getInt: () => getInt,
    getSubscriptionId: () => getSubscriptionId,
    matchEventId: () => matchEventId,
    matchEventKind: () => matchEventKind,
    matchEventPubkey: () => matchEventPubkey
  });
  function getHex64(json, field) {
    let len = field.length + 3;
    let idx = json.indexOf(`"${field}":`) + len;
    let s = json.slice(idx).indexOf(`"`) + idx + 1;
    return json.slice(s, s + 64);
  }
  function getInt(json, field) {
    let len = field.length;
    let idx = json.indexOf(`"${field}":`) + len + 3;
    let sliced = json.slice(idx);
    let end = Math.min(sliced.indexOf(","), sliced.indexOf("}"));
    return parseInt(sliced.slice(0, end), 10);
  }
  function getSubscriptionId(json) {
    let idx = json.slice(0, 22).indexOf(`"EVENT"`);
    if (idx === -1)
      return null;
    let pstart = json.slice(idx + 7 + 1).indexOf(`"`);
    if (pstart === -1)
      return null;
    let start = idx + 7 + 1 + pstart;
    let pend = json.slice(start + 1, 80).indexOf(`"`);
    if (pend === -1)
      return null;
    let end = start + 1 + pend;
    return json.slice(start + 1, end);
  }
  function matchEventId(json, id) {
    return id === getHex64(json, "id");
  }
  function matchEventPubkey(json, pubkey) {
    return pubkey === getHex64(json, "pubkey");
  }
  function matchEventKind(json, kind) {
    return kind === getInt(json, "kind");
  }

  // nip42.ts
  var nip42_exports = {};
  __export(nip42_exports, {
    makeAuthEvent: () => makeAuthEvent
  });
  function makeAuthEvent(relayURL, challenge2) {
    return {
      kind: ClientAuth,
      created_at: Math.floor(Date.now() / 1e3),
      tags: [
        ["relay", relayURL],
        ["challenge", challenge2]
      ],
      content: ""
    };
  }

  // abstract-relay.ts
  var SendingOnClosedConnection = class extends Error {
    constructor(message, relay) {
      super(`Tried to send message '${message} on a closed connection to ${relay}.`);
      this.name = "SendingOnClosedConnection";
    }
  };
  var AbstractRelay = class {
    url;
    _connected = false;
    onclose = null;
    onnotice = (msg) => console.debug(`NOTICE from ${this.url}: ${msg}`);
    onauth;
    baseEoseTimeout = 4400;
    publishTimeout = 4400;
    pingFrequency = 29e3;
    pingTimeout = 2e4;
    resubscribeBackoff = [1e4, 1e4, 1e4, 2e4, 2e4, 3e4, 6e4];
    openSubs = /* @__PURE__ */ new Map();
    enablePing;
    enableReconnect;
    idleSince = Date.now();
    ongoingOperations = 0;
    reconnectTimeoutHandle;
    pingIntervalHandle;
    reconnectAttempts = 0;
    skipReconnection = false;
    connectionPromise;
    openCountRequests = /* @__PURE__ */ new Map();
    openEventPublishes = /* @__PURE__ */ new Map();
    ws;
    challenge;
    authPromise;
    serial = 0;
    verifyEvent;
    _WebSocket;
    constructor(url, opts) {
      this.url = normalizeURL(url);
      this.verifyEvent = opts.verifyEvent;
      this._WebSocket = opts.websocketImplementation || WebSocket;
      this.enablePing = opts.enablePing;
      this.enableReconnect = opts.enableReconnect || false;
    }
    static async connect(url, opts) {
      const relay = new AbstractRelay(url, opts);
      await relay.connect(opts);
      return relay;
    }
    closeAllSubscriptions(reason) {
      for (let [_, sub] of this.openSubs) {
        sub.close(reason);
      }
      this.openSubs.clear();
      for (let [_, ep] of this.openEventPublishes) {
        ep.reject(new Error(reason));
      }
      this.openEventPublishes.clear();
      for (let [_, cr] of this.openCountRequests) {
        cr.reject(new Error(reason));
      }
      this.openCountRequests.clear();
    }
    get connected() {
      return this._connected;
    }
    async reconnect() {
      const backoff = this.resubscribeBackoff[Math.min(this.reconnectAttempts, this.resubscribeBackoff.length - 1)];
      this.reconnectAttempts++;
      this.reconnectTimeoutHandle = setTimeout(async () => {
        try {
          await this.connect();
        } catch (err) {
        }
      }, backoff);
    }
    handleHardClose(reason) {
      if (this.pingIntervalHandle) {
        clearInterval(this.pingIntervalHandle);
        this.pingIntervalHandle = void 0;
      }
      this._connected = false;
      this.connectionPromise = void 0;
      this.idleSince = void 0;
      if (this.enableReconnect && !this.skipReconnection) {
        this.reconnect();
      } else {
        this.onclose?.();
        this.closeAllSubscriptions(reason);
      }
    }
    async connect(opts) {
      let connectionTimeoutHandle;
      if (this.connectionPromise)
        return this.connectionPromise;
      this.challenge = void 0;
      this.authPromise = void 0;
      this.skipReconnection = false;
      this.connectionPromise = new Promise((resolve, reject) => {
        if (opts?.timeout) {
          connectionTimeoutHandle = setTimeout(() => {
            reject("connection timed out");
            this.connectionPromise = void 0;
            this.skipReconnection = true;
            this.onclose?.();
            this.handleHardClose("relay connection timed out");
          }, opts.timeout);
        }
        if (opts?.abort) {
          opts.abort.onabort = reject;
        }
        try {
          this.ws = new this._WebSocket(this.url);
        } catch (err) {
          clearTimeout(connectionTimeoutHandle);
          reject(err);
          return;
        }
        this.ws.onopen = () => {
          if (this.reconnectTimeoutHandle) {
            clearTimeout(this.reconnectTimeoutHandle);
            this.reconnectTimeoutHandle = void 0;
          }
          clearTimeout(connectionTimeoutHandle);
          this._connected = true;
          const isReconnection = this.reconnectAttempts > 0;
          this.reconnectAttempts = 0;
          for (const sub of this.openSubs.values()) {
            sub.eosed = false;
            if (isReconnection) {
              for (let f = 0; f < sub.filters.length; f++) {
                if (sub.lastEmitted) {
                  sub.filters[f].since = sub.lastEmitted + 1;
                }
              }
            }
            sub.fire();
          }
          if (this.enablePing) {
            this.pingIntervalHandle = setInterval(() => this.pingpong(), this.pingFrequency);
          }
          resolve();
        };
        this.ws.onerror = () => {
          clearTimeout(connectionTimeoutHandle);
          reject("connection failed");
          this.connectionPromise = void 0;
          this.skipReconnection = true;
          this.onclose?.();
          this.handleHardClose("relay connection failed");
        };
        this.ws.onclose = (ev) => {
          clearTimeout(connectionTimeoutHandle);
          reject(ev.message || "websocket closed");
          this.handleHardClose("relay connection closed");
        };
        this.ws.onmessage = this._onmessage.bind(this);
      });
      return this.connectionPromise;
    }
    waitForPingPong() {
      return new Promise((resolve) => {
        ;
        this.ws.once("pong", () => resolve(true));
        this.ws.ping();
      });
    }
    waitForDummyReq() {
      return new Promise((resolve, reject) => {
        if (!this.connectionPromise)
          return reject(new Error(`no connection to ${this.url}, can't ping`));
        try {
          const sub = this.subscribe(
            [{ ids: ["aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"], limit: 0 }],
            {
              label: "<forced-ping>",
              oneose: () => {
                resolve(true);
                sub.close();
              },
              onclose() {
                resolve(true);
              },
              eoseTimeout: this.pingTimeout + 1e3
            }
          );
        } catch (err) {
          reject(err);
        }
      });
    }
    async pingpong() {
      if (this.ws?.readyState === 1) {
        const result = await Promise.any([
          this.ws && this.ws.ping && this.ws.once ? this.waitForPingPong() : this.waitForDummyReq(),
          new Promise((res) => setTimeout(() => res(false), this.pingTimeout))
        ]);
        if (!result) {
          if (this.ws?.readyState === this._WebSocket.OPEN) {
            this.ws?.close();
          }
        }
      }
    }
    async send(message) {
      if (!this.connectionPromise)
        throw new SendingOnClosedConnection(message, this.url);
      this.connectionPromise.then(() => {
        this.ws?.send(message);
      });
    }
    async auth(signAuthEvent) {
      const challenge2 = this.challenge;
      if (!challenge2)
        throw new Error("can't perform auth, no challenge was received");
      if (this.authPromise)
        return this.authPromise;
      this.authPromise = new Promise(async (resolve, reject) => {
        try {
          let evt = await signAuthEvent(makeAuthEvent(this.url, challenge2));
          let timeout = setTimeout(() => {
            let ep = this.openEventPublishes.get(evt.id);
            if (ep) {
              ep.reject(new Error("auth timed out"));
              this.openEventPublishes.delete(evt.id);
            }
          }, this.publishTimeout);
          this.openEventPublishes.set(evt.id, { resolve, reject, timeout });
          this.send('["AUTH",' + JSON.stringify(evt) + "]");
        } catch (err) {
          console.warn("subscribe auth function failed:", err);
        }
      });
      return this.authPromise;
    }
    async publish(event) {
      this.idleSince = void 0;
      this.ongoingOperations++;
      const ret = new Promise((resolve, reject) => {
        const timeout = setTimeout(() => {
          const ep = this.openEventPublishes.get(event.id);
          if (ep) {
            ep.reject(new Error("publish timed out"));
            this.openEventPublishes.delete(event.id);
          }
        }, this.publishTimeout);
        this.openEventPublishes.set(event.id, { resolve, reject, timeout });
      });
      this.send('["EVENT",' + JSON.stringify(event) + "]");
      this.ongoingOperations--;
      if (this.ongoingOperations === 0)
        this.idleSince = Date.now();
      return ret;
    }
    async count(filters, params) {
      this.serial++;
      const id = params?.id || "count:" + this.serial;
      const ret = new Promise((resolve, reject) => {
        this.openCountRequests.set(id, { resolve, reject });
      });
      this.send('["COUNT","' + id + '",' + JSON.stringify(filters).substring(1));
      return ret;
    }
    subscribe(filters, params) {
      if (params.label !== "<forced-ping>") {
        this.idleSince = void 0;
        this.ongoingOperations++;
      }
      const sub = this.prepareSubscription(filters, params);
      sub.fire();
      if (params.abort) {
        params.abort.onabort = () => sub.close(String(params.abort.reason || "<aborted>"));
      }
      return sub;
    }
    prepareSubscription(filters, params) {
      this.serial++;
      const id = params.id || (params.label ? params.label + ":" : "sub:") + this.serial;
      const sub = new Subscription(this, id, filters, params);
      this.openSubs.set(id, sub);
      return sub;
    }
    close() {
      this.skipReconnection = true;
      if (this.reconnectTimeoutHandle) {
        clearTimeout(this.reconnectTimeoutHandle);
        this.reconnectTimeoutHandle = void 0;
      }
      if (this.pingIntervalHandle) {
        clearInterval(this.pingIntervalHandle);
        this.pingIntervalHandle = void 0;
      }
      this.closeAllSubscriptions("relay connection closed by us");
      this._connected = false;
      this.idleSince = void 0;
      this.onclose?.();
      if (this.ws?.readyState === this._WebSocket.OPEN) {
        this.ws?.close();
      }
    }
    _onmessage(ev) {
      const json = ev.data;
      if (!json) {
        return;
      }
      const subid = getSubscriptionId(json);
      if (subid) {
        const so = this.openSubs.get(subid);
        if (!so) {
          return;
        }
        const id = getHex64(json, "id");
        const alreadyHave = so.alreadyHaveEvent?.(id);
        so.receivedEvent?.(this, id);
        if (alreadyHave) {
          return;
        }
      }
      try {
        let data = JSON.parse(json);
        switch (data[0]) {
          case "EVENT": {
            const so = this.openSubs.get(data[1]);
            const event = data[2];
            if (this.verifyEvent(event) && matchFilters(so.filters, event)) {
              so.onevent(event);
            } else {
              so.oninvalidevent?.(event);
            }
            if (!so.lastEmitted || so.lastEmitted < event.created_at)
              so.lastEmitted = event.created_at;
            return;
          }
          case "COUNT": {
            const id = data[1];
            const payload = data[2];
            const cr = this.openCountRequests.get(id);
            if (cr) {
              cr.resolve(payload.count);
              this.openCountRequests.delete(id);
            }
            return;
          }
          case "EOSE": {
            const so = this.openSubs.get(data[1]);
            if (!so)
              return;
            so.receivedEose();
            return;
          }
          case "OK": {
            const id = data[1];
            const ok = data[2];
            const reason = data[3];
            const ep = this.openEventPublishes.get(id);
            if (ep) {
              clearTimeout(ep.timeout);
              if (ok)
                ep.resolve(reason);
              else
                ep.reject(new Error(reason));
              this.openEventPublishes.delete(id);
            }
            return;
          }
          case "CLOSED": {
            const id = data[1];
            const so = this.openSubs.get(id);
            if (!so)
              return;
            so.closed = true;
            so.close(data[2]);
            return;
          }
          case "NOTICE": {
            this.onnotice(data[1]);
            return;
          }
          case "AUTH": {
            this.challenge = data[1];
            if (this.onauth) {
              this.auth(this.onauth);
            }
            return;
          }
          default: {
            const so = this.openSubs.get(data[1]);
            so?.oncustom?.(data);
            return;
          }
        }
      } catch (err) {
        try {
          const [_, __, event] = JSON.parse(json);
          console.warn(`[nostr] relay ${this.url} error processing message:`, err, event);
        } catch (_) {
          console.warn(`[nostr] relay ${this.url} error processing message:`, err);
        }
        return;
      }
    }
  };
  var Subscription = class {
    relay;
    id;
    lastEmitted;
    closed = false;
    eosed = false;
    filters;
    alreadyHaveEvent;
    receivedEvent;
    onevent;
    oninvalidevent;
    oneose;
    onclose;
    oncustom;
    eoseTimeout;
    eoseTimeoutHandle;
    constructor(relay, id, filters, params) {
      if (filters.length === 0)
        throw new Error("subscription can't be created with zero filters");
      this.relay = relay;
      this.filters = filters;
      this.id = id;
      this.alreadyHaveEvent = params.alreadyHaveEvent;
      this.receivedEvent = params.receivedEvent;
      this.eoseTimeout = params.eoseTimeout || relay.baseEoseTimeout;
      this.oneose = params.oneose;
      this.onclose = params.onclose;
      this.oninvalidevent = params.oninvalidevent;
      this.onevent = params.onevent || ((event) => {
        console.warn(
          `onevent() callback not defined for subscription '${this.id}' in relay ${this.relay.url}. event received:`,
          event
        );
      });
    }
    fire() {
      this.relay.send('["REQ","' + this.id + '",' + JSON.stringify(this.filters).substring(1));
      this.eoseTimeoutHandle = setTimeout(this.receivedEose.bind(this), this.eoseTimeout);
    }
    receivedEose() {
      if (this.eosed)
        return;
      clearTimeout(this.eoseTimeoutHandle);
      this.eosed = true;
      this.oneose?.();
    }
    close(reason = "closed by caller") {
      if (!this.closed && this.relay.connected) {
        try {
          this.relay.send('["CLOSE",' + JSON.stringify(this.id) + "]");
        } catch (err) {
          if (err instanceof SendingOnClosedConnection) {
          } else {
            throw err;
          }
        }
        this.closed = true;
      }
      this.relay.openSubs.delete(this.id);
      this.relay.ongoingOperations--;
      if (this.relay.ongoingOperations === 0)
        this.relay.idleSince = Date.now();
      this.onclose?.(reason);
    }
  };

  // relay.ts
  var _WebSocket;
  try {
    _WebSocket = WebSocket;
  } catch {
  }
  var Relay = class extends AbstractRelay {
    constructor(url, options) {
      super(url, { verifyEvent, websocketImplementation: _WebSocket, ...options });
    }
    static async connect(url, options) {
      const relay = new Relay(url, options);
      await relay.connect();
      return relay;
    }
  };

  // helpers.ts
  var alwaysTrue = (t) => {
    t[verifiedSymbol] = true;
    return true;
  };

  // abstract-pool.ts
  var AbstractSimplePool = class {
    relays = /* @__PURE__ */ new Map();
    seenOn = /* @__PURE__ */ new Map();
    trackRelays = false;
    verifyEvent;
    enablePing;
    enableReconnect;
    automaticallyAuth;
    trustedRelayURLs = /* @__PURE__ */ new Set();
    onRelayConnectionFailure;
    onRelayConnectionSuccess;
    allowConnectingToRelay;
    maxWaitForConnection;
    _WebSocket;
    constructor(opts) {
      this.verifyEvent = opts.verifyEvent;
      this._WebSocket = opts.websocketImplementation;
      this.enablePing = opts.enablePing;
      this.enableReconnect = opts.enableReconnect || false;
      this.automaticallyAuth = opts.automaticallyAuth;
      this.onRelayConnectionFailure = opts.onRelayConnectionFailure;
      this.onRelayConnectionSuccess = opts.onRelayConnectionSuccess;
      this.allowConnectingToRelay = opts.allowConnectingToRelay;
      this.maxWaitForConnection = opts.maxWaitForConnection || 3e3;
    }
    async ensureRelay(url, params) {
      url = normalizeURL(url);
      let relay = this.relays.get(url);
      if (!relay) {
        relay = new AbstractRelay(url, {
          verifyEvent: this.trustedRelayURLs.has(url) ? alwaysTrue : this.verifyEvent,
          websocketImplementation: this._WebSocket,
          enablePing: this.enablePing,
          enableReconnect: this.enableReconnect
        });
        relay.onclose = () => {
          this.relays.delete(url);
        };
        this.relays.set(url, relay);
      }
      if (this.automaticallyAuth) {
        const authSignerFn = this.automaticallyAuth(url);
        if (authSignerFn) {
          relay.onauth = authSignerFn;
        }
      }
      try {
        await relay.connect({
          timeout: params?.connectionTimeout,
          abort: params?.abort
        });
      } catch (err) {
        this.relays.delete(url);
        throw err;
      }
      return relay;
    }
    close(relays) {
      relays.map(normalizeURL).forEach((url) => {
        this.relays.get(url)?.close();
        this.relays.delete(url);
      });
    }
    subscribe(relays, filter, params) {
      const request = [];
      const uniqUrls = [];
      for (let i2 = 0; i2 < relays.length; i2++) {
        const url = normalizeURL(relays[i2]);
        if (!request.find((r) => r.url === url)) {
          if (uniqUrls.indexOf(url) === -1) {
            uniqUrls.push(url);
            request.push({ url, filter });
          }
        }
      }
      return this.subscribeMap(request, params);
    }
    subscribeMany(relays, filter, params) {
      return this.subscribe(relays, filter, params);
    }
    subscribeMap(requests, params) {
      const grouped = /* @__PURE__ */ new Map();
      for (const req of requests) {
        const { url, filter } = req;
        if (!grouped.has(url))
          grouped.set(url, []);
        grouped.get(url).push(filter);
      }
      const groupedRequests = Array.from(grouped.entries()).map(([url, filters]) => ({ url, filters }));
      if (this.trackRelays) {
        params.receivedEvent = (relay, id) => {
          let set = this.seenOn.get(id);
          if (!set) {
            set = /* @__PURE__ */ new Set();
            this.seenOn.set(id, set);
          }
          set.add(relay);
        };
      }
      const _knownIds = /* @__PURE__ */ new Set();
      const subs = [];
      const eosesReceived = [];
      let handleEose = (i2) => {
        if (eosesReceived[i2])
          return;
        eosesReceived[i2] = true;
        if (eosesReceived.filter((a) => a).length === groupedRequests.length) {
          params.oneose?.();
          handleEose = () => {
          };
        }
      };
      const closesReceived = [];
      let handleClose = (i2, reason) => {
        if (closesReceived[i2])
          return;
        handleEose(i2);
        closesReceived[i2] = reason;
        if (closesReceived.filter((a) => a).length === groupedRequests.length) {
          params.onclose?.(closesReceived);
          handleClose = () => {
          };
        }
      };
      const localAlreadyHaveEventHandler = (id) => {
        if (params.alreadyHaveEvent?.(id)) {
          return true;
        }
        const have = _knownIds.has(id);
        _knownIds.add(id);
        return have;
      };
      const allOpened = Promise.all(
        groupedRequests.map(async ({ url, filters }, i2) => {
          if (this.allowConnectingToRelay?.(url, ["read", filters]) === false) {
            handleClose(i2, "connection skipped by allowConnectingToRelay");
            return;
          }
          let relay;
          try {
            relay = await this.ensureRelay(url, {
              connectionTimeout: this.maxWaitForConnection < (params.maxWait || 0) ? Math.max(params.maxWait * 0.8, params.maxWait - 1e3) : this.maxWaitForConnection,
              abort: params.abort
            });
          } catch (err) {
            this.onRelayConnectionFailure?.(url);
            handleClose(i2, err?.message || String(err));
            return;
          }
          this.onRelayConnectionSuccess?.(url);
          let subscription = relay.subscribe(filters, {
            ...params,
            oneose: () => handleEose(i2),
            onclose: (reason) => {
              if (reason.startsWith("auth-required: ") && params.onauth) {
                relay.auth(params.onauth).then(() => {
                  relay.subscribe(filters, {
                    ...params,
                    oneose: () => handleEose(i2),
                    onclose: (reason2) => {
                      handleClose(i2, reason2);
                    },
                    alreadyHaveEvent: localAlreadyHaveEventHandler,
                    eoseTimeout: params.maxWait,
                    abort: params.abort
                  });
                }).catch((err) => {
                  handleClose(i2, `auth was required and attempted, but failed with: ${err}`);
                });
              } else {
                handleClose(i2, reason);
              }
            },
            alreadyHaveEvent: localAlreadyHaveEventHandler,
            eoseTimeout: params.maxWait,
            abort: params.abort
          });
          subs.push(subscription);
        })
      );
      return {
        async close(reason) {
          await allOpened;
          subs.forEach((sub) => {
            sub.close(reason);
          });
        }
      };
    }
    subscribeEose(relays, filter, params) {
      let subcloser;
      subcloser = this.subscribe(relays, filter, {
        ...params,
        oneose() {
          const reason = "closed automatically on eose";
          if (subcloser)
            subcloser.close(reason);
          else
            params.onclose?.(relays.map((_) => reason));
        }
      });
      return subcloser;
    }
    subscribeManyEose(relays, filter, params) {
      return this.subscribeEose(relays, filter, params);
    }
    async querySync(relays, filter, params) {
      return new Promise(async (resolve) => {
        const events = [];
        this.subscribeEose(relays, filter, {
          ...params,
          onevent(event) {
            events.push(event);
          },
          onclose(_) {
            resolve(events);
          }
        });
      });
    }
    async get(relays, filter, params) {
      filter.limit = 1;
      const events = await this.querySync(relays, filter, params);
      events.sort((a, b) => b.created_at - a.created_at);
      return events[0] || null;
    }
    publish(relays, event, params) {
      return relays.map(normalizeURL).map(async (url, i2, arr) => {
        if (arr.indexOf(url) !== i2) {
          return Promise.reject("duplicate url");
        }
        if (this.allowConnectingToRelay?.(url, ["write", event]) === false) {
          return Promise.reject("connection skipped by allowConnectingToRelay");
        }
        let r;
        try {
          r = await this.ensureRelay(url, {
            connectionTimeout: this.maxWaitForConnection < (params?.maxWait || 0) ? Math.max(params.maxWait * 0.8, params.maxWait - 1e3) : this.maxWaitForConnection,
            abort: params?.abort
          });
        } catch (err) {
          this.onRelayConnectionFailure?.(url);
          return String("connection failure: " + String(err));
        }
        return r.publish(event).catch(async (err) => {
          if (err instanceof Error && err.message.startsWith("auth-required: ") && params?.onauth) {
            await r.auth(params.onauth);
            return r.publish(event);
          }
          throw err;
        }).then((reason) => {
          if (this.trackRelays) {
            let set = this.seenOn.get(event.id);
            if (!set) {
              set = /* @__PURE__ */ new Set();
              this.seenOn.set(event.id, set);
            }
            set.add(r);
          }
          return reason;
        });
      });
    }
    listConnectionStatus() {
      const map = /* @__PURE__ */ new Map();
      this.relays.forEach((relay, url) => map.set(url, relay.connected));
      return map;
    }
    destroy() {
      this.relays.forEach((conn) => conn.close());
      this.relays = /* @__PURE__ */ new Map();
    }
    pruneIdleRelays(idleThresholdMs = 1e4) {
      const prunedUrls = [];
      for (const [url, relay] of this.relays) {
        if (relay.idleSince && Date.now() - relay.idleSince >= idleThresholdMs) {
          this.relays.delete(url);
          prunedUrls.push(url);
          relay.close();
        }
      }
      return prunedUrls;
    }
  };

  // pool.ts
  var _WebSocket2;
  try {
    _WebSocket2 = WebSocket;
  } catch {
  }
  var SimplePool = class extends AbstractSimplePool {
    constructor(options) {
      super({ verifyEvent, websocketImplementation: _WebSocket2, maxWaitForConnection: 3e3, ...options });
    }
  };

  // nip19.ts
  var nip19_exports = {};
  __export(nip19_exports, {
    BECH32_REGEX: () => BECH32_REGEX,
    Bech32MaxSize: () => Bech32MaxSize,
    NostrTypeGuard: () => NostrTypeGuard,
    decode: () => decode,
    decodeNostrURI: () => decodeNostrURI,
    encodeBytes: () => encodeBytes,
    naddrEncode: () => naddrEncode,
    neventEncode: () => neventEncode,
    noteEncode: () => noteEncode,
    nprofileEncode: () => nprofileEncode,
    npubEncode: () => npubEncode,
    nsecEncode: () => nsecEncode
  });

  // node_modules/@scure/base/index.js
  function isBytes2(a) {
    return a instanceof Uint8Array || ArrayBuffer.isView(a) && a.constructor.name === "Uint8Array";
  }
  function abytes2(b) {
    if (!isBytes2(b))
      throw new Error("Uint8Array expected");
  }
  function isArrayOf(isString, arr) {
    if (!Array.isArray(arr))
      return false;
    if (arr.length === 0)
      return true;
    if (isString) {
      return arr.every((item) => typeof item === "string");
    } else {
      return arr.every((item) => Number.isSafeInteger(item));
    }
  }
  function afn(input) {
    if (typeof input !== "function")
      throw new Error("function expected");
    return true;
  }
  function astr(label, input) {
    if (typeof input !== "string")
      throw new Error(`${label}: string expected`);
    return true;
  }
  function anumber2(n) {
    if (!Number.isSafeInteger(n))
      throw new Error(`invalid integer: ${n}`);
  }
  function aArr(input) {
    if (!Array.isArray(input))
      throw new Error("array expected");
  }
  function astrArr(label, input) {
    if (!isArrayOf(true, input))
      throw new Error(`${label}: array of strings expected`);
  }
  function anumArr(label, input) {
    if (!isArrayOf(false, input))
      throw new Error(`${label}: array of numbers expected`);
  }
  function chain(...args) {
    const id = (a) => a;
    const wrap = (a, b) => (c) => a(b(c));
    const encode = args.map((x) => x.encode).reduceRight(wrap, id);
    const decode2 = args.map((x) => x.decode).reduce(wrap, id);
    return { encode, decode: decode2 };
  }
  function alphabet(letters) {
    const lettersA = typeof letters === "string" ? letters.split("") : letters;
    const len = lettersA.length;
    astrArr("alphabet", lettersA);
    const indexes = new Map(lettersA.map((l, i2) => [l, i2]));
    return {
      encode: (digits) => {
        aArr(digits);
        return digits.map((i2) => {
          if (!Number.isSafeInteger(i2) || i2 < 0 || i2 >= len)
            throw new Error(`alphabet.encode: digit index outside alphabet "${i2}". Allowed: ${letters}`);
          return lettersA[i2];
        });
      },
      decode: (input) => {
        aArr(input);
        return input.map((letter) => {
          astr("alphabet.decode", letter);
          const i2 = indexes.get(letter);
          if (i2 === void 0)
            throw new Error(`Unknown letter: "${letter}". Allowed: ${letters}`);
          return i2;
        });
      }
    };
  }
  function join(separator = "") {
    astr("join", separator);
    return {
      encode: (from) => {
        astrArr("join.decode", from);
        return from.join(separator);
      },
      decode: (to) => {
        astr("join.decode", to);
        return to.split(separator);
      }
    };
  }
  function padding(bits, chr = "=") {
    anumber2(bits);
    astr("padding", chr);
    return {
      encode(data) {
        astrArr("padding.encode", data);
        while (data.length * bits % 8)
          data.push(chr);
        return data;
      },
      decode(input) {
        astrArr("padding.decode", input);
        let end = input.length;
        if (end * bits % 8)
          throw new Error("padding: invalid, string should have whole number of bytes");
        for (; end > 0 && input[end - 1] === chr; end--) {
          const last = end - 1;
          const byte = last * bits;
          if (byte % 8 === 0)
            throw new Error("padding: invalid, string has too much padding");
        }
        return input.slice(0, end);
      }
    };
  }
  function normalize(fn) {
    afn(fn);
    return { encode: (from) => from, decode: (to) => fn(to) };
  }
  function convertRadix(data, from, to) {
    if (from < 2)
      throw new Error(`convertRadix: invalid from=${from}, base cannot be less than 2`);
    if (to < 2)
      throw new Error(`convertRadix: invalid to=${to}, base cannot be less than 2`);
    aArr(data);
    if (!data.length)
      return [];
    let pos = 0;
    const res = [];
    const digits = Array.from(data, (d) => {
      anumber2(d);
      if (d < 0 || d >= from)
        throw new Error(`invalid integer: ${d}`);
      return d;
    });
    const dlen = digits.length;
    while (true) {
      let carry = 0;
      let done = true;
      for (let i2 = pos; i2 < dlen; i2++) {
        const digit = digits[i2];
        const fromCarry = from * carry;
        const digitBase = fromCarry + digit;
        if (!Number.isSafeInteger(digitBase) || fromCarry / from !== carry || digitBase - digit !== fromCarry) {
          throw new Error("convertRadix: carry overflow");
        }
        const div = digitBase / to;
        carry = digitBase % to;
        const rounded = Math.floor(div);
        digits[i2] = rounded;
        if (!Number.isSafeInteger(rounded) || rounded * to + carry !== digitBase)
          throw new Error("convertRadix: carry overflow");
        if (!done)
          continue;
        else if (!rounded)
          pos = i2;
        else
          done = false;
      }
      res.push(carry);
      if (done)
        break;
    }
    for (let i2 = 0; i2 < data.length - 1 && data[i2] === 0; i2++)
      res.push(0);
    return res.reverse();
  }
  var gcd = (a, b) => b === 0 ? a : gcd(b, a % b);
  var radix2carry = (from, to) => from + (to - gcd(from, to));
  var powers = /* @__PURE__ */ (() => {
    let res = [];
    for (let i2 = 0; i2 < 40; i2++)
      res.push(2 ** i2);
    return res;
  })();
  function convertRadix2(data, from, to, padding2) {
    aArr(data);
    if (from <= 0 || from > 32)
      throw new Error(`convertRadix2: wrong from=${from}`);
    if (to <= 0 || to > 32)
      throw new Error(`convertRadix2: wrong to=${to}`);
    if (radix2carry(from, to) > 32) {
      throw new Error(`convertRadix2: carry overflow from=${from} to=${to} carryBits=${radix2carry(from, to)}`);
    }
    let carry = 0;
    let pos = 0;
    const max = powers[from];
    const mask = powers[to] - 1;
    const res = [];
    for (const n of data) {
      anumber2(n);
      if (n >= max)
        throw new Error(`convertRadix2: invalid data word=${n} from=${from}`);
      carry = carry << from | n;
      if (pos + from > 32)
        throw new Error(`convertRadix2: carry overflow pos=${pos} from=${from}`);
      pos += from;
      for (; pos >= to; pos -= to)
        res.push((carry >> pos - to & mask) >>> 0);
      const pow = powers[pos];
      if (pow === void 0)
        throw new Error("invalid carry");
      carry &= pow - 1;
    }
    carry = carry << to - pos & mask;
    if (!padding2 && pos >= from)
      throw new Error("Excess padding");
    if (!padding2 && carry > 0)
      throw new Error(`Non-zero padding: ${carry}`);
    if (padding2 && pos > 0)
      res.push(carry >>> 0);
    return res;
  }
  function radix(num2) {
    anumber2(num2);
    const _256 = 2 ** 8;
    return {
      encode: (bytes) => {
        if (!isBytes2(bytes))
          throw new Error("radix.encode input should be Uint8Array");
        return convertRadix(Array.from(bytes), _256, num2);
      },
      decode: (digits) => {
        anumArr("radix.decode", digits);
        return Uint8Array.from(convertRadix(digits, num2, _256));
      }
    };
  }
  function radix2(bits, revPadding = false) {
    anumber2(bits);
    if (bits <= 0 || bits > 32)
      throw new Error("radix2: bits should be in (0..32]");
    if (radix2carry(8, bits) > 32 || radix2carry(bits, 8) > 32)
      throw new Error("radix2: carry overflow");
    return {
      encode: (bytes) => {
        if (!isBytes2(bytes))
          throw new Error("radix2.encode input should be Uint8Array");
        return convertRadix2(Array.from(bytes), 8, bits, !revPadding);
      },
      decode: (digits) => {
        anumArr("radix2.decode", digits);
        return Uint8Array.from(convertRadix2(digits, bits, 8, revPadding));
      }
    };
  }
  function unsafeWrapper(fn) {
    afn(fn);
    return function(...args) {
      try {
        return fn.apply(null, args);
      } catch (e) {
      }
    };
  }
  var base16 = chain(radix2(4), alphabet("0123456789ABCDEF"), join(""));
  var base32 = chain(radix2(5), alphabet("ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"), padding(5), join(""));
  var base32nopad = chain(radix2(5), alphabet("ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"), join(""));
  var base32hex = chain(radix2(5), alphabet("0123456789ABCDEFGHIJKLMNOPQRSTUV"), padding(5), join(""));
  var base32hexnopad = chain(radix2(5), alphabet("0123456789ABCDEFGHIJKLMNOPQRSTUV"), join(""));
  var base32crockford = chain(radix2(5), alphabet("0123456789ABCDEFGHJKMNPQRSTVWXYZ"), join(""), normalize((s) => s.toUpperCase().replace(/O/g, "0").replace(/[IL]/g, "1")));
  var hasBase64Builtin = /* @__PURE__ */ (() => typeof Uint8Array.from([]).toBase64 === "function" && typeof Uint8Array.fromBase64 === "function")();
  var decodeBase64Builtin = (s, isUrl) => {
    astr("base64", s);
    const re = isUrl ? /^[A-Za-z0-9=_-]+$/ : /^[A-Za-z0-9=+/]+$/;
    const alphabet2 = isUrl ? "base64url" : "base64";
    if (s.length > 0 && !re.test(s))
      throw new Error("invalid base64");
    return Uint8Array.fromBase64(s, { alphabet: alphabet2, lastChunkHandling: "strict" });
  };
  var base64 = hasBase64Builtin ? {
    encode(b) {
      abytes2(b);
      return b.toBase64();
    },
    decode(s) {
      return decodeBase64Builtin(s, false);
    }
  } : chain(radix2(6), alphabet("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"), padding(6), join(""));
  var base64nopad = chain(radix2(6), alphabet("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"), join(""));
  var base64url = hasBase64Builtin ? {
    encode(b) {
      abytes2(b);
      return b.toBase64({ alphabet: "base64url" });
    },
    decode(s) {
      return decodeBase64Builtin(s, true);
    }
  } : chain(radix2(6), alphabet("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"), padding(6), join(""));
  var base64urlnopad = chain(radix2(6), alphabet("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"), join(""));
  var genBase58 = (abc) => chain(radix(58), alphabet(abc), join(""));
  var base58 = genBase58("123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz");
  var base58flickr = genBase58("123456789abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ");
  var base58xrp = genBase58("rpshnaf39wBUDNEGHJKLM4PQRST7VWXYZ2bcdeCg65jkm8oFqi1tuvAxyz");
  var BECH_ALPHABET = chain(alphabet("qpzry9x8gf2tvdw0s3jn54khce6mua7l"), join(""));
  var POLYMOD_GENERATORS = [996825010, 642813549, 513874426, 1027748829, 705979059];
  function bech32Polymod(pre) {
    const b = pre >> 25;
    let chk = (pre & 33554431) << 5;
    for (let i2 = 0; i2 < POLYMOD_GENERATORS.length; i2++) {
      if ((b >> i2 & 1) === 1)
        chk ^= POLYMOD_GENERATORS[i2];
    }
    return chk;
  }
  function bechChecksum(prefix, words, encodingConst = 1) {
    const len = prefix.length;
    let chk = 1;
    for (let i2 = 0; i2 < len; i2++) {
      const c = prefix.charCodeAt(i2);
      if (c < 33 || c > 126)
        throw new Error(`Invalid prefix (${prefix})`);
      chk = bech32Polymod(chk) ^ c >> 5;
    }
    chk = bech32Polymod(chk);
    for (let i2 = 0; i2 < len; i2++)
      chk = bech32Polymod(chk) ^ prefix.charCodeAt(i2) & 31;
    for (let v of words)
      chk = bech32Polymod(chk) ^ v;
    for (let i2 = 0; i2 < 6; i2++)
      chk = bech32Polymod(chk);
    chk ^= encodingConst;
    return BECH_ALPHABET.encode(convertRadix2([chk % powers[30]], 30, 5, false));
  }
  function genBech32(encoding) {
    const ENCODING_CONST = encoding === "bech32" ? 1 : 734539939;
    const _words = radix2(5);
    const fromWords = _words.decode;
    const toWords = _words.encode;
    const fromWordsUnsafe = unsafeWrapper(fromWords);
    function encode(prefix, words, limit = 90) {
      astr("bech32.encode prefix", prefix);
      if (isBytes2(words))
        words = Array.from(words);
      anumArr("bech32.encode", words);
      const plen = prefix.length;
      if (plen === 0)
        throw new TypeError(`Invalid prefix length ${plen}`);
      const actualLength = plen + 7 + words.length;
      if (limit !== false && actualLength > limit)
        throw new TypeError(`Length ${actualLength} exceeds limit ${limit}`);
      const lowered = prefix.toLowerCase();
      const sum = bechChecksum(lowered, words, ENCODING_CONST);
      return `${lowered}1${BECH_ALPHABET.encode(words)}${sum}`;
    }
    function decode2(str, limit = 90) {
      astr("bech32.decode input", str);
      const slen = str.length;
      if (slen < 8 || limit !== false && slen > limit)
        throw new TypeError(`invalid string length: ${slen} (${str}). Expected (8..${limit})`);
      const lowered = str.toLowerCase();
      if (str !== lowered && str !== str.toUpperCase())
        throw new Error(`String must be lowercase or uppercase`);
      const sepIndex = lowered.lastIndexOf("1");
      if (sepIndex === 0 || sepIndex === -1)
        throw new Error(`Letter "1" must be present between prefix and data only`);
      const prefix = lowered.slice(0, sepIndex);
      const data = lowered.slice(sepIndex + 1);
      if (data.length < 6)
        throw new Error("Data must be at least 6 characters long");
      const words = BECH_ALPHABET.decode(data).slice(0, -6);
      const sum = bechChecksum(prefix, words, ENCODING_CONST);
      if (!data.endsWith(sum))
        throw new Error(`Invalid checksum in ${str}: expected "${sum}"`);
      return { prefix, words };
    }
    const decodeUnsafe = unsafeWrapper(decode2);
    function decodeToBytes(str) {
      const { prefix, words } = decode2(str, false);
      return { prefix, words, bytes: fromWords(words) };
    }
    function encodeFromBytes(prefix, bytes) {
      return encode(prefix, toWords(bytes));
    }
    return {
      encode,
      decode: decode2,
      encodeFromBytes,
      decodeToBytes,
      decodeUnsafe,
      fromWords,
      fromWordsUnsafe,
      toWords
    };
  }
  var bech32 = genBech32("bech32");
  var bech32m = genBech32("bech32m");
  var hasHexBuiltin2 = /* @__PURE__ */ (() => typeof Uint8Array.from([]).toHex === "function" && typeof Uint8Array.fromHex === "function")();
  var hexBuiltin = {
    encode(data) {
      abytes2(data);
      return data.toHex();
    },
    decode(s) {
      astr("hex", s);
      return Uint8Array.fromHex(s);
    }
  };
  var hex = hasHexBuiltin2 ? hexBuiltin : chain(radix2(4), alphabet("0123456789abcdef"), join(""), normalize((s) => {
    if (typeof s !== "string" || s.length % 2 !== 0)
      throw new TypeError(`hex.decode: expected string, got ${typeof s} with length ${s.length}`);
    return s.toLowerCase();
  }));

  // nip19.ts
  var NostrTypeGuard = {
    isNProfile: (value) => /^nprofile1[a-z\d]+$/.test(value || ""),
    isNEvent: (value) => /^nevent1[a-z\d]+$/.test(value || ""),
    isNAddr: (value) => /^naddr1[a-z\d]+$/.test(value || ""),
    isNSec: (value) => /^nsec1[a-z\d]{58}$/.test(value || ""),
    isNPub: (value) => /^npub1[a-z\d]{58}$/.test(value || ""),
    isNote: (value) => /^note1[a-z\d]+$/.test(value || ""),
    isNcryptsec: (value) => /^ncryptsec1[a-z\d]+$/.test(value || "")
  };
  var Bech32MaxSize = 5e3;
  var BECH32_REGEX = /[\x21-\x7E]{1,83}1[023456789acdefghjklmnpqrstuvwxyz]{6,}/;
  function integerToUint8Array(number) {
    const uint8Array = new Uint8Array(4);
    uint8Array[0] = number >> 24 & 255;
    uint8Array[1] = number >> 16 & 255;
    uint8Array[2] = number >> 8 & 255;
    uint8Array[3] = number & 255;
    return uint8Array;
  }
  function decodeNostrURI(nip19code) {
    try {
      if (nip19code.startsWith("nostr:"))
        nip19code = nip19code.substring(6);
      return decode(nip19code);
    } catch (_err) {
      return { type: "invalid", data: null };
    }
  }
  function decode(code) {
    let { prefix, words } = bech32.decode(code, Bech32MaxSize);
    let data = new Uint8Array(bech32.fromWords(words));
    switch (prefix) {
      case "nprofile": {
        let tlv = parseTLV(data);
        if (!tlv[0]?.[0])
          throw new Error("missing TLV 0 for nprofile");
        if (tlv[0][0].length !== 32)
          throw new Error("TLV 0 should be 32 bytes");
        return {
          type: "nprofile",
          data: {
            pubkey: bytesToHex(tlv[0][0]),
            relays: tlv[1] ? tlv[1].map((d) => utf8Decoder.decode(d)) : []
          }
        };
      }
      case "nevent": {
        let tlv = parseTLV(data);
        if (!tlv[0]?.[0])
          throw new Error("missing TLV 0 for nevent");
        if (tlv[0][0].length !== 32)
          throw new Error("TLV 0 should be 32 bytes");
        if (tlv[2] && tlv[2][0].length !== 32)
          throw new Error("TLV 2 should be 32 bytes");
        if (tlv[3] && tlv[3][0].length !== 4)
          throw new Error("TLV 3 should be 4 bytes");
        return {
          type: "nevent",
          data: {
            id: bytesToHex(tlv[0][0]),
            relays: tlv[1] ? tlv[1].map((d) => utf8Decoder.decode(d)) : [],
            author: tlv[2]?.[0] ? bytesToHex(tlv[2][0]) : void 0,
            kind: tlv[3]?.[0] ? parseInt(bytesToHex(tlv[3][0]), 16) : void 0
          }
        };
      }
      case "naddr": {
        let tlv = parseTLV(data);
        if (!tlv[0]?.[0])
          throw new Error("missing TLV 0 for naddr");
        if (!tlv[2]?.[0])
          throw new Error("missing TLV 2 for naddr");
        if (tlv[2][0].length !== 32)
          throw new Error("TLV 2 should be 32 bytes");
        if (!tlv[3]?.[0])
          throw new Error("missing TLV 3 for naddr");
        if (tlv[3][0].length !== 4)
          throw new Error("TLV 3 should be 4 bytes");
        return {
          type: "naddr",
          data: {
            identifier: utf8Decoder.decode(tlv[0][0]),
            pubkey: bytesToHex(tlv[2][0]),
            kind: parseInt(bytesToHex(tlv[3][0]), 16),
            relays: tlv[1] ? tlv[1].map((d) => utf8Decoder.decode(d)) : []
          }
        };
      }
      case "nsec":
        return { type: prefix, data };
      case "npub":
      case "note":
        return { type: prefix, data: bytesToHex(data) };
      default:
        throw new Error(`unknown prefix ${prefix}`);
    }
  }
  function parseTLV(data) {
    let result = {};
    let rest = data;
    while (rest.length > 0) {
      let t = rest[0];
      let l = rest[1];
      let v = rest.slice(2, 2 + l);
      rest = rest.slice(2 + l);
      if (v.length < l)
        throw new Error(`not enough data to read on TLV ${t}`);
      result[t] = result[t] || [];
      result[t].push(v);
    }
    return result;
  }
  function nsecEncode(key) {
    return encodeBytes("nsec", key);
  }
  function npubEncode(hex2) {
    return encodeBytes("npub", hexToBytes(hex2));
  }
  function noteEncode(hex2) {
    return encodeBytes("note", hexToBytes(hex2));
  }
  function encodeBech32(prefix, data) {
    let words = bech32.toWords(data);
    return bech32.encode(prefix, words, Bech32MaxSize);
  }
  function encodeBytes(prefix, bytes) {
    return encodeBech32(prefix, bytes);
  }
  function nprofileEncode(profile) {
    let data = encodeTLV({
      0: [hexToBytes(profile.pubkey)],
      1: (profile.relays || []).map((url) => utf8Encoder.encode(url))
    });
    return encodeBech32("nprofile", data);
  }
  function neventEncode(event) {
    let kindArray;
    if (event.kind !== void 0) {
      kindArray = integerToUint8Array(event.kind);
    }
    let data = encodeTLV({
      0: [hexToBytes(event.id)],
      1: (event.relays || []).map((url) => utf8Encoder.encode(url)),
      2: event.author ? [hexToBytes(event.author)] : [],
      3: kindArray ? [new Uint8Array(kindArray)] : []
    });
    return encodeBech32("nevent", data);
  }
  function naddrEncode(addr) {
    let kind = new ArrayBuffer(4);
    new DataView(kind).setUint32(0, addr.kind, false);
    let data = encodeTLV({
      0: [utf8Encoder.encode(addr.identifier)],
      1: (addr.relays || []).map((url) => utf8Encoder.encode(url)),
      2: [hexToBytes(addr.pubkey)],
      3: [new Uint8Array(kind)]
    });
    return encodeBech32("naddr", data);
  }
  function encodeTLV(tlv) {
    let entries = [];
    Object.entries(tlv).reverse().forEach(([t, vs]) => {
      vs.forEach((v) => {
        let entry = new Uint8Array(v.length + 2);
        entry.set([parseInt(t)], 0);
        entry.set([v.length], 1);
        entry.set(v, 2);
        entries.push(entry);
      });
    });
    return concatBytes(...entries);
  }

  // references.ts
  var mentionRegex = /\bnostr:((note|npub|naddr|nevent|nprofile)1\w+)\b|#\[(\d+)\]/g;
  function parseReferences(evt) {
    let references = [];
    for (let ref of evt.content.matchAll(mentionRegex)) {
      if (ref[2]) {
        try {
          let { type, data } = decode(ref[1]);
          switch (type) {
            case "npub": {
              references.push({
                text: ref[0],
                profile: { pubkey: data, relays: [] }
              });
              break;
            }
            case "nprofile": {
              references.push({
                text: ref[0],
                profile: data
              });
              break;
            }
            case "note": {
              references.push({
                text: ref[0],
                event: { id: data, relays: [] }
              });
              break;
            }
            case "nevent": {
              references.push({
                text: ref[0],
                event: data
              });
              break;
            }
            case "naddr": {
              references.push({
                text: ref[0],
                address: data
              });
              break;
            }
          }
        } catch (err) {
        }
      } else if (ref[3]) {
        let idx = parseInt(ref[3], 10);
        let tag = evt.tags[idx];
        if (!tag)
          continue;
        switch (tag[0]) {
          case "p": {
            references.push({
              text: ref[0],
              profile: { pubkey: tag[1], relays: tag[2] ? [tag[2]] : [] }
            });
            break;
          }
          case "e": {
            references.push({
              text: ref[0],
              event: { id: tag[1], relays: tag[2] ? [tag[2]] : [] }
            });
            break;
          }
          case "a": {
            try {
              let [kind, pubkey, identifier] = tag[1].split(":");
              references.push({
                text: ref[0],
                address: {
                  identifier,
                  pubkey,
                  kind: parseInt(kind, 10),
                  relays: tag[2] ? [tag[2]] : []
                }
              });
            } catch (err) {
            }
            break;
          }
        }
      }
    }
    return references;
  }

  // nip04.ts
  var nip04_exports = {};
  __export(nip04_exports, {
    decrypt: () => decrypt2,
    encrypt: () => encrypt2
  });

  // node_modules/@noble/ciphers/utils.js
  function isBytes3(a) {
    return a instanceof Uint8Array || ArrayBuffer.isView(a) && a.constructor.name === "Uint8Array";
  }
  function abool2(b) {
    if (typeof b !== "boolean")
      throw new Error(`boolean expected, not ${b}`);
  }
  function anumber3(n) {
    if (!Number.isSafeInteger(n) || n < 0)
      throw new Error("positive integer expected, got " + n);
  }
  function abytes3(value, length, title = "") {
    const bytes = isBytes3(value);
    const len = value?.length;
    const needsLen = length !== void 0;
    if (!bytes || needsLen && len !== length) {
      const prefix = title && `"${title}" `;
      const ofLen = needsLen ? ` of length ${length}` : "";
      const got = bytes ? `length=${len}` : `type=${typeof value}`;
      throw new Error(prefix + "expected Uint8Array" + ofLen + ", got " + got);
    }
    return value;
  }
  function aexists2(instance, checkFinished = true) {
    if (instance.destroyed)
      throw new Error("Hash instance has been destroyed");
    if (checkFinished && instance.finished)
      throw new Error("Hash#digest() has already been called");
  }
  function aoutput2(out, instance) {
    abytes3(out, void 0, "output");
    const min = instance.outputLen;
    if (out.length < min) {
      throw new Error("digestInto() expects output buffer of length at least " + min);
    }
  }
  function u32(arr) {
    return new Uint32Array(arr.buffer, arr.byteOffset, Math.floor(arr.byteLength / 4));
  }
  function clean2(...arrays) {
    for (let i2 = 0; i2 < arrays.length; i2++) {
      arrays[i2].fill(0);
    }
  }
  function createView2(arr) {
    return new DataView(arr.buffer, arr.byteOffset, arr.byteLength);
  }
  var isLE = /* @__PURE__ */ (() => new Uint8Array(new Uint32Array([287454020]).buffer)[0] === 68)();
  function overlapBytes(a, b) {
    return a.buffer === b.buffer && a.byteOffset < b.byteOffset + b.byteLength && b.byteOffset < a.byteOffset + a.byteLength;
  }
  function complexOverlapBytes(input, output) {
    if (overlapBytes(input, output) && input.byteOffset < output.byteOffset)
      throw new Error("complex overlap of input and output is not supported");
  }
  function checkOpts(defaults, opts) {
    if (opts == null || typeof opts !== "object")
      throw new Error("options must be defined");
    const merged = Object.assign(defaults, opts);
    return merged;
  }
  function equalBytes(a, b) {
    if (a.length !== b.length)
      return false;
    let diff = 0;
    for (let i2 = 0; i2 < a.length; i2++)
      diff |= a[i2] ^ b[i2];
    return diff === 0;
  }
  var wrapCipher = (params, constructor) => {
    function wrappedCipher(key, ...args) {
      abytes3(key, void 0, "key");
      if (!isLE)
        throw new Error("Non little-endian hardware is not yet supported");
      if (params.nonceLength !== void 0) {
        const nonce = args[0];
        abytes3(nonce, params.varSizeNonce ? void 0 : params.nonceLength, "nonce");
      }
      const tagl = params.tagLength;
      if (tagl && args[1] !== void 0)
        abytes3(args[1], void 0, "AAD");
      const cipher = constructor(key, ...args);
      const checkOutput = (fnLength, output) => {
        if (output !== void 0) {
          if (fnLength !== 2)
            throw new Error("cipher output not supported");
          abytes3(output, void 0, "output");
        }
      };
      let called = false;
      const wrCipher = {
        encrypt(data, output) {
          if (called)
            throw new Error("cannot encrypt() twice with same key + nonce");
          called = true;
          abytes3(data);
          checkOutput(cipher.encrypt.length, output);
          return cipher.encrypt(data, output);
        },
        decrypt(data, output) {
          abytes3(data);
          if (tagl && data.length < tagl)
            throw new Error('"ciphertext" expected length bigger than tagLength=' + tagl);
          checkOutput(cipher.decrypt.length, output);
          return cipher.decrypt(data, output);
        }
      };
      return wrCipher;
    }
    Object.assign(wrappedCipher, params);
    return wrappedCipher;
  };
  function getOutput(expectedLength, out, onlyAligned = true) {
    if (out === void 0)
      return new Uint8Array(expectedLength);
    if (out.length !== expectedLength)
      throw new Error('"output" expected Uint8Array of length ' + expectedLength + ", got: " + out.length);
    if (onlyAligned && !isAligned32(out))
      throw new Error("invalid output, must be aligned");
    return out;
  }
  function u64Lengths(dataLength, aadLength, isLE2) {
    abool2(isLE2);
    const num2 = new Uint8Array(16);
    const view = createView2(num2);
    view.setBigUint64(0, BigInt(aadLength), isLE2);
    view.setBigUint64(8, BigInt(dataLength), isLE2);
    return num2;
  }
  function isAligned32(bytes) {
    return bytes.byteOffset % 4 === 0;
  }
  function copyBytes2(bytes) {
    return Uint8Array.from(bytes);
  }

  // node_modules/@noble/ciphers/aes.js
  var BLOCK_SIZE = 16;
  var POLY = 283;
  function validateKeyLength(key) {
    if (![16, 24, 32].includes(key.length))
      throw new Error('"aes key" expected Uint8Array of length 16/24/32, got length=' + key.length);
  }
  function mul2(n) {
    return n << 1 ^ POLY & -(n >> 7);
  }
  function mul(a, b) {
    let res = 0;
    for (; b > 0; b >>= 1) {
      res ^= a & -(b & 1);
      a = mul2(a);
    }
    return res;
  }
  var sbox = /* @__PURE__ */ (() => {
    const t = new Uint8Array(256);
    for (let i2 = 0, x = 1; i2 < 256; i2++, x ^= mul2(x))
      t[i2] = x;
    const box = new Uint8Array(256);
    box[0] = 99;
    for (let i2 = 0; i2 < 255; i2++) {
      let x = t[255 - i2];
      x |= x << 8;
      box[t[i2]] = (x ^ x >> 4 ^ x >> 5 ^ x >> 6 ^ x >> 7 ^ 99) & 255;
    }
    clean2(t);
    return box;
  })();
  var invSbox = /* @__PURE__ */ sbox.map((_, j) => sbox.indexOf(j));
  var rotr32_8 = (n) => n << 24 | n >>> 8;
  var rotl32_8 = (n) => n << 8 | n >>> 24;
  function genTtable(sbox2, fn) {
    if (sbox2.length !== 256)
      throw new Error("Wrong sbox length");
    const T0 = new Uint32Array(256).map((_, j) => fn(sbox2[j]));
    const T1 = T0.map(rotl32_8);
    const T2 = T1.map(rotl32_8);
    const T3 = T2.map(rotl32_8);
    const T01 = new Uint32Array(256 * 256);
    const T23 = new Uint32Array(256 * 256);
    const sbox22 = new Uint16Array(256 * 256);
    for (let i2 = 0; i2 < 256; i2++) {
      for (let j = 0; j < 256; j++) {
        const idx = i2 * 256 + j;
        T01[idx] = T0[i2] ^ T1[j];
        T23[idx] = T2[i2] ^ T3[j];
        sbox22[idx] = sbox2[i2] << 8 | sbox2[j];
      }
    }
    return { sbox: sbox2, sbox2: sbox22, T0, T1, T2, T3, T01, T23 };
  }
  var tableEncoding = /* @__PURE__ */ genTtable(sbox, (s) => mul(s, 3) << 24 | s << 16 | s << 8 | mul(s, 2));
  var tableDecoding = /* @__PURE__ */ genTtable(invSbox, (s) => mul(s, 11) << 24 | mul(s, 13) << 16 | mul(s, 9) << 8 | mul(s, 14));
  var xPowers = /* @__PURE__ */ (() => {
    const p = new Uint8Array(16);
    for (let i2 = 0, x = 1; i2 < 16; i2++, x = mul2(x))
      p[i2] = x;
    return p;
  })();
  function expandKeyLE(key) {
    abytes3(key);
    const len = key.length;
    validateKeyLength(key);
    const { sbox2 } = tableEncoding;
    const toClean = [];
    if (!isAligned32(key))
      toClean.push(key = copyBytes2(key));
    const k32 = u32(key);
    const Nk = k32.length;
    const subByte = (n) => applySbox(sbox2, n, n, n, n);
    const xk = new Uint32Array(len + 28);
    xk.set(k32);
    for (let i2 = Nk; i2 < xk.length; i2++) {
      let t = xk[i2 - 1];
      if (i2 % Nk === 0)
        t = subByte(rotr32_8(t)) ^ xPowers[i2 / Nk - 1];
      else if (Nk > 6 && i2 % Nk === 4)
        t = subByte(t);
      xk[i2] = xk[i2 - Nk] ^ t;
    }
    clean2(...toClean);
    return xk;
  }
  function expandKeyDecLE(key) {
    const encKey = expandKeyLE(key);
    const xk = encKey.slice();
    const Nk = encKey.length;
    const { sbox2 } = tableEncoding;
    const { T0, T1, T2, T3 } = tableDecoding;
    for (let i2 = 0; i2 < Nk; i2 += 4) {
      for (let j = 0; j < 4; j++)
        xk[i2 + j] = encKey[Nk - i2 - 4 + j];
    }
    clean2(encKey);
    for (let i2 = 4; i2 < Nk - 4; i2++) {
      const x = xk[i2];
      const w = applySbox(sbox2, x, x, x, x);
      xk[i2] = T0[w & 255] ^ T1[w >>> 8 & 255] ^ T2[w >>> 16 & 255] ^ T3[w >>> 24];
    }
    return xk;
  }
  function apply0123(T01, T23, s0, s1, s2, s3) {
    return T01[s0 << 8 & 65280 | s1 >>> 8 & 255] ^ T23[s2 >>> 8 & 65280 | s3 >>> 24 & 255];
  }
  function applySbox(sbox2, s0, s1, s2, s3) {
    return sbox2[s0 & 255 | s1 & 65280] | sbox2[s2 >>> 16 & 255 | s3 >>> 16 & 65280] << 16;
  }
  function encrypt(xk, s0, s1, s2, s3) {
    const { sbox2, T01, T23 } = tableEncoding;
    let k = 0;
    s0 ^= xk[k++], s1 ^= xk[k++], s2 ^= xk[k++], s3 ^= xk[k++];
    const rounds = xk.length / 4 - 2;
    for (let i2 = 0; i2 < rounds; i2++) {
      const t02 = xk[k++] ^ apply0123(T01, T23, s0, s1, s2, s3);
      const t12 = xk[k++] ^ apply0123(T01, T23, s1, s2, s3, s0);
      const t22 = xk[k++] ^ apply0123(T01, T23, s2, s3, s0, s1);
      const t32 = xk[k++] ^ apply0123(T01, T23, s3, s0, s1, s2);
      s0 = t02, s1 = t12, s2 = t22, s3 = t32;
    }
    const t0 = xk[k++] ^ applySbox(sbox2, s0, s1, s2, s3);
    const t1 = xk[k++] ^ applySbox(sbox2, s1, s2, s3, s0);
    const t2 = xk[k++] ^ applySbox(sbox2, s2, s3, s0, s1);
    const t3 = xk[k++] ^ applySbox(sbox2, s3, s0, s1, s2);
    return { s0: t0, s1: t1, s2: t2, s3: t3 };
  }
  function decrypt(xk, s0, s1, s2, s3) {
    const { sbox2, T01, T23 } = tableDecoding;
    let k = 0;
    s0 ^= xk[k++], s1 ^= xk[k++], s2 ^= xk[k++], s3 ^= xk[k++];
    const rounds = xk.length / 4 - 2;
    for (let i2 = 0; i2 < rounds; i2++) {
      const t02 = xk[k++] ^ apply0123(T01, T23, s0, s3, s2, s1);
      const t12 = xk[k++] ^ apply0123(T01, T23, s1, s0, s3, s2);
      const t22 = xk[k++] ^ apply0123(T01, T23, s2, s1, s0, s3);
      const t32 = xk[k++] ^ apply0123(T01, T23, s3, s2, s1, s0);
      s0 = t02, s1 = t12, s2 = t22, s3 = t32;
    }
    const t0 = xk[k++] ^ applySbox(sbox2, s0, s3, s2, s1);
    const t1 = xk[k++] ^ applySbox(sbox2, s1, s0, s3, s2);
    const t2 = xk[k++] ^ applySbox(sbox2, s2, s1, s0, s3);
    const t3 = xk[k++] ^ applySbox(sbox2, s3, s2, s1, s0);
    return { s0: t0, s1: t1, s2: t2, s3: t3 };
  }
  function validateBlockDecrypt(data) {
    abytes3(data);
    if (data.length % BLOCK_SIZE !== 0) {
      throw new Error("aes-(cbc/ecb).decrypt ciphertext should consist of blocks with size " + BLOCK_SIZE);
    }
  }
  function validateBlockEncrypt(plaintext, pcks5, dst) {
    abytes3(plaintext);
    let outLen = plaintext.length;
    const remaining = outLen % BLOCK_SIZE;
    if (!pcks5 && remaining !== 0)
      throw new Error("aec/(cbc-ecb): unpadded plaintext with disabled padding");
    if (!isAligned32(plaintext))
      plaintext = copyBytes2(plaintext);
    const b = u32(plaintext);
    if (pcks5) {
      let left = BLOCK_SIZE - remaining;
      if (!left)
        left = BLOCK_SIZE;
      outLen = outLen + left;
    }
    dst = getOutput(outLen, dst);
    complexOverlapBytes(plaintext, dst);
    const o = u32(dst);
    return { b, o, out: dst };
  }
  function validatePCKS(data, pcks5) {
    if (!pcks5)
      return data;
    const len = data.length;
    if (!len)
      throw new Error("aes/pcks5: empty ciphertext not allowed");
    const lastByte = data[len - 1];
    if (lastByte <= 0 || lastByte > 16)
      throw new Error("aes/pcks5: wrong padding");
    const out = data.subarray(0, -lastByte);
    for (let i2 = 0; i2 < lastByte; i2++)
      if (data[len - i2 - 1] !== lastByte)
        throw new Error("aes/pcks5: wrong padding");
    return out;
  }
  function padPCKS(left) {
    const tmp = new Uint8Array(16);
    const tmp32 = u32(tmp);
    tmp.set(left);
    const paddingByte = BLOCK_SIZE - left.length;
    for (let i2 = BLOCK_SIZE - paddingByte; i2 < BLOCK_SIZE; i2++)
      tmp[i2] = paddingByte;
    return tmp32;
  }
  var cbc = /* @__PURE__ */ wrapCipher({ blockSize: 16, nonceLength: 16 }, function aescbc(key, iv, opts = {}) {
    const pcks5 = !opts.disablePadding;
    return {
      encrypt(plaintext, dst) {
        const xk = expandKeyLE(key);
        const { b, o, out: _out } = validateBlockEncrypt(plaintext, pcks5, dst);
        let _iv = iv;
        const toClean = [xk];
        if (!isAligned32(_iv))
          toClean.push(_iv = copyBytes2(_iv));
        const n32 = u32(_iv);
        let s0 = n32[0], s1 = n32[1], s2 = n32[2], s3 = n32[3];
        let i2 = 0;
        for (; i2 + 4 <= b.length; ) {
          s0 ^= b[i2 + 0], s1 ^= b[i2 + 1], s2 ^= b[i2 + 2], s3 ^= b[i2 + 3];
          ({ s0, s1, s2, s3 } = encrypt(xk, s0, s1, s2, s3));
          o[i2++] = s0, o[i2++] = s1, o[i2++] = s2, o[i2++] = s3;
        }
        if (pcks5) {
          const tmp32 = padPCKS(plaintext.subarray(i2 * 4));
          s0 ^= tmp32[0], s1 ^= tmp32[1], s2 ^= tmp32[2], s3 ^= tmp32[3];
          ({ s0, s1, s2, s3 } = encrypt(xk, s0, s1, s2, s3));
          o[i2++] = s0, o[i2++] = s1, o[i2++] = s2, o[i2++] = s3;
        }
        clean2(...toClean);
        return _out;
      },
      decrypt(ciphertext, dst) {
        validateBlockDecrypt(ciphertext);
        const xk = expandKeyDecLE(key);
        let _iv = iv;
        const toClean = [xk];
        if (!isAligned32(_iv))
          toClean.push(_iv = copyBytes2(_iv));
        const n32 = u32(_iv);
        dst = getOutput(ciphertext.length, dst);
        if (!isAligned32(ciphertext))
          toClean.push(ciphertext = copyBytes2(ciphertext));
        complexOverlapBytes(ciphertext, dst);
        const b = u32(ciphertext);
        const o = u32(dst);
        let s0 = n32[0], s1 = n32[1], s2 = n32[2], s3 = n32[3];
        for (let i2 = 0; i2 + 4 <= b.length; ) {
          const ps0 = s0, ps1 = s1, ps2 = s2, ps3 = s3;
          s0 = b[i2 + 0], s1 = b[i2 + 1], s2 = b[i2 + 2], s3 = b[i2 + 3];
          const { s0: o0, s1: o1, s2: o2, s3: o3 } = decrypt(xk, s0, s1, s2, s3);
          o[i2++] = o0 ^ ps0, o[i2++] = o1 ^ ps1, o[i2++] = o2 ^ ps2, o[i2++] = o3 ^ ps3;
        }
        clean2(...toClean);
        return validatePCKS(dst, pcks5);
      }
    };
  });
  function isBytes32(a) {
    return a instanceof Uint32Array || ArrayBuffer.isView(a) && a.constructor.name === "Uint32Array";
  }
  function encryptBlock(xk, block) {
    abytes3(block, 16, "block");
    if (!isBytes32(xk))
      throw new Error("_encryptBlock accepts result of expandKeyLE");
    const b32 = u32(block);
    let { s0, s1, s2, s3 } = encrypt(xk, b32[0], b32[1], b32[2], b32[3]);
    b32[0] = s0, b32[1] = s1, b32[2] = s2, b32[3] = s3;
    return block;
  }
  function dbl(block) {
    let carry = 0;
    for (let i2 = BLOCK_SIZE - 1; i2 >= 0; i2--) {
      const newCarry = (block[i2] & 128) >>> 7;
      block[i2] = block[i2] << 1 | carry;
      carry = newCarry;
    }
    if (carry) {
      block[BLOCK_SIZE - 1] ^= 135;
    }
    return block;
  }
  function xorBlock(a, b) {
    if (a.length !== b.length)
      throw new Error("xorBlock: blocks must have same length");
    for (let i2 = 0; i2 < a.length; i2++) {
      a[i2] = a[i2] ^ b[i2];
    }
    return a;
  }
  var _CMAC = class {
    buffer;
    destroyed;
    k1;
    k2;
    xk;
    constructor(key) {
      abytes3(key);
      validateKeyLength(key);
      this.xk = expandKeyLE(key);
      this.buffer = new Uint8Array(0);
      this.destroyed = false;
      const L = new Uint8Array(BLOCK_SIZE);
      encryptBlock(this.xk, L);
      this.k1 = dbl(L);
      this.k2 = dbl(new Uint8Array(this.k1));
    }
    update(data) {
      const { destroyed, buffer } = this;
      if (destroyed)
        throw new Error("CMAC instance was destroyed");
      abytes3(data);
      const newBuffer = new Uint8Array(buffer.length + data.length);
      newBuffer.set(buffer);
      newBuffer.set(data, buffer.length);
      this.buffer = newBuffer;
      return this;
    }
    digest() {
      if (this.destroyed)
        throw new Error("CMAC instance was destroyed");
      const { buffer } = this;
      const msgLen = buffer.length;
      let n = Math.ceil(msgLen / BLOCK_SIZE);
      let flag;
      if (n === 0) {
        n = 1;
        flag = false;
      } else {
        flag = msgLen % BLOCK_SIZE === 0;
      }
      const lastBlockStart = (n - 1) * BLOCK_SIZE;
      const lastBlockData = buffer.subarray(lastBlockStart);
      let m_last;
      if (flag) {
        m_last = xorBlock(new Uint8Array(lastBlockData), this.k1);
      } else {
        const padded = new Uint8Array(BLOCK_SIZE);
        padded.set(lastBlockData);
        padded[lastBlockData.length] = 128;
        m_last = xorBlock(padded, this.k2);
      }
      let x = new Uint8Array(BLOCK_SIZE);
      for (let i2 = 0; i2 < n - 1; i2++) {
        const m_i = buffer.subarray(i2 * BLOCK_SIZE, (i2 + 1) * BLOCK_SIZE);
        xorBlock(x, m_i);
        encryptBlock(this.xk, x);
      }
      xorBlock(x, m_last);
      encryptBlock(this.xk, x);
      clean2(m_last);
      return x;
    }
    destroy() {
      const { buffer, destroyed, xk, k1, k2 } = this;
      if (destroyed)
        return;
      this.destroyed = true;
      clean2(buffer, xk, k1, k2);
    }
  };
  var cmac = (key, message) => new _CMAC(key).update(message).digest();
  cmac.create = (key) => new _CMAC(key);

  // nip04.ts
  function encrypt2(secretKey, pubkey, text) {
    const privkey = secretKey instanceof Uint8Array ? secretKey : hexToBytes(secretKey);
    const key = secp256k1.getSharedSecret(privkey, hexToBytes("02" + pubkey));
    const normalizedKey = getNormalizedX(key);
    let iv = Uint8Array.from(randomBytes(16));
    let plaintext = utf8Encoder.encode(text);
    let ciphertext = cbc(normalizedKey, iv).encrypt(plaintext);
    let ctb64 = base64.encode(new Uint8Array(ciphertext));
    let ivb64 = base64.encode(new Uint8Array(iv.buffer));
    return `${ctb64}?iv=${ivb64}`;
  }
  function decrypt2(secretKey, pubkey, data) {
    const privkey = secretKey instanceof Uint8Array ? secretKey : hexToBytes(secretKey);
    let [ctb64, ivb64] = data.split("?iv=");
    let key = secp256k1.getSharedSecret(privkey, hexToBytes("02" + pubkey));
    let normalizedKey = getNormalizedX(key);
    let iv = base64.decode(ivb64);
    let ciphertext = base64.decode(ctb64);
    let plaintext = cbc(normalizedKey, iv).decrypt(ciphertext);
    return utf8Decoder.decode(plaintext);
  }
  function getNormalizedX(key) {
    return key.slice(1, 33);
  }

  // nip05.ts
  var nip05_exports = {};
  __export(nip05_exports, {
    NIP05_REGEX: () => NIP05_REGEX,
    isNip05: () => isNip05,
    isValid: () => isValid,
    queryProfile: () => queryProfile,
    searchDomain: () => searchDomain,
    useFetchImplementation: () => useFetchImplementation
  });
  var NIP05_REGEX = /^(?:([\w.+-]+)@)?([\w_-]+(\.[\w_-]+)+)$/;
  var isNip05 = (value) => NIP05_REGEX.test(value || "");
  var _fetch;
  try {
    _fetch = fetch;
  } catch (_) {
    null;
  }
  function useFetchImplementation(fetchImplementation) {
    _fetch = fetchImplementation;
  }
  async function searchDomain(domain, query = "") {
    try {
      const url = `https://${domain}/.well-known/nostr.json?name=${query}`;
      const res = await _fetch(url, { redirect: "manual" });
      if (res.status !== 200) {
        throw Error("Wrong response code");
      }
      const json = await res.json();
      return json.names;
    } catch (_) {
      return {};
    }
  }
  async function queryProfile(fullname) {
    const match = fullname.match(NIP05_REGEX);
    if (!match)
      return null;
    const [, name = "_", domain] = match;
    try {
      const url = `https://${domain}/.well-known/nostr.json?name=${name}`;
      const res = await _fetch(url, { redirect: "manual" });
      if (res.status !== 200) {
        throw Error("Wrong response code");
      }
      const json = await res.json();
      const pubkey = json.names[name];
      return pubkey ? { pubkey, relays: json.relays?.[pubkey] } : null;
    } catch (_e) {
      return null;
    }
  }
  async function isValid(pubkey, nip05) {
    const res = await queryProfile(nip05);
    return res ? res.pubkey === pubkey : false;
  }

  // nip10.ts
  var nip10_exports = {};
  __export(nip10_exports, {
    parse: () => parse
  });
  function parse(event) {
    const result = {
      reply: void 0,
      root: void 0,
      mentions: [],
      profiles: [],
      quotes: []
    };
    let maybeParent;
    let maybeRoot;
    for (let i2 = event.tags.length - 1; i2 >= 0; i2--) {
      const tag = event.tags[i2];
      if (tag[0] === "e" && tag[1]) {
        const [_, eTagEventId, eTagRelayUrl, eTagMarker, eTagAuthor] = tag;
        const eventPointer = {
          id: eTagEventId,
          relays: eTagRelayUrl ? [eTagRelayUrl] : [],
          author: eTagAuthor
        };
        if (eTagMarker === "root") {
          result.root = eventPointer;
          continue;
        }
        if (eTagMarker === "reply") {
          result.reply = eventPointer;
          continue;
        }
        if (eTagMarker === "mention") {
          result.mentions.push(eventPointer);
          continue;
        }
        if (!maybeParent) {
          maybeParent = eventPointer;
        } else {
          maybeRoot = eventPointer;
        }
        result.mentions.push(eventPointer);
        continue;
      }
      if (tag[0] === "q" && tag[1]) {
        const [_, eTagEventId, eTagRelayUrl] = tag;
        result.quotes.push({
          id: eTagEventId,
          relays: eTagRelayUrl ? [eTagRelayUrl] : []
        });
      }
      if (tag[0] === "p" && tag[1]) {
        result.profiles.push({
          pubkey: tag[1],
          relays: tag[2] ? [tag[2]] : []
        });
        continue;
      }
    }
    if (!result.root) {
      result.root = maybeRoot || maybeParent || result.reply;
    }
    if (!result.reply) {
      result.reply = maybeParent || result.root;
    }
    ;
    [result.reply, result.root].forEach((ref) => {
      if (!ref)
        return;
      let idx = result.mentions.indexOf(ref);
      if (idx !== -1) {
        result.mentions.splice(idx, 1);
      }
      if (ref.author) {
        let author = result.profiles.find((p) => p.pubkey === ref.author);
        if (author && author.relays) {
          if (!ref.relays) {
            ref.relays = [];
          }
          author.relays.forEach((url) => {
            if (ref.relays?.indexOf(url) === -1)
              ref.relays.push(url);
          });
          author.relays = ref.relays;
        }
      }
    });
    result.mentions.forEach((ref) => {
      if (ref.author) {
        let author = result.profiles.find((p) => p.pubkey === ref.author);
        if (author && author.relays) {
          if (!ref.relays) {
            ref.relays = [];
          }
          author.relays.forEach((url) => {
            if (ref.relays.indexOf(url) === -1)
              ref.relays.push(url);
          });
          author.relays = ref.relays;
        }
      }
    });
    return result;
  }

  // nip11.ts
  var nip11_exports = {};
  __export(nip11_exports, {
    fetchRelayInformation: () => fetchRelayInformation,
    useFetchImplementation: () => useFetchImplementation2
  });
  var _fetch2;
  try {
    _fetch2 = fetch;
  } catch {
  }
  function useFetchImplementation2(fetchImplementation) {
    _fetch2 = fetchImplementation;
  }
  async function fetchRelayInformation(url) {
    return await (await fetch(url.replace("ws://", "http://").replace("wss://", "https://"), {
      headers: { Accept: "application/nostr+json" }
    })).json();
  }

  // nip13.ts
  var nip13_exports = {};
  __export(nip13_exports, {
    getPow: () => getPow,
    minePow: () => minePow
  });
  function getPow(hex2) {
    let count = 0;
    for (let i2 = 0; i2 < 64; i2 += 8) {
      const nibble = parseInt(hex2.substring(i2, i2 + 8), 16);
      if (nibble === 0) {
        count += 32;
      } else {
        count += Math.clz32(nibble);
        break;
      }
    }
    return count;
  }
  function getPowFromBytes(hash) {
    let count = 0;
    for (let i2 = 0; i2 < hash.length; i2++) {
      const byte = hash[i2];
      if (byte === 0) {
        count += 8;
      } else {
        count += Math.clz32(byte) - 24;
        break;
      }
    }
    return count;
  }
  function minePow(unsigned, difficulty) {
    let count = 0;
    const event = unsigned;
    const tag = ["nonce", count.toString(), difficulty.toString()];
    event.tags.push(tag);
    while (true) {
      const now2 = Math.floor(new Date().getTime() / 1e3);
      if (now2 !== event.created_at) {
        count = 0;
        event.created_at = now2;
      }
      tag[1] = (++count).toString();
      const hash = sha256(
        utf8Encoder.encode(JSON.stringify([0, event.pubkey, event.created_at, event.kind, event.tags, event.content]))
      );
      if (getPowFromBytes(hash) >= difficulty) {
        event.id = bytesToHex(hash);
        break;
      }
    }
    return event;
  }

  // nip17.ts
  var nip17_exports = {};
  __export(nip17_exports, {
    unwrapEvent: () => unwrapEvent2,
    unwrapManyEvents: () => unwrapManyEvents2,
    wrapEvent: () => wrapEvent2,
    wrapManyEvents: () => wrapManyEvents2
  });

  // nip59.ts
  var nip59_exports = {};
  __export(nip59_exports, {
    createRumor: () => createRumor,
    createSeal: () => createSeal,
    createWrap: () => createWrap,
    unwrapEvent: () => unwrapEvent,
    unwrapManyEvents: () => unwrapManyEvents,
    wrapEvent: () => wrapEvent,
    wrapManyEvents: () => wrapManyEvents
  });

  // nip44.ts
  var nip44_exports = {};
  __export(nip44_exports, {
    decrypt: () => decrypt3,
    encrypt: () => encrypt3,
    getConversationKey: () => getConversationKey,
    v2: () => v2
  });

  // node_modules/@noble/ciphers/_arx.js
  var encodeStr = (str) => Uint8Array.from(str.split(""), (c) => c.charCodeAt(0));
  var sigma16 = encodeStr("expand 16-byte k");
  var sigma32 = encodeStr("expand 32-byte k");
  var sigma16_32 = u32(sigma16);
  var sigma32_32 = u32(sigma32);
  function rotl(a, b) {
    return a << b | a >>> 32 - b;
  }
  function isAligned322(b) {
    return b.byteOffset % 4 === 0;
  }
  var BLOCK_LEN = 64;
  var BLOCK_LEN32 = 16;
  var MAX_COUNTER = 2 ** 32 - 1;
  var U32_EMPTY = Uint32Array.of();
  function runCipher(core, sigma, key, nonce, data, output, counter, rounds) {
    const len = data.length;
    const block = new Uint8Array(BLOCK_LEN);
    const b32 = u32(block);
    const isAligned = isAligned322(data) && isAligned322(output);
    const d32 = isAligned ? u32(data) : U32_EMPTY;
    const o32 = isAligned ? u32(output) : U32_EMPTY;
    for (let pos = 0; pos < len; counter++) {
      core(sigma, key, nonce, b32, counter, rounds);
      if (counter >= MAX_COUNTER)
        throw new Error("arx: counter overflow");
      const take = Math.min(BLOCK_LEN, len - pos);
      if (isAligned && take === BLOCK_LEN) {
        const pos32 = pos / 4;
        if (pos % 4 !== 0)
          throw new Error("arx: invalid block position");
        for (let j = 0, posj; j < BLOCK_LEN32; j++) {
          posj = pos32 + j;
          o32[posj] = d32[posj] ^ b32[j];
        }
        pos += BLOCK_LEN;
        continue;
      }
      for (let j = 0, posj; j < take; j++) {
        posj = pos + j;
        output[posj] = data[posj] ^ block[j];
      }
      pos += take;
    }
  }
  function createCipher(core, opts) {
    const { allowShortKeys, extendNonceFn, counterLength, counterRight, rounds } = checkOpts({ allowShortKeys: false, counterLength: 8, counterRight: false, rounds: 20 }, opts);
    if (typeof core !== "function")
      throw new Error("core must be a function");
    anumber3(counterLength);
    anumber3(rounds);
    abool2(counterRight);
    abool2(allowShortKeys);
    return (key, nonce, data, output, counter = 0) => {
      abytes3(key, void 0, "key");
      abytes3(nonce, void 0, "nonce");
      abytes3(data, void 0, "data");
      const len = data.length;
      if (output === void 0)
        output = new Uint8Array(len);
      abytes3(output, void 0, "output");
      anumber3(counter);
      if (counter < 0 || counter >= MAX_COUNTER)
        throw new Error("arx: counter overflow");
      if (output.length < len)
        throw new Error(`arx: output (${output.length}) is shorter than data (${len})`);
      const toClean = [];
      let l = key.length;
      let k;
      let sigma;
      if (l === 32) {
        toClean.push(k = copyBytes2(key));
        sigma = sigma32_32;
      } else if (l === 16 && allowShortKeys) {
        k = new Uint8Array(32);
        k.set(key);
        k.set(key, 16);
        sigma = sigma16_32;
        toClean.push(k);
      } else {
        abytes3(key, 32, "arx key");
        throw new Error("invalid key size");
      }
      if (!isAligned322(nonce))
        toClean.push(nonce = copyBytes2(nonce));
      const k32 = u32(k);
      if (extendNonceFn) {
        if (nonce.length !== 24)
          throw new Error(`arx: extended nonce must be 24 bytes`);
        extendNonceFn(sigma, k32, u32(nonce.subarray(0, 16)), k32);
        nonce = nonce.subarray(16);
      }
      const nonceNcLen = 16 - counterLength;
      if (nonceNcLen !== nonce.length)
        throw new Error(`arx: nonce must be ${nonceNcLen} or 16 bytes`);
      if (nonceNcLen !== 12) {
        const nc = new Uint8Array(12);
        nc.set(nonce, counterRight ? 0 : 12 - nonce.length);
        nonce = nc;
        toClean.push(nonce);
      }
      const n32 = u32(nonce);
      runCipher(core, sigma, k32, n32, data, output, counter, rounds);
      clean2(...toClean);
      return output;
    };
  }

  // node_modules/@noble/ciphers/_poly1305.js
  function u8to16(a, i2) {
    return a[i2++] & 255 | (a[i2++] & 255) << 8;
  }
  var Poly1305 = class {
    blockLen = 16;
    outputLen = 16;
    buffer = new Uint8Array(16);
    r = new Uint16Array(10);
    h = new Uint16Array(10);
    pad = new Uint16Array(8);
    pos = 0;
    finished = false;
    constructor(key) {
      key = copyBytes2(abytes3(key, 32, "key"));
      const t0 = u8to16(key, 0);
      const t1 = u8to16(key, 2);
      const t2 = u8to16(key, 4);
      const t3 = u8to16(key, 6);
      const t4 = u8to16(key, 8);
      const t5 = u8to16(key, 10);
      const t6 = u8to16(key, 12);
      const t7 = u8to16(key, 14);
      this.r[0] = t0 & 8191;
      this.r[1] = (t0 >>> 13 | t1 << 3) & 8191;
      this.r[2] = (t1 >>> 10 | t2 << 6) & 7939;
      this.r[3] = (t2 >>> 7 | t3 << 9) & 8191;
      this.r[4] = (t3 >>> 4 | t4 << 12) & 255;
      this.r[5] = t4 >>> 1 & 8190;
      this.r[6] = (t4 >>> 14 | t5 << 2) & 8191;
      this.r[7] = (t5 >>> 11 | t6 << 5) & 8065;
      this.r[8] = (t6 >>> 8 | t7 << 8) & 8191;
      this.r[9] = t7 >>> 5 & 127;
      for (let i2 = 0; i2 < 8; i2++)
        this.pad[i2] = u8to16(key, 16 + 2 * i2);
    }
    process(data, offset, isLast = false) {
      const hibit = isLast ? 0 : 1 << 11;
      const { h, r } = this;
      const r0 = r[0];
      const r1 = r[1];
      const r2 = r[2];
      const r3 = r[3];
      const r4 = r[4];
      const r5 = r[5];
      const r6 = r[6];
      const r7 = r[7];
      const r8 = r[8];
      const r9 = r[9];
      const t0 = u8to16(data, offset + 0);
      const t1 = u8to16(data, offset + 2);
      const t2 = u8to16(data, offset + 4);
      const t3 = u8to16(data, offset + 6);
      const t4 = u8to16(data, offset + 8);
      const t5 = u8to16(data, offset + 10);
      const t6 = u8to16(data, offset + 12);
      const t7 = u8to16(data, offset + 14);
      let h0 = h[0] + (t0 & 8191);
      let h1 = h[1] + ((t0 >>> 13 | t1 << 3) & 8191);
      let h2 = h[2] + ((t1 >>> 10 | t2 << 6) & 8191);
      let h3 = h[3] + ((t2 >>> 7 | t3 << 9) & 8191);
      let h4 = h[4] + ((t3 >>> 4 | t4 << 12) & 8191);
      let h5 = h[5] + (t4 >>> 1 & 8191);
      let h6 = h[6] + ((t4 >>> 14 | t5 << 2) & 8191);
      let h7 = h[7] + ((t5 >>> 11 | t6 << 5) & 8191);
      let h8 = h[8] + ((t6 >>> 8 | t7 << 8) & 8191);
      let h9 = h[9] + (t7 >>> 5 | hibit);
      let c = 0;
      let d0 = c + h0 * r0 + h1 * (5 * r9) + h2 * (5 * r8) + h3 * (5 * r7) + h4 * (5 * r6);
      c = d0 >>> 13;
      d0 &= 8191;
      d0 += h5 * (5 * r5) + h6 * (5 * r4) + h7 * (5 * r3) + h8 * (5 * r2) + h9 * (5 * r1);
      c += d0 >>> 13;
      d0 &= 8191;
      let d1 = c + h0 * r1 + h1 * r0 + h2 * (5 * r9) + h3 * (5 * r8) + h4 * (5 * r7);
      c = d1 >>> 13;
      d1 &= 8191;
      d1 += h5 * (5 * r6) + h6 * (5 * r5) + h7 * (5 * r4) + h8 * (5 * r3) + h9 * (5 * r2);
      c += d1 >>> 13;
      d1 &= 8191;
      let d2 = c + h0 * r2 + h1 * r1 + h2 * r0 + h3 * (5 * r9) + h4 * (5 * r8);
      c = d2 >>> 13;
      d2 &= 8191;
      d2 += h5 * (5 * r7) + h6 * (5 * r6) + h7 * (5 * r5) + h8 * (5 * r4) + h9 * (5 * r3);
      c += d2 >>> 13;
      d2 &= 8191;
      let d3 = c + h0 * r3 + h1 * r2 + h2 * r1 + h3 * r0 + h4 * (5 * r9);
      c = d3 >>> 13;
      d3 &= 8191;
      d3 += h5 * (5 * r8) + h6 * (5 * r7) + h7 * (5 * r6) + h8 * (5 * r5) + h9 * (5 * r4);
      c += d3 >>> 13;
      d3 &= 8191;
      let d4 = c + h0 * r4 + h1 * r3 + h2 * r2 + h3 * r1 + h4 * r0;
      c = d4 >>> 13;
      d4 &= 8191;
      d4 += h5 * (5 * r9) + h6 * (5 * r8) + h7 * (5 * r7) + h8 * (5 * r6) + h9 * (5 * r5);
      c += d4 >>> 13;
      d4 &= 8191;
      let d5 = c + h0 * r5 + h1 * r4 + h2 * r3 + h3 * r2 + h4 * r1;
      c = d5 >>> 13;
      d5 &= 8191;
      d5 += h5 * r0 + h6 * (5 * r9) + h7 * (5 * r8) + h8 * (5 * r7) + h9 * (5 * r6);
      c += d5 >>> 13;
      d5 &= 8191;
      let d6 = c + h0 * r6 + h1 * r5 + h2 * r4 + h3 * r3 + h4 * r2;
      c = d6 >>> 13;
      d6 &= 8191;
      d6 += h5 * r1 + h6 * r0 + h7 * (5 * r9) + h8 * (5 * r8) + h9 * (5 * r7);
      c += d6 >>> 13;
      d6 &= 8191;
      let d7 = c + h0 * r7 + h1 * r6 + h2 * r5 + h3 * r4 + h4 * r3;
      c = d7 >>> 13;
      d7 &= 8191;
      d7 += h5 * r2 + h6 * r1 + h7 * r0 + h8 * (5 * r9) + h9 * (5 * r8);
      c += d7 >>> 13;
      d7 &= 8191;
      let d8 = c + h0 * r8 + h1 * r7 + h2 * r6 + h3 * r5 + h4 * r4;
      c = d8 >>> 13;
      d8 &= 8191;
      d8 += h5 * r3 + h6 * r2 + h7 * r1 + h8 * r0 + h9 * (5 * r9);
      c += d8 >>> 13;
      d8 &= 8191;
      let d9 = c + h0 * r9 + h1 * r8 + h2 * r7 + h3 * r6 + h4 * r5;
      c = d9 >>> 13;
      d9 &= 8191;
      d9 += h5 * r4 + h6 * r3 + h7 * r2 + h8 * r1 + h9 * r0;
      c += d9 >>> 13;
      d9 &= 8191;
      c = (c << 2) + c | 0;
      c = c + d0 | 0;
      d0 = c & 8191;
      c = c >>> 13;
      d1 += c;
      h[0] = d0;
      h[1] = d1;
      h[2] = d2;
      h[3] = d3;
      h[4] = d4;
      h[5] = d5;
      h[6] = d6;
      h[7] = d7;
      h[8] = d8;
      h[9] = d9;
    }
    finalize() {
      const { h, pad: pad2 } = this;
      const g = new Uint16Array(10);
      let c = h[1] >>> 13;
      h[1] &= 8191;
      for (let i2 = 2; i2 < 10; i2++) {
        h[i2] += c;
        c = h[i2] >>> 13;
        h[i2] &= 8191;
      }
      h[0] += c * 5;
      c = h[0] >>> 13;
      h[0] &= 8191;
      h[1] += c;
      c = h[1] >>> 13;
      h[1] &= 8191;
      h[2] += c;
      g[0] = h[0] + 5;
      c = g[0] >>> 13;
      g[0] &= 8191;
      for (let i2 = 1; i2 < 10; i2++) {
        g[i2] = h[i2] + c;
        c = g[i2] >>> 13;
        g[i2] &= 8191;
      }
      g[9] -= 1 << 13;
      let mask = (c ^ 1) - 1;
      for (let i2 = 0; i2 < 10; i2++)
        g[i2] &= mask;
      mask = ~mask;
      for (let i2 = 0; i2 < 10; i2++)
        h[i2] = h[i2] & mask | g[i2];
      h[0] = (h[0] | h[1] << 13) & 65535;
      h[1] = (h[1] >>> 3 | h[2] << 10) & 65535;
      h[2] = (h[2] >>> 6 | h[3] << 7) & 65535;
      h[3] = (h[3] >>> 9 | h[4] << 4) & 65535;
      h[4] = (h[4] >>> 12 | h[5] << 1 | h[6] << 14) & 65535;
      h[5] = (h[6] >>> 2 | h[7] << 11) & 65535;
      h[6] = (h[7] >>> 5 | h[8] << 8) & 65535;
      h[7] = (h[8] >>> 8 | h[9] << 5) & 65535;
      let f = h[0] + pad2[0];
      h[0] = f & 65535;
      for (let i2 = 1; i2 < 8; i2++) {
        f = (h[i2] + pad2[i2] | 0) + (f >>> 16) | 0;
        h[i2] = f & 65535;
      }
      clean2(g);
    }
    update(data) {
      aexists2(this);
      abytes3(data);
      data = copyBytes2(data);
      const { buffer, blockLen } = this;
      const len = data.length;
      for (let pos = 0; pos < len; ) {
        const take = Math.min(blockLen - this.pos, len - pos);
        if (take === blockLen) {
          for (; blockLen <= len - pos; pos += blockLen)
            this.process(data, pos);
          continue;
        }
        buffer.set(data.subarray(pos, pos + take), this.pos);
        this.pos += take;
        pos += take;
        if (this.pos === blockLen) {
          this.process(buffer, 0, false);
          this.pos = 0;
        }
      }
      return this;
    }
    destroy() {
      clean2(this.h, this.r, this.buffer, this.pad);
    }
    digestInto(out) {
      aexists2(this);
      aoutput2(out, this);
      this.finished = true;
      const { buffer, h } = this;
      let { pos } = this;
      if (pos) {
        buffer[pos++] = 1;
        for (; pos < 16; pos++)
          buffer[pos] = 0;
        this.process(buffer, 0, true);
      }
      this.finalize();
      let opos = 0;
      for (let i2 = 0; i2 < 8; i2++) {
        out[opos++] = h[i2] >>> 0;
        out[opos++] = h[i2] >>> 8;
      }
      return out;
    }
    digest() {
      const { buffer, outputLen } = this;
      this.digestInto(buffer);
      const res = buffer.slice(0, outputLen);
      this.destroy();
      return res;
    }
  };
  function wrapConstructorWithKey(hashCons) {
    const hashC = (msg, key) => hashCons(key).update(msg).digest();
    const tmp = hashCons(new Uint8Array(32));
    hashC.outputLen = tmp.outputLen;
    hashC.blockLen = tmp.blockLen;
    hashC.create = (key) => hashCons(key);
    return hashC;
  }
  var poly1305 = /* @__PURE__ */ (() => wrapConstructorWithKey((key) => new Poly1305(key)))();

  // node_modules/@noble/ciphers/chacha.js
  function chachaCore(s, k, n, out, cnt, rounds = 20) {
    let y00 = s[0], y01 = s[1], y02 = s[2], y03 = s[3], y04 = k[0], y05 = k[1], y06 = k[2], y07 = k[3], y08 = k[4], y09 = k[5], y10 = k[6], y11 = k[7], y12 = cnt, y13 = n[0], y14 = n[1], y15 = n[2];
    let x00 = y00, x01 = y01, x02 = y02, x03 = y03, x04 = y04, x05 = y05, x06 = y06, x07 = y07, x08 = y08, x09 = y09, x10 = y10, x11 = y11, x12 = y12, x13 = y13, x14 = y14, x15 = y15;
    for (let r = 0; r < rounds; r += 2) {
      x00 = x00 + x04 | 0;
      x12 = rotl(x12 ^ x00, 16);
      x08 = x08 + x12 | 0;
      x04 = rotl(x04 ^ x08, 12);
      x00 = x00 + x04 | 0;
      x12 = rotl(x12 ^ x00, 8);
      x08 = x08 + x12 | 0;
      x04 = rotl(x04 ^ x08, 7);
      x01 = x01 + x05 | 0;
      x13 = rotl(x13 ^ x01, 16);
      x09 = x09 + x13 | 0;
      x05 = rotl(x05 ^ x09, 12);
      x01 = x01 + x05 | 0;
      x13 = rotl(x13 ^ x01, 8);
      x09 = x09 + x13 | 0;
      x05 = rotl(x05 ^ x09, 7);
      x02 = x02 + x06 | 0;
      x14 = rotl(x14 ^ x02, 16);
      x10 = x10 + x14 | 0;
      x06 = rotl(x06 ^ x10, 12);
      x02 = x02 + x06 | 0;
      x14 = rotl(x14 ^ x02, 8);
      x10 = x10 + x14 | 0;
      x06 = rotl(x06 ^ x10, 7);
      x03 = x03 + x07 | 0;
      x15 = rotl(x15 ^ x03, 16);
      x11 = x11 + x15 | 0;
      x07 = rotl(x07 ^ x11, 12);
      x03 = x03 + x07 | 0;
      x15 = rotl(x15 ^ x03, 8);
      x11 = x11 + x15 | 0;
      x07 = rotl(x07 ^ x11, 7);
      x00 = x00 + x05 | 0;
      x15 = rotl(x15 ^ x00, 16);
      x10 = x10 + x15 | 0;
      x05 = rotl(x05 ^ x10, 12);
      x00 = x00 + x05 | 0;
      x15 = rotl(x15 ^ x00, 8);
      x10 = x10 + x15 | 0;
      x05 = rotl(x05 ^ x10, 7);
      x01 = x01 + x06 | 0;
      x12 = rotl(x12 ^ x01, 16);
      x11 = x11 + x12 | 0;
      x06 = rotl(x06 ^ x11, 12);
      x01 = x01 + x06 | 0;
      x12 = rotl(x12 ^ x01, 8);
      x11 = x11 + x12 | 0;
      x06 = rotl(x06 ^ x11, 7);
      x02 = x02 + x07 | 0;
      x13 = rotl(x13 ^ x02, 16);
      x08 = x08 + x13 | 0;
      x07 = rotl(x07 ^ x08, 12);
      x02 = x02 + x07 | 0;
      x13 = rotl(x13 ^ x02, 8);
      x08 = x08 + x13 | 0;
      x07 = rotl(x07 ^ x08, 7);
      x03 = x03 + x04 | 0;
      x14 = rotl(x14 ^ x03, 16);
      x09 = x09 + x14 | 0;
      x04 = rotl(x04 ^ x09, 12);
      x03 = x03 + x04 | 0;
      x14 = rotl(x14 ^ x03, 8);
      x09 = x09 + x14 | 0;
      x04 = rotl(x04 ^ x09, 7);
    }
    let oi = 0;
    out[oi++] = y00 + x00 | 0;
    out[oi++] = y01 + x01 | 0;
    out[oi++] = y02 + x02 | 0;
    out[oi++] = y03 + x03 | 0;
    out[oi++] = y04 + x04 | 0;
    out[oi++] = y05 + x05 | 0;
    out[oi++] = y06 + x06 | 0;
    out[oi++] = y07 + x07 | 0;
    out[oi++] = y08 + x08 | 0;
    out[oi++] = y09 + x09 | 0;
    out[oi++] = y10 + x10 | 0;
    out[oi++] = y11 + x11 | 0;
    out[oi++] = y12 + x12 | 0;
    out[oi++] = y13 + x13 | 0;
    out[oi++] = y14 + x14 | 0;
    out[oi++] = y15 + x15 | 0;
  }
  function hchacha(s, k, i2, out) {
    let x00 = s[0], x01 = s[1], x02 = s[2], x03 = s[3], x04 = k[0], x05 = k[1], x06 = k[2], x07 = k[3], x08 = k[4], x09 = k[5], x10 = k[6], x11 = k[7], x12 = i2[0], x13 = i2[1], x14 = i2[2], x15 = i2[3];
    for (let r = 0; r < 20; r += 2) {
      x00 = x00 + x04 | 0;
      x12 = rotl(x12 ^ x00, 16);
      x08 = x08 + x12 | 0;
      x04 = rotl(x04 ^ x08, 12);
      x00 = x00 + x04 | 0;
      x12 = rotl(x12 ^ x00, 8);
      x08 = x08 + x12 | 0;
      x04 = rotl(x04 ^ x08, 7);
      x01 = x01 + x05 | 0;
      x13 = rotl(x13 ^ x01, 16);
      x09 = x09 + x13 | 0;
      x05 = rotl(x05 ^ x09, 12);
      x01 = x01 + x05 | 0;
      x13 = rotl(x13 ^ x01, 8);
      x09 = x09 + x13 | 0;
      x05 = rotl(x05 ^ x09, 7);
      x02 = x02 + x06 | 0;
      x14 = rotl(x14 ^ x02, 16);
      x10 = x10 + x14 | 0;
      x06 = rotl(x06 ^ x10, 12);
      x02 = x02 + x06 | 0;
      x14 = rotl(x14 ^ x02, 8);
      x10 = x10 + x14 | 0;
      x06 = rotl(x06 ^ x10, 7);
      x03 = x03 + x07 | 0;
      x15 = rotl(x15 ^ x03, 16);
      x11 = x11 + x15 | 0;
      x07 = rotl(x07 ^ x11, 12);
      x03 = x03 + x07 | 0;
      x15 = rotl(x15 ^ x03, 8);
      x11 = x11 + x15 | 0;
      x07 = rotl(x07 ^ x11, 7);
      x00 = x00 + x05 | 0;
      x15 = rotl(x15 ^ x00, 16);
      x10 = x10 + x15 | 0;
      x05 = rotl(x05 ^ x10, 12);
      x00 = x00 + x05 | 0;
      x15 = rotl(x15 ^ x00, 8);
      x10 = x10 + x15 | 0;
      x05 = rotl(x05 ^ x10, 7);
      x01 = x01 + x06 | 0;
      x12 = rotl(x12 ^ x01, 16);
      x11 = x11 + x12 | 0;
      x06 = rotl(x06 ^ x11, 12);
      x01 = x01 + x06 | 0;
      x12 = rotl(x12 ^ x01, 8);
      x11 = x11 + x12 | 0;
      x06 = rotl(x06 ^ x11, 7);
      x02 = x02 + x07 | 0;
      x13 = rotl(x13 ^ x02, 16);
      x08 = x08 + x13 | 0;
      x07 = rotl(x07 ^ x08, 12);
      x02 = x02 + x07 | 0;
      x13 = rotl(x13 ^ x02, 8);
      x08 = x08 + x13 | 0;
      x07 = rotl(x07 ^ x08, 7);
      x03 = x03 + x04 | 0;
      x14 = rotl(x14 ^ x03, 16);
      x09 = x09 + x14 | 0;
      x04 = rotl(x04 ^ x09, 12);
      x03 = x03 + x04 | 0;
      x14 = rotl(x14 ^ x03, 8);
      x09 = x09 + x14 | 0;
      x04 = rotl(x04 ^ x09, 7);
    }
    let oi = 0;
    out[oi++] = x00;
    out[oi++] = x01;
    out[oi++] = x02;
    out[oi++] = x03;
    out[oi++] = x12;
    out[oi++] = x13;
    out[oi++] = x14;
    out[oi++] = x15;
  }
  var chacha20 = /* @__PURE__ */ createCipher(chachaCore, {
    counterRight: false,
    counterLength: 4,
    allowShortKeys: false
  });
  var xchacha20 = /* @__PURE__ */ createCipher(chachaCore, {
    counterRight: false,
    counterLength: 8,
    extendNonceFn: hchacha,
    allowShortKeys: false
  });
  var ZEROS16 = /* @__PURE__ */ new Uint8Array(16);
  var updatePadded = (h, msg) => {
    h.update(msg);
    const leftover = msg.length % 16;
    if (leftover)
      h.update(ZEROS16.subarray(leftover));
  };
  var ZEROS32 = /* @__PURE__ */ new Uint8Array(32);
  function computeTag(fn, key, nonce, ciphertext, AAD) {
    if (AAD !== void 0)
      abytes3(AAD, void 0, "AAD");
    const authKey = fn(key, nonce, ZEROS32);
    const lengths = u64Lengths(ciphertext.length, AAD ? AAD.length : 0, true);
    const h = poly1305.create(authKey);
    if (AAD)
      updatePadded(h, AAD);
    updatePadded(h, ciphertext);
    h.update(lengths);
    const res = h.digest();
    clean2(authKey, lengths);
    return res;
  }
  var _poly1305_aead = (xorStream) => (key, nonce, AAD) => {
    const tagLength = 16;
    return {
      encrypt(plaintext, output) {
        const plength = plaintext.length;
        output = getOutput(plength + tagLength, output, false);
        output.set(plaintext);
        const oPlain = output.subarray(0, -tagLength);
        xorStream(key, nonce, oPlain, oPlain, 1);
        const tag = computeTag(xorStream, key, nonce, oPlain, AAD);
        output.set(tag, plength);
        clean2(tag);
        return output;
      },
      decrypt(ciphertext, output) {
        output = getOutput(ciphertext.length - tagLength, output, false);
        const data = ciphertext.subarray(0, -tagLength);
        const passedTag = ciphertext.subarray(-tagLength);
        const tag = computeTag(xorStream, key, nonce, data, AAD);
        if (!equalBytes(passedTag, tag))
          throw new Error("invalid tag");
        output.set(ciphertext.subarray(0, -tagLength));
        xorStream(key, nonce, output, output, 1);
        clean2(tag);
        return output;
      }
    };
  };
  var chacha20poly1305 = /* @__PURE__ */ wrapCipher({ blockSize: 64, nonceLength: 12, tagLength: 16 }, _poly1305_aead(chacha20));
  var xchacha20poly1305 = /* @__PURE__ */ wrapCipher({ blockSize: 64, nonceLength: 24, tagLength: 16 }, _poly1305_aead(xchacha20));

  // node_modules/@noble/hashes/hkdf.js
  function extract(hash, ikm, salt) {
    ahash(hash);
    if (salt === void 0)
      salt = new Uint8Array(hash.outputLen);
    return hmac(hash, salt, ikm);
  }
  var HKDF_COUNTER = /* @__PURE__ */ Uint8Array.of(0);
  var EMPTY_BUFFER = /* @__PURE__ */ Uint8Array.of();
  function expand(hash, prk, info, length = 32) {
    ahash(hash);
    anumber(length, "length");
    const olen = hash.outputLen;
    if (length > 255 * olen)
      throw new Error("Length must be <= 255*HashLen");
    const blocks = Math.ceil(length / olen);
    if (info === void 0)
      info = EMPTY_BUFFER;
    else
      abytes(info, void 0, "info");
    const okm = new Uint8Array(blocks * olen);
    const HMAC = hmac.create(hash, prk);
    const HMACTmp = HMAC._cloneInto();
    const T = new Uint8Array(HMAC.outputLen);
    for (let counter = 0; counter < blocks; counter++) {
      HKDF_COUNTER[0] = counter + 1;
      HMACTmp.update(counter === 0 ? EMPTY_BUFFER : T).update(info).update(HKDF_COUNTER).digestInto(T);
      okm.set(T, olen * counter);
      HMAC._cloneInto(HMACTmp);
    }
    HMAC.destroy();
    HMACTmp.destroy();
    clean(T, HKDF_COUNTER);
    return okm.slice(0, length);
  }

  // nip44.ts
  var minPlaintextSize = 1;
  var maxPlaintextSize = 65535;
  function getConversationKey(privkeyA, pubkeyB) {
    const sharedX = secp256k1.getSharedSecret(privkeyA, hexToBytes("02" + pubkeyB)).subarray(1, 33);
    return extract(sha256, sharedX, utf8Encoder.encode("nip44-v2"));
  }
  function getMessageKeys(conversationKey, nonce) {
    const keys = expand(sha256, conversationKey, nonce, 76);
    return {
      chacha_key: keys.subarray(0, 32),
      chacha_nonce: keys.subarray(32, 44),
      hmac_key: keys.subarray(44, 76)
    };
  }
  function calcPaddedLen(len) {
    if (!Number.isSafeInteger(len) || len < 1)
      throw new Error("expected positive integer");
    if (len <= 32)
      return 32;
    const nextPower = 1 << Math.floor(Math.log2(len - 1)) + 1;
    const chunk = nextPower <= 256 ? 32 : nextPower / 8;
    return chunk * (Math.floor((len - 1) / chunk) + 1);
  }
  function writeU16BE(num2) {
    if (!Number.isSafeInteger(num2) || num2 < minPlaintextSize || num2 > maxPlaintextSize)
      throw new Error("invalid plaintext size: must be between 1 and 65535 bytes");
    const arr = new Uint8Array(2);
    new DataView(arr.buffer).setUint16(0, num2, false);
    return arr;
  }
  function pad(plaintext) {
    const unpadded = utf8Encoder.encode(plaintext);
    const unpaddedLen = unpadded.length;
    const prefix = writeU16BE(unpaddedLen);
    const suffix = new Uint8Array(calcPaddedLen(unpaddedLen) - unpaddedLen);
    return concatBytes(prefix, unpadded, suffix);
  }
  function unpad(padded) {
    const unpaddedLen = new DataView(padded.buffer).getUint16(0);
    const unpadded = padded.subarray(2, 2 + unpaddedLen);
    if (unpaddedLen < minPlaintextSize || unpaddedLen > maxPlaintextSize || unpadded.length !== unpaddedLen || padded.length !== 2 + calcPaddedLen(unpaddedLen))
      throw new Error("invalid padding");
    return utf8Decoder.decode(unpadded);
  }
  function hmacAad(key, message, aad) {
    if (aad.length !== 32)
      throw new Error("AAD associated data must be 32 bytes");
    const combined = concatBytes(aad, message);
    return hmac(sha256, key, combined);
  }
  function decodePayload(payload) {
    if (typeof payload !== "string")
      throw new Error("payload must be a valid string");
    const plen = payload.length;
    if (plen < 132 || plen > 87472)
      throw new Error("invalid payload length: " + plen);
    if (payload[0] === "#")
      throw new Error("unknown encryption version");
    let data;
    try {
      data = base64.decode(payload);
    } catch (error) {
      throw new Error("invalid base64: " + error.message);
    }
    const dlen = data.length;
    if (dlen < 99 || dlen > 65603)
      throw new Error("invalid data length: " + dlen);
    const vers = data[0];
    if (vers !== 2)
      throw new Error("unknown encryption version " + vers);
    return {
      nonce: data.subarray(1, 33),
      ciphertext: data.subarray(33, -32),
      mac: data.subarray(-32)
    };
  }
  function encrypt3(plaintext, conversationKey, nonce = randomBytes(32)) {
    const { chacha_key, chacha_nonce, hmac_key } = getMessageKeys(conversationKey, nonce);
    const padded = pad(plaintext);
    const ciphertext = chacha20(chacha_key, chacha_nonce, padded);
    const mac = hmacAad(hmac_key, ciphertext, nonce);
    return base64.encode(concatBytes(new Uint8Array([2]), nonce, ciphertext, mac));
  }
  function decrypt3(payload, conversationKey) {
    const { nonce, ciphertext, mac } = decodePayload(payload);
    const { chacha_key, chacha_nonce, hmac_key } = getMessageKeys(conversationKey, nonce);
    const calculatedMac = hmacAad(hmac_key, ciphertext, nonce);
    if (!equalBytes(calculatedMac, mac))
      throw new Error("invalid MAC");
    const padded = chacha20(chacha_key, chacha_nonce, ciphertext);
    return unpad(padded);
  }
  var v2 = {
    utils: {
      getConversationKey,
      calcPaddedLen
    },
    encrypt: encrypt3,
    decrypt: decrypt3
  };

  // nip59.ts
  var TWO_DAYS = 2 * 24 * 60 * 60;
  var now = () => Math.round(Date.now() / 1e3);
  var randomNow = () => Math.round(now() - Math.random() * TWO_DAYS);
  var nip44ConversationKey = (privateKey, publicKey) => getConversationKey(privateKey, publicKey);
  var nip44Encrypt = (data, privateKey, publicKey) => encrypt3(JSON.stringify(data), nip44ConversationKey(privateKey, publicKey));
  var nip44Decrypt = (data, privateKey) => JSON.parse(decrypt3(data.content, nip44ConversationKey(privateKey, data.pubkey)));
  function createRumor(event, privateKey) {
    const rumor = {
      created_at: now(),
      content: "",
      tags: [],
      ...event,
      pubkey: getPublicKey(privateKey)
    };
    rumor.id = getEventHash(rumor);
    return rumor;
  }
  function createSeal(rumor, privateKey, recipientPublicKey) {
    return finalizeEvent(
      {
        kind: Seal,
        content: nip44Encrypt(rumor, privateKey, recipientPublicKey),
        created_at: randomNow(),
        tags: []
      },
      privateKey
    );
  }
  function createWrap(seal, recipientPublicKey) {
    const randomKey = generateSecretKey();
    return finalizeEvent(
      {
        kind: GiftWrap,
        content: nip44Encrypt(seal, randomKey, recipientPublicKey),
        created_at: randomNow(),
        tags: [["p", recipientPublicKey]]
      },
      randomKey
    );
  }
  function wrapEvent(event, senderPrivateKey, recipientPublicKey) {
    const rumor = createRumor(event, senderPrivateKey);
    const seal = createSeal(rumor, senderPrivateKey, recipientPublicKey);
    return createWrap(seal, recipientPublicKey);
  }
  function wrapManyEvents(event, senderPrivateKey, recipientsPublicKeys) {
    if (!recipientsPublicKeys || recipientsPublicKeys.length === 0) {
      throw new Error("At least one recipient is required.");
    }
    const senderPublicKey = getPublicKey(senderPrivateKey);
    const wrappeds = [wrapEvent(event, senderPrivateKey, senderPublicKey)];
    recipientsPublicKeys.forEach((recipientPublicKey) => {
      wrappeds.push(wrapEvent(event, senderPrivateKey, recipientPublicKey));
    });
    return wrappeds;
  }
  function unwrapEvent(wrap, recipientPrivateKey) {
    const unwrappedSeal = nip44Decrypt(wrap, recipientPrivateKey);
    return nip44Decrypt(unwrappedSeal, recipientPrivateKey);
  }
  function unwrapManyEvents(wrappedEvents, recipientPrivateKey) {
    let unwrappedEvents = [];
    wrappedEvents.forEach((e) => {
      unwrappedEvents.push(unwrapEvent(e, recipientPrivateKey));
    });
    unwrappedEvents.sort((a, b) => a.created_at - b.created_at);
    return unwrappedEvents;
  }

  // nip17.ts
  function createEvent(recipients, message, conversationTitle, replyTo) {
    const baseEvent = {
      created_at: Math.ceil(Date.now() / 1e3),
      kind: PrivateDirectMessage,
      tags: [],
      content: message
    };
    const recipientsArray = Array.isArray(recipients) ? recipients : [recipients];
    recipientsArray.forEach(({ publicKey, relayUrl }) => {
      baseEvent.tags.push(relayUrl ? ["p", publicKey, relayUrl] : ["p", publicKey]);
    });
    if (replyTo) {
      baseEvent.tags.push(["e", replyTo.eventId, replyTo.relayUrl || "", "reply"]);
    }
    if (conversationTitle) {
      baseEvent.tags.push(["subject", conversationTitle]);
    }
    return baseEvent;
  }
  function wrapEvent2(senderPrivateKey, recipient, message, conversationTitle, replyTo) {
    const event = createEvent(recipient, message, conversationTitle, replyTo);
    return wrapEvent(event, senderPrivateKey, recipient.publicKey);
  }
  function wrapManyEvents2(senderPrivateKey, recipients, message, conversationTitle, replyTo) {
    if (!recipients || recipients.length === 0) {
      throw new Error("At least one recipient is required.");
    }
    const senderPublicKey = getPublicKey(senderPrivateKey);
    return [{ publicKey: senderPublicKey }, ...recipients].map(
      (recipient) => wrapEvent2(senderPrivateKey, recipient, message, conversationTitle, replyTo)
    );
  }
  var unwrapEvent2 = unwrapEvent;
  var unwrapManyEvents2 = unwrapManyEvents;

  // nip18.ts
  var nip18_exports = {};
  __export(nip18_exports, {
    finishRepostEvent: () => finishRepostEvent,
    getRepostedEvent: () => getRepostedEvent,
    getRepostedEventPointer: () => getRepostedEventPointer
  });
  function finishRepostEvent(t, reposted, relayUrl, privateKey) {
    let kind;
    const tags = [...t.tags ?? [], ["e", reposted.id, relayUrl], ["p", reposted.pubkey]];
    if (reposted.kind === ShortTextNote) {
      kind = Repost;
    } else {
      kind = GenericRepost;
      tags.push(["k", String(reposted.kind)]);
    }
    return finalizeEvent(
      {
        kind,
        tags,
        content: t.content === "" || reposted.tags?.find((tag) => tag[0] === "-") ? "" : JSON.stringify(reposted),
        created_at: t.created_at
      },
      privateKey
    );
  }
  function getRepostedEventPointer(event) {
    if (![Repost, GenericRepost].includes(event.kind)) {
      return void 0;
    }
    let lastETag;
    let lastPTag;
    for (let i2 = event.tags.length - 1; i2 >= 0 && (lastETag === void 0 || lastPTag === void 0); i2--) {
      const tag = event.tags[i2];
      if (tag.length >= 2) {
        if (tag[0] === "e" && lastETag === void 0) {
          lastETag = tag;
        } else if (tag[0] === "p" && lastPTag === void 0) {
          lastPTag = tag;
        }
      }
    }
    if (lastETag === void 0) {
      return void 0;
    }
    return {
      id: lastETag[1],
      relays: [lastETag[2], lastPTag?.[2]].filter((x) => typeof x === "string"),
      author: lastPTag?.[1]
    };
  }
  function getRepostedEvent(event, { skipVerification } = {}) {
    const pointer = getRepostedEventPointer(event);
    if (pointer === void 0 || event.content === "") {
      return void 0;
    }
    let repostedEvent;
    try {
      repostedEvent = JSON.parse(event.content);
    } catch (error) {
      return void 0;
    }
    if (repostedEvent.id !== pointer.id) {
      return void 0;
    }
    if (!skipVerification && !verifyEvent(repostedEvent)) {
      return void 0;
    }
    return repostedEvent;
  }

  // nip21.ts
  var nip21_exports = {};
  __export(nip21_exports, {
    NOSTR_URI_REGEX: () => NOSTR_URI_REGEX,
    parse: () => parse2,
    test: () => test
  });
  var NOSTR_URI_REGEX = new RegExp(`nostr:(${BECH32_REGEX.source})`);
  function test(value) {
    return typeof value === "string" && new RegExp(`^${NOSTR_URI_REGEX.source}$`).test(value);
  }
  function parse2(uri) {
    const match = uri.match(new RegExp(`^${NOSTR_URI_REGEX.source}$`));
    if (!match)
      throw new Error(`Invalid Nostr URI: ${uri}`);
    return {
      uri: match[0],
      value: match[1],
      decoded: decode(match[1])
    };
  }

  // nip25.ts
  var nip25_exports = {};
  __export(nip25_exports, {
    finishReactionEvent: () => finishReactionEvent,
    getReactedEventPointer: () => getReactedEventPointer
  });
  function finishReactionEvent(t, reacted, privateKey) {
    const inheritedTags = reacted.tags.filter((tag) => tag.length >= 2 && (tag[0] === "e" || tag[0] === "p"));
    return finalizeEvent(
      {
        ...t,
        kind: Reaction,
        tags: [...t.tags ?? [], ...inheritedTags, ["e", reacted.id], ["p", reacted.pubkey]],
        content: t.content ?? "+"
      },
      privateKey
    );
  }
  function getReactedEventPointer(event) {
    if (event.kind !== Reaction) {
      return void 0;
    }
    let lastETag;
    let lastPTag;
    for (let i2 = event.tags.length - 1; i2 >= 0 && (lastETag === void 0 || lastPTag === void 0); i2--) {
      const tag = event.tags[i2];
      if (tag.length >= 2) {
        if (tag[0] === "e" && lastETag === void 0) {
          lastETag = tag;
        } else if (tag[0] === "p" && lastPTag === void 0) {
          lastPTag = tag;
        }
      }
    }
    if (lastETag === void 0 || lastPTag === void 0) {
      return void 0;
    }
    return {
      id: lastETag[1],
      relays: [lastETag[2], lastPTag[2]].filter((x) => x !== void 0),
      author: lastPTag[1]
    };
  }

  // nip27.ts
  var nip27_exports = {};
  __export(nip27_exports, {
    parse: () => parse3
  });
  var noCharacter = /\W/m;
  var noURLCharacter = /[^\w\/] |[^\w\/]$|$|,| /m;
  var MAX_HASHTAG_LENGTH = 42;
  function* parse3(content) {
    let emojis = [];
    if (typeof content !== "string") {
      for (let i2 = 0; i2 < content.tags.length; i2++) {
        const tag = content.tags[i2];
        if (tag[0] === "emoji" && tag.length >= 3) {
          emojis.push({ type: "emoji", shortcode: tag[1], url: tag[2] });
        }
      }
      content = content.content;
    }
    const max = content.length;
    let prevIndex = 0;
    let index = 0;
    mainloop:
      while (index < max) {
        const u = content.indexOf(":", index);
        const h = content.indexOf("#", index);
        if (u === -1 && h === -1) {
          break mainloop;
        }
        if (u === -1 || h >= 0 && h < u) {
          if (h === 0 || content[h - 1].match(noCharacter)) {
            const m = content.slice(h + 1, h + MAX_HASHTAG_LENGTH).match(noCharacter);
            const end = m ? h + 1 + m.index : max;
            yield { type: "text", text: content.slice(prevIndex, h) };
            yield { type: "hashtag", value: content.slice(h + 1, end) };
            index = end;
            prevIndex = index;
            continue mainloop;
          }
          index = h + 1;
          continue mainloop;
        }
        if (content.slice(u - 5, u) === "nostr") {
          const m = content.slice(u + 60).match(noCharacter);
          const end = m ? u + 60 + m.index : max;
          try {
            let pointer;
            let { data, type } = decode(content.slice(u + 1, end));
            switch (type) {
              case "npub":
                pointer = { pubkey: data };
                break;
              case "note":
                pointer = { id: data };
                break;
              case "nsec":
                index = end + 1;
                continue;
              default:
                pointer = data;
            }
            if (prevIndex !== u - 5) {
              yield { type: "text", text: content.slice(prevIndex, u - 5) };
            }
            yield { type: "reference", pointer };
            index = end;
            prevIndex = index;
            continue mainloop;
          } catch (_err) {
            index = u + 1;
            continue mainloop;
          }
        } else if (content.slice(u - 5, u) === "https" || content.slice(u - 4, u) === "http") {
          const m = content.slice(u + 4).match(noURLCharacter);
          const end = m ? u + 4 + m.index : max;
          const prefixLen = content[u - 1] === "s" ? 5 : 4;
          try {
            let url = new URL(content.slice(u - prefixLen, end));
            if (url.hostname.indexOf(".") === -1) {
              throw new Error("invalid url");
            }
            if (prevIndex !== u - prefixLen) {
              yield { type: "text", text: content.slice(prevIndex, u - prefixLen) };
            }
            if (/\.(png|jpe?g|gif|webp|heic|svg)$/i.test(url.pathname)) {
              yield { type: "image", url: url.toString() };
              index = end;
              prevIndex = index;
              continue mainloop;
            }
            if (/\.(mp4|avi|webm|mkv|mov)$/i.test(url.pathname)) {
              yield { type: "video", url: url.toString() };
              index = end;
              prevIndex = index;
              continue mainloop;
            }
            if (/\.(mp3|aac|ogg|opus|wav|flac)$/i.test(url.pathname)) {
              yield { type: "audio", url: url.toString() };
              index = end;
              prevIndex = index;
              continue mainloop;
            }
            yield { type: "url", url: url.toString() };
            index = end;
            prevIndex = index;
            continue mainloop;
          } catch (_err) {
            index = end + 1;
            continue mainloop;
          }
        } else if (content.slice(u - 3, u) === "wss" || content.slice(u - 2, u) === "ws") {
          const m = content.slice(u + 4).match(noURLCharacter);
          const end = m ? u + 4 + m.index : max;
          const prefixLen = content[u - 1] === "s" ? 3 : 2;
          try {
            let url = new URL(content.slice(u - prefixLen, end));
            if (url.hostname.indexOf(".") === -1) {
              throw new Error("invalid ws url");
            }
            if (prevIndex !== u - prefixLen) {
              yield { type: "text", text: content.slice(prevIndex, u - prefixLen) };
            }
            yield { type: "relay", url: url.toString() };
            index = end;
            prevIndex = index;
            continue mainloop;
          } catch (_err) {
            index = end + 1;
            continue mainloop;
          }
        } else {
          for (let e = 0; e < emojis.length; e++) {
            const emoji = emojis[e];
            if (content[u + emoji.shortcode.length + 1] === ":" && content.slice(u + 1, u + emoji.shortcode.length + 1) === emoji.shortcode) {
              if (prevIndex !== u) {
                yield { type: "text", text: content.slice(prevIndex, u) };
              }
              yield emoji;
              index = u + emoji.shortcode.length + 2;
              prevIndex = index;
              continue mainloop;
            }
          }
          index = u + 1;
          continue mainloop;
        }
      }
    if (prevIndex !== max) {
      yield { type: "text", text: content.slice(prevIndex) };
    }
  }

  // nip28.ts
  var nip28_exports = {};
  __export(nip28_exports, {
    channelCreateEvent: () => channelCreateEvent,
    channelHideMessageEvent: () => channelHideMessageEvent,
    channelMessageEvent: () => channelMessageEvent,
    channelMetadataEvent: () => channelMetadataEvent,
    channelMuteUserEvent: () => channelMuteUserEvent
  });
  var channelCreateEvent = (t, privateKey) => {
    let content;
    if (typeof t.content === "object") {
      content = JSON.stringify(t.content);
    } else if (typeof t.content === "string") {
      content = t.content;
    } else {
      return void 0;
    }
    return finalizeEvent(
      {
        kind: ChannelCreation,
        tags: [...t.tags ?? []],
        content,
        created_at: t.created_at
      },
      privateKey
    );
  };
  var channelMetadataEvent = (t, privateKey) => {
    let content;
    if (typeof t.content === "object") {
      content = JSON.stringify(t.content);
    } else if (typeof t.content === "string") {
      content = t.content;
    } else {
      return void 0;
    }
    return finalizeEvent(
      {
        kind: ChannelMetadata,
        tags: [["e", t.channel_create_event_id], ...t.tags ?? []],
        content,
        created_at: t.created_at
      },
      privateKey
    );
  };
  var channelMessageEvent = (t, privateKey) => {
    const tags = [["e", t.channel_create_event_id, t.relay_url, "root"]];
    if (t.reply_to_channel_message_event_id) {
      tags.push(["e", t.reply_to_channel_message_event_id, t.relay_url, "reply"]);
    }
    return finalizeEvent(
      {
        kind: ChannelMessage,
        tags: [...tags, ...t.tags ?? []],
        content: t.content,
        created_at: t.created_at
      },
      privateKey
    );
  };
  var channelHideMessageEvent = (t, privateKey) => {
    let content;
    if (typeof t.content === "object") {
      content = JSON.stringify(t.content);
    } else if (typeof t.content === "string") {
      content = t.content;
    } else {
      return void 0;
    }
    return finalizeEvent(
      {
        kind: ChannelHideMessage,
        tags: [["e", t.channel_message_event_id], ...t.tags ?? []],
        content,
        created_at: t.created_at
      },
      privateKey
    );
  };
  var channelMuteUserEvent = (t, privateKey) => {
    let content;
    if (typeof t.content === "object") {
      content = JSON.stringify(t.content);
    } else if (typeof t.content === "string") {
      content = t.content;
    } else {
      return void 0;
    }
    return finalizeEvent(
      {
        kind: ChannelMuteUser,
        tags: [["p", t.pubkey_to_mute], ...t.tags ?? []],
        content,
        created_at: t.created_at
      },
      privateKey
    );
  };

  // nip30.ts
  var nip30_exports = {};
  __export(nip30_exports, {
    EMOJI_SHORTCODE_REGEX: () => EMOJI_SHORTCODE_REGEX,
    matchAll: () => matchAll,
    regex: () => regex,
    replaceAll: () => replaceAll
  });
  var EMOJI_SHORTCODE_REGEX = /:(\w+):/;
  var regex = () => new RegExp(`\\B${EMOJI_SHORTCODE_REGEX.source}\\B`, "g");
  function* matchAll(content) {
    const matches = content.matchAll(regex());
    for (const match of matches) {
      try {
        const [shortcode, name] = match;
        yield {
          shortcode,
          name,
          start: match.index,
          end: match.index + shortcode.length
        };
      } catch (_e) {
      }
    }
  }
  function replaceAll(content, replacer) {
    return content.replaceAll(regex(), (shortcode, name) => {
      return replacer({
        shortcode,
        name
      });
    });
  }

  // nip39.ts
  var nip39_exports = {};
  __export(nip39_exports, {
    useFetchImplementation: () => useFetchImplementation3,
    validateGithub: () => validateGithub
  });
  var _fetch3;
  try {
    _fetch3 = fetch;
  } catch {
  }
  function useFetchImplementation3(fetchImplementation) {
    _fetch3 = fetchImplementation;
  }
  async function validateGithub(pubkey, username, proof) {
    try {
      let res = await (await _fetch3(`https://gist.github.com/${username}/${proof}/raw`)).text();
      return res === `Verifying that I control the following Nostr public key: ${pubkey}`;
    } catch (_) {
      return false;
    }
  }

  // nip47.ts
  var nip47_exports = {};
  __export(nip47_exports, {
    makeNwcRequestEvent: () => makeNwcRequestEvent,
    parseConnectionString: () => parseConnectionString
  });
  function parseConnectionString(connectionString) {
    const { host, pathname, searchParams } = new URL(connectionString);
    const pubkey = pathname || host;
    const relay = searchParams.get("relay");
    const secret = searchParams.get("secret");
    if (!pubkey || !relay || !secret) {
      throw new Error("invalid connection string");
    }
    return { pubkey, relay, secret };
  }
  async function makeNwcRequestEvent(pubkey, secretKey, invoice) {
    const content = {
      method: "pay_invoice",
      params: {
        invoice
      }
    };
    const encryptedContent = encrypt2(secretKey, pubkey, JSON.stringify(content));
    const eventTemplate = {
      kind: NWCWalletRequest,
      created_at: Math.round(Date.now() / 1e3),
      content: encryptedContent,
      tags: [["p", pubkey]]
    };
    return finalizeEvent(eventTemplate, secretKey);
  }

  // nip54.ts
  var nip54_exports = {};
  __export(nip54_exports, {
    normalizeIdentifier: () => normalizeIdentifier
  });
  function normalizeIdentifier(name) {
    name = name.trim().toLowerCase();
    name = name.normalize("NFKC");
    return Array.from(name).map((char) => {
      if (/\p{Letter}/u.test(char) || /\p{Number}/u.test(char)) {
        return char;
      }
      return "-";
    }).join("");
  }

  // nip57.ts
  var nip57_exports = {};
  __export(nip57_exports, {
    getSatoshisAmountFromBolt11: () => getSatoshisAmountFromBolt11,
    getZapEndpoint: () => getZapEndpoint,
    makeZapReceipt: () => makeZapReceipt,
    makeZapRequest: () => makeZapRequest,
    useFetchImplementation: () => useFetchImplementation4,
    validateZapRequest: () => validateZapRequest
  });
  var _fetch4;
  try {
    _fetch4 = fetch;
  } catch {
  }
  function useFetchImplementation4(fetchImplementation) {
    _fetch4 = fetchImplementation;
  }
  async function getZapEndpoint(metadata) {
    try {
      let lnurl = "";
      let { lud06, lud16 } = JSON.parse(metadata.content);
      if (lud16) {
        let [name, domain] = lud16.split("@");
        lnurl = new URL(`/.well-known/lnurlp/${name}`, `https://${domain}`).toString();
      } else if (lud06) {
        let { words } = bech32.decode(lud06, 1e3);
        let data = bech32.fromWords(words);
        lnurl = utf8Decoder.decode(data);
      } else {
        return null;
      }
      let res = await _fetch4(lnurl);
      let body = await res.json();
      if (body.allowsNostr && body.nostrPubkey) {
        return body.callback;
      }
    } catch (err) {
    }
    return null;
  }
  function makeZapRequest(params) {
    let zr = {
      kind: 9734,
      created_at: Math.round(Date.now() / 1e3),
      content: params.comment || "",
      tags: [
        ["p", "pubkey" in params ? params.pubkey : params.event.pubkey],
        ["amount", params.amount.toString()],
        ["relays", ...params.relays]
      ]
    };
    if ("event" in params) {
      zr.tags.push(["e", params.event.id]);
      if (isReplaceableKind(params.event.kind)) {
        const a = ["a", `${params.event.kind}:${params.event.pubkey}:`];
        zr.tags.push(a);
      } else if (isAddressableKind(params.event.kind)) {
        let d = params.event.tags.find(([t, v]) => t === "d" && v);
        if (!d)
          throw new Error("d tag not found or is empty");
        const a = ["a", `${params.event.kind}:${params.event.pubkey}:${d[1]}`];
        zr.tags.push(a);
      }
      zr.tags.push(["k", params.event.kind.toString()]);
    }
    return zr;
  }
  function validateZapRequest(zapRequestString) {
    let zapRequest;
    try {
      zapRequest = JSON.parse(zapRequestString);
    } catch (err) {
      return "Invalid zap request JSON.";
    }
    if (!validateEvent(zapRequest))
      return "Zap request is not a valid Nostr event.";
    if (!verifyEvent(zapRequest))
      return "Invalid signature on zap request.";
    let p = zapRequest.tags.find(([t, v]) => t === "p" && v);
    if (!p)
      return "Zap request doesn't have a 'p' tag.";
    if (!p[1].match(/^[a-f0-9]{64}$/))
      return "Zap request 'p' tag is not valid hex.";
    let e = zapRequest.tags.find(([t, v]) => t === "e" && v);
    if (e && !e[1].match(/^[a-f0-9]{64}$/))
      return "Zap request 'e' tag is not valid hex.";
    let relays = zapRequest.tags.find(([t, v]) => t === "relays" && v);
    if (!relays)
      return "Zap request doesn't have a 'relays' tag.";
    return null;
  }
  function makeZapReceipt({
    zapRequest,
    preimage,
    bolt11,
    paidAt
  }) {
    let zr = JSON.parse(zapRequest);
    let tagsFromZapRequest = zr.tags.filter(([t]) => t === "e" || t === "p" || t === "a");
    let zap = {
      kind: 9735,
      created_at: Math.round(paidAt.getTime() / 1e3),
      content: "",
      tags: [...tagsFromZapRequest, ["P", zr.pubkey], ["bolt11", bolt11], ["description", zapRequest]]
    };
    if (preimage) {
      zap.tags.push(["preimage", preimage]);
    }
    return zap;
  }
  function getSatoshisAmountFromBolt11(bolt11) {
    if (bolt11.length < 50) {
      return 0;
    }
    bolt11 = bolt11.substring(0, 50);
    const idx = bolt11.lastIndexOf("1");
    if (idx === -1) {
      return 0;
    }
    const hrp = bolt11.substring(0, idx);
    if (!hrp.startsWith("lnbc")) {
      return 0;
    }
    const amount = hrp.substring(4);
    if (amount.length < 1) {
      return 0;
    }
    const char = amount[amount.length - 1];
    const digit = char.charCodeAt(0) - "0".charCodeAt(0);
    const isDigit = digit >= 0 && digit <= 9;
    let cutPoint = amount.length - 1;
    if (isDigit) {
      cutPoint++;
    }
    if (cutPoint < 1) {
      return 0;
    }
    const num2 = parseInt(amount.substring(0, cutPoint));
    switch (char) {
      case "m":
        return num2 * 1e5;
      case "u":
        return num2 * 100;
      case "n":
        return num2 / 10;
      case "p":
        return num2 / 1e4;
      default:
        return num2 * 1e8;
    }
  }

  // nip77.ts
  var nip77_exports = {};
  __export(nip77_exports, {
    Negentropy: () => Negentropy,
    NegentropyStorageVector: () => NegentropyStorageVector,
    NegentropySync: () => NegentropySync
  });
  var PROTOCOL_VERSION = 97;
  var ID_SIZE = 32;
  var FINGERPRINT_SIZE = 16;
  var Mode = {
    Skip: 0,
    Fingerprint: 1,
    IdList: 2
  };
  var WrappedBuffer = class {
    _raw;
    length;
    constructor(buffer) {
      if (typeof buffer === "number") {
        this._raw = new Uint8Array(buffer);
        this.length = 0;
      } else if (buffer instanceof Uint8Array) {
        this._raw = new Uint8Array(buffer);
        this.length = buffer.length;
      } else {
        this._raw = new Uint8Array(512);
        this.length = 0;
      }
    }
    unwrap() {
      return this._raw.subarray(0, this.length);
    }
    get capacity() {
      return this._raw.byteLength;
    }
    extend(buf) {
      if (buf instanceof WrappedBuffer)
        buf = buf.unwrap();
      if (typeof buf.length !== "number")
        throw Error("bad length");
      const targetSize = buf.length + this.length;
      if (this.capacity < targetSize) {
        const oldRaw = this._raw;
        const newCapacity = Math.max(this.capacity * 2, targetSize);
        this._raw = new Uint8Array(newCapacity);
        this._raw.set(oldRaw);
      }
      this._raw.set(buf, this.length);
      this.length += buf.length;
    }
    shift() {
      const first = this._raw[0];
      this._raw = this._raw.subarray(1);
      this.length--;
      return first;
    }
    shiftN(n = 1) {
      const firstSubarray = this._raw.subarray(0, n);
      this._raw = this._raw.subarray(n);
      this.length -= n;
      return firstSubarray;
    }
  };
  function decodeVarInt(buf) {
    let res = 0;
    while (1) {
      if (buf.length === 0)
        throw Error("parse ends prematurely");
      let byte = buf.shift();
      res = res << 7 | byte & 127;
      if ((byte & 128) === 0)
        break;
    }
    return res;
  }
  function encodeVarInt(n) {
    if (n === 0)
      return new WrappedBuffer(new Uint8Array([0]));
    let o = [];
    while (n !== 0) {
      o.push(n & 127);
      n >>>= 7;
    }
    o.reverse();
    for (let i2 = 0; i2 < o.length - 1; i2++)
      o[i2] |= 128;
    return new WrappedBuffer(new Uint8Array(o));
  }
  function getByte(buf) {
    return getBytes(buf, 1)[0];
  }
  function getBytes(buf, n) {
    if (buf.length < n)
      throw Error("parse ends prematurely");
    return buf.shiftN(n);
  }
  var Accumulator = class {
    buf;
    constructor() {
      this.setToZero();
    }
    setToZero() {
      this.buf = new Uint8Array(ID_SIZE);
    }
    add(otherBuf) {
      let currCarry = 0, nextCarry = 0;
      let p = new DataView(this.buf.buffer);
      let po = new DataView(otherBuf.buffer);
      for (let i2 = 0; i2 < 8; i2++) {
        let offset = i2 * 4;
        let orig = p.getUint32(offset, true);
        let otherV = po.getUint32(offset, true);
        let next = orig;
        next += currCarry;
        next += otherV;
        if (next > 4294967295)
          nextCarry = 1;
        p.setUint32(offset, next & 4294967295, true);
        currCarry = nextCarry;
        nextCarry = 0;
      }
    }
    negate() {
      let p = new DataView(this.buf.buffer);
      for (let i2 = 0; i2 < 8; i2++) {
        let offset = i2 * 4;
        p.setUint32(offset, ~p.getUint32(offset, true));
      }
      let one = new Uint8Array(ID_SIZE);
      one[0] = 1;
      this.add(one);
    }
    getFingerprint(n) {
      let input = new WrappedBuffer();
      input.extend(this.buf);
      input.extend(encodeVarInt(n));
      let hash = sha256(input.unwrap());
      return hash.subarray(0, FINGERPRINT_SIZE);
    }
  };
  var NegentropyStorageVector = class {
    items;
    sealed;
    constructor() {
      this.items = [];
      this.sealed = false;
    }
    insert(timestamp, id) {
      if (this.sealed)
        throw Error("already sealed");
      const idb = hexToBytes(id);
      if (idb.byteLength !== ID_SIZE)
        throw Error("bad id size for added item");
      this.items.push({ timestamp, id: idb });
    }
    seal() {
      if (this.sealed)
        throw Error("already sealed");
      this.sealed = true;
      this.items.sort(itemCompare);
      for (let i2 = 1; i2 < this.items.length; i2++) {
        if (itemCompare(this.items[i2 - 1], this.items[i2]) === 0)
          throw Error("duplicate item inserted");
      }
    }
    unseal() {
      this.sealed = false;
    }
    size() {
      this._checkSealed();
      return this.items.length;
    }
    getItem(i2) {
      this._checkSealed();
      if (i2 >= this.items.length)
        throw Error("out of range");
      return this.items[i2];
    }
    iterate(begin, end, cb) {
      this._checkSealed();
      this._checkBounds(begin, end);
      for (let i2 = begin; i2 < end; ++i2) {
        if (!cb(this.items[i2], i2))
          break;
      }
    }
    findLowerBound(begin, end, bound) {
      this._checkSealed();
      this._checkBounds(begin, end);
      return this._binarySearch(this.items, begin, end, (a) => itemCompare(a, bound) < 0);
    }
    fingerprint(begin, end) {
      let out = new Accumulator();
      out.setToZero();
      this.iterate(begin, end, (item) => {
        out.add(item.id);
        return true;
      });
      return out.getFingerprint(end - begin);
    }
    _checkSealed() {
      if (!this.sealed)
        throw Error("not sealed");
    }
    _checkBounds(begin, end) {
      if (begin > end || end > this.items.length)
        throw Error("bad range");
    }
    _binarySearch(arr, first, last, cmp) {
      let count = last - first;
      while (count > 0) {
        let it = first;
        let step = Math.floor(count / 2);
        it += step;
        if (cmp(arr[it])) {
          first = ++it;
          count -= step + 1;
        } else {
          count = step;
        }
      }
      return first;
    }
  };
  var Negentropy = class {
    storage;
    frameSizeLimit;
    lastTimestampIn;
    lastTimestampOut;
    constructor(storage, frameSizeLimit = 6e4) {
      if (frameSizeLimit < 4096)
        throw Error("frameSizeLimit too small");
      this.storage = storage;
      this.frameSizeLimit = frameSizeLimit;
      this.lastTimestampIn = 0;
      this.lastTimestampOut = 0;
    }
    _bound(timestamp, id) {
      return { timestamp, id: id || new Uint8Array(0) };
    }
    initiate() {
      let output = new WrappedBuffer();
      output.extend(new Uint8Array([PROTOCOL_VERSION]));
      this.splitRange(0, this.storage.size(), this._bound(Number.MAX_VALUE), output);
      return bytesToHex(output.unwrap());
    }
    reconcile(queryMsg, onhave, onneed) {
      const query = new WrappedBuffer(hexToBytes(queryMsg));
      this.lastTimestampIn = this.lastTimestampOut = 0;
      let fullOutput = new WrappedBuffer();
      fullOutput.extend(new Uint8Array([PROTOCOL_VERSION]));
      let protocolVersion = getByte(query);
      if (protocolVersion < 96 || protocolVersion > 111)
        throw Error("invalid negentropy protocol version byte");
      if (protocolVersion !== PROTOCOL_VERSION) {
        throw Error("unsupported negentropy protocol version requested: " + (protocolVersion - 96));
      }
      let storageSize = this.storage.size();
      let prevBound = this._bound(0);
      let prevIndex = 0;
      let skip = false;
      while (query.length !== 0) {
        let o = new WrappedBuffer();
        let doSkip = () => {
          if (skip) {
            skip = false;
            o.extend(this.encodeBound(prevBound));
            o.extend(encodeVarInt(Mode.Skip));
          }
        };
        let currBound = this.decodeBound(query);
        let mode = decodeVarInt(query);
        let lower = prevIndex;
        let upper = this.storage.findLowerBound(prevIndex, storageSize, currBound);
        if (mode === Mode.Skip) {
          skip = true;
        } else if (mode === Mode.Fingerprint) {
          let theirFingerprint = getBytes(query, FINGERPRINT_SIZE);
          let ourFingerprint = this.storage.fingerprint(lower, upper);
          if (compareUint8Array(theirFingerprint, ourFingerprint) !== 0) {
            doSkip();
            this.splitRange(lower, upper, currBound, o);
          } else {
            skip = true;
          }
        } else if (mode === Mode.IdList) {
          let numIds = decodeVarInt(query);
          let theirElems = {};
          for (let i2 = 0; i2 < numIds; i2++) {
            let e = getBytes(query, ID_SIZE);
            theirElems[bytesToHex(e)] = e;
          }
          skip = true;
          this.storage.iterate(lower, upper, (item) => {
            let k = item.id;
            const id = bytesToHex(k);
            if (!theirElems[id]) {
              onhave?.(id);
            } else {
              delete theirElems[bytesToHex(k)];
            }
            return true;
          });
          if (onneed) {
            for (let v of Object.values(theirElems)) {
              onneed(bytesToHex(v));
            }
          }
        } else {
          throw Error("unexpected mode");
        }
        if (this.exceededFrameSizeLimit(fullOutput.length + o.length)) {
          let remainingFingerprint = this.storage.fingerprint(upper, storageSize);
          fullOutput.extend(this.encodeBound(this._bound(Number.MAX_VALUE)));
          fullOutput.extend(encodeVarInt(Mode.Fingerprint));
          fullOutput.extend(remainingFingerprint);
          break;
        } else {
          fullOutput.extend(o);
        }
        prevIndex = upper;
        prevBound = currBound;
      }
      return fullOutput.length === 1 ? null : bytesToHex(fullOutput.unwrap());
    }
    splitRange(lower, upper, upperBound, o) {
      let numElems = upper - lower;
      let buckets = 16;
      if (numElems < buckets * 2) {
        o.extend(this.encodeBound(upperBound));
        o.extend(encodeVarInt(Mode.IdList));
        o.extend(encodeVarInt(numElems));
        this.storage.iterate(lower, upper, (item) => {
          o.extend(item.id);
          return true;
        });
      } else {
        let itemsPerBucket = Math.floor(numElems / buckets);
        let bucketsWithExtra = numElems % buckets;
        let curr = lower;
        for (let i2 = 0; i2 < buckets; i2++) {
          let bucketSize = itemsPerBucket + (i2 < bucketsWithExtra ? 1 : 0);
          let ourFingerprint = this.storage.fingerprint(curr, curr + bucketSize);
          curr += bucketSize;
          let nextBound;
          if (curr === upper) {
            nextBound = upperBound;
          } else {
            let prevItem;
            let currItem;
            this.storage.iterate(curr - 1, curr + 1, (item, index) => {
              if (index === curr - 1)
                prevItem = item;
              else
                currItem = item;
              return true;
            });
            nextBound = this.getMinimalBound(prevItem, currItem);
          }
          o.extend(this.encodeBound(nextBound));
          o.extend(encodeVarInt(Mode.Fingerprint));
          o.extend(ourFingerprint);
        }
      }
    }
    exceededFrameSizeLimit(n) {
      return n > this.frameSizeLimit - 200;
    }
    decodeTimestampIn(encoded) {
      let timestamp = decodeVarInt(encoded);
      timestamp = timestamp === 0 ? Number.MAX_VALUE : timestamp - 1;
      if (this.lastTimestampIn === Number.MAX_VALUE || timestamp === Number.MAX_VALUE) {
        this.lastTimestampIn = Number.MAX_VALUE;
        return Number.MAX_VALUE;
      }
      timestamp += this.lastTimestampIn;
      this.lastTimestampIn = timestamp;
      return timestamp;
    }
    decodeBound(encoded) {
      let timestamp = this.decodeTimestampIn(encoded);
      let len = decodeVarInt(encoded);
      if (len > ID_SIZE)
        throw Error("bound key too long");
      let id = getBytes(encoded, len);
      return { timestamp, id };
    }
    encodeTimestampOut(timestamp) {
      if (timestamp === Number.MAX_VALUE) {
        this.lastTimestampOut = Number.MAX_VALUE;
        return encodeVarInt(0);
      }
      let temp = timestamp;
      timestamp -= this.lastTimestampOut;
      this.lastTimestampOut = temp;
      return encodeVarInt(timestamp + 1);
    }
    encodeBound(key) {
      let output = new WrappedBuffer();
      output.extend(this.encodeTimestampOut(key.timestamp));
      output.extend(encodeVarInt(key.id.length));
      output.extend(key.id);
      return output;
    }
    getMinimalBound(prev, curr) {
      if (curr.timestamp !== prev.timestamp) {
        return this._bound(curr.timestamp);
      } else {
        let sharedPrefixBytes = 0;
        let currKey = curr.id;
        let prevKey = prev.id;
        for (let i2 = 0; i2 < ID_SIZE; i2++) {
          if (currKey[i2] !== prevKey[i2])
            break;
          sharedPrefixBytes++;
        }
        return this._bound(curr.timestamp, curr.id.subarray(0, sharedPrefixBytes + 1));
      }
    }
  };
  function compareUint8Array(a, b) {
    for (let i2 = 0; i2 < a.byteLength; i2++) {
      if (a[i2] < b[i2])
        return -1;
      if (a[i2] > b[i2])
        return 1;
    }
    if (a.byteLength > b.byteLength)
      return 1;
    if (a.byteLength < b.byteLength)
      return -1;
    return 0;
  }
  function itemCompare(a, b) {
    if (a.timestamp === b.timestamp) {
      return compareUint8Array(a.id, b.id);
    }
    return a.timestamp - b.timestamp;
  }
  var NegentropySync = class {
    relay;
    storage;
    neg;
    filter;
    subscription;
    onhave;
    onneed;
    constructor(relay, storage, filter, params = {}) {
      this.relay = relay;
      this.storage = storage;
      this.neg = new Negentropy(storage);
      this.onhave = params.onhave;
      this.onneed = params.onneed;
      this.filter = filter;
      this.subscription = this.relay.prepareSubscription([{}], { label: params.label || "negentropy" });
      this.subscription.oncustom = (data) => {
        switch (data[0]) {
          case "NEG-MSG": {
            if (data.length < 3) {
              console.warn(`got invalid NEG-MSG from ${this.relay.url}: ${data}`);
            }
            try {
              const response = this.neg.reconcile(data[2], this.onhave, this.onneed);
              if (response) {
                this.relay.send(`["NEG-MSG", "${this.subscription.id}", "${response}"]`);
              } else {
                this.close();
                params.onclose?.();
              }
            } catch (error) {
              console.error("negentropy reconcile error:", error);
              params?.onclose?.(`reconcile error: ${error}`);
            }
            break;
          }
          case "NEG-CLOSE": {
            const reason = data[2];
            console.warn("negentropy error:", reason);
            params.onclose?.(reason);
            break;
          }
          case "NEG-ERR": {
            params.onclose?.();
          }
        }
      };
    }
    async start() {
      const initMsg = this.neg.initiate();
      this.relay.send(`["NEG-OPEN","${this.subscription.id}",${JSON.stringify(this.filter)},"${initMsg}"]`);
    }
    close() {
      this.relay.send(`["NEG-CLOSE","${this.subscription.id}"]`);
      this.subscription.close();
    }
  };

  // nip98.ts
  var nip98_exports = {};
  __export(nip98_exports, {
    getToken: () => getToken,
    hashPayload: () => hashPayload,
    unpackEventFromToken: () => unpackEventFromToken,
    validateEvent: () => validateEvent2,
    validateEventKind: () => validateEventKind,
    validateEventMethodTag: () => validateEventMethodTag,
    validateEventPayloadTag: () => validateEventPayloadTag,
    validateEventTimestamp: () => validateEventTimestamp,
    validateEventUrlTag: () => validateEventUrlTag,
    validateToken: () => validateToken
  });
  var _authorizationScheme = "Nostr ";
  async function getToken(loginUrl, httpMethod, sign, includeAuthorizationScheme = false, payload) {
    const event = {
      kind: HTTPAuth,
      tags: [
        ["u", loginUrl],
        ["method", httpMethod]
      ],
      created_at: Math.round(new Date().getTime() / 1e3),
      content: ""
    };
    if (payload) {
      event.tags.push(["payload", hashPayload(payload)]);
    }
    const signedEvent = await sign(event);
    const authorizationScheme = includeAuthorizationScheme ? _authorizationScheme : "";
    return authorizationScheme + base64.encode(utf8Encoder.encode(JSON.stringify(signedEvent)));
  }
  async function validateToken(token, url, method) {
    const event = await unpackEventFromToken(token).catch((error) => {
      throw error;
    });
    const valid = await validateEvent2(event, url, method).catch((error) => {
      throw error;
    });
    return valid;
  }
  async function unpackEventFromToken(token) {
    if (!token) {
      throw new Error("Missing token");
    }
    token = token.replace(_authorizationScheme, "");
    const eventB64 = utf8Decoder.decode(base64.decode(token));
    if (!eventB64 || eventB64.length === 0 || !eventB64.startsWith("{")) {
      throw new Error("Invalid token");
    }
    const event = JSON.parse(eventB64);
    return event;
  }
  function validateEventTimestamp(event) {
    if (!event.created_at) {
      return false;
    }
    return Math.round(new Date().getTime() / 1e3) - event.created_at < 60;
  }
  function validateEventKind(event) {
    return event.kind === HTTPAuth;
  }
  function validateEventUrlTag(event, url) {
    const urlTag = event.tags.find((t) => t[0] === "u");
    if (!urlTag) {
      return false;
    }
    return urlTag.length > 0 && urlTag[1] === url;
  }
  function validateEventMethodTag(event, method) {
    const methodTag = event.tags.find((t) => t[0] === "method");
    if (!methodTag) {
      return false;
    }
    return methodTag.length > 0 && methodTag[1].toLowerCase() === method.toLowerCase();
  }
  function hashPayload(payload) {
    const hash = sha256(utf8Encoder.encode(JSON.stringify(payload)));
    return bytesToHex(hash);
  }
  function validateEventPayloadTag(event, payload) {
    const payloadTag = event.tags.find((t) => t[0] === "payload");
    if (!payloadTag) {
      return false;
    }
    const payloadHash = hashPayload(payload);
    return payloadTag.length > 0 && payloadTag[1] === payloadHash;
  }
  async function validateEvent2(event, url, method, body) {
    if (!verifyEvent(event)) {
      throw new Error("Invalid nostr event, signature invalid");
    }
    if (!validateEventKind(event)) {
      throw new Error("Invalid nostr event, kind invalid");
    }
    if (!validateEventTimestamp(event)) {
      throw new Error("Invalid nostr event, created_at timestamp invalid");
    }
    if (!validateEventUrlTag(event, url)) {
      throw new Error("Invalid nostr event, url tag invalid");
    }
    if (!validateEventMethodTag(event, method)) {
      throw new Error("Invalid nostr event, method tag invalid");
    }
    if (Boolean(body) && typeof body === "object" && Object.keys(body).length > 0) {
      if (!validateEventPayloadTag(event, body)) {
        throw new Error("Invalid nostr event, payload tag does not match request body hash");
      }
    }
    return true;
  }
  return __toCommonJS(nostr_tools_exports);
})();
