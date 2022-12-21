function splitAmount(value) {
  const chunks = []
  for (let i = 0; i < 32; i++) {
    const mask = 1 << i
    if ((value & mask) !== 0) chunks.push(Math.pow(2, i))
  }
  return chunks
}

function bytesToNumber(bytes) {
  return hexToNumber(nobleSecp256k1.utils.bytesToHex(bytes))
}

function bigIntStringify(key, value) {
  return typeof value === 'bigint' ? value.toString() : value
}

function hexToNumber(hex) {
  if (typeof hex !== 'string') {
    throw new TypeError('hexToNumber: expected string, got ' + typeof hex)
  }
  return BigInt(`0x${hex}`)
}
