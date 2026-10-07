export const PSBT_BASE64_PREFIX = 'cHNidP8'

export const COMMAND_PING = '/ping'
export const COMMAND_PASSWORD = '/password'
export const COMMAND_PASSWORD_CLEAR = '/password-clear'
export const COMMAND_ADDRESS = '/address'
export const COMMAND_SEND_PSBT = '/psbt'
export const COMMAND_PSBT_BEGIN = '/psbt-begin'
export const COMMAND_PSBT_CHUNK = '/psbt-chunk'
export const COMMAND_PSBT_COMMIT = '/psbt-commit'
export const COMMAND_PSBT_REVIEW = '/psbt-review'
export const COMMAND_NEW = '/new'
export const COMMAND_SIGN_PSBT = '/sign'
export const COMMAND_HELP = '/help'
export const COMMAND_WIPE = '/wipe'
export const COMMAND_SEED = '/seed'
export const COMMAND_TRNG = '/trng'
export const COMMAND_RESTORE = '/restore'
export const COMMAND_CONFIRM_NEXT = '/confirm-next'
export const COMMAND_CANCEL = '/cancel'
export const COMMAND_XPUB = '/xpub'
export const COMMAND_PAIR = '/pair'
export const COMMAND_LOG = '/log'

export const DEFAULT_RECEIVE_GAP_LIMIT = 20

// Testnet3 and Testnet4 share key/address formats and hardware signing rules.
export const getSigningNetwork = network =>
  network === 'Testnet4' ? 'Testnet' : network

export const HWW_DEFAULT_CONFIG = Object.freeze({
  name: '',
  baudRate: 9600,
  bufferSize: 255,
  dataBits: 8,
  flowControl: 'none',
  parity: 'none',
  stopBits: 1
})

export const blockTimeToDate = blockTime =>
  blockTime ? moment(blockTime * 1000).format('LLL') : ''

export const currentDateTime = () => moment().format('LLL')

export const sleep = ms => new Promise(r => setTimeout(r, ms))

export const retryWithDelay = async function (fn, retryCount = 0) {
  try {
    await sleep(25)
    // Do not return the call directly, use result.
    // Otherwise the error will not be cought in this try-catch block.
    const result = await fn()
    return result
  } catch (err) {
    if (retryCount >= 2) throw err
    await sleep((retryCount + 1) * 1000)
    return retryWithDelay(fn, retryCount + 1)
  }
}

export const txSize = tx => {
  // https://bitcoinops.org/en/tools/calc-size/
  // overhead size
  const nVersion = 4
  const inCount = 1
  const outCount = 1
  const nlockTime = 4
  const hasSegwit = !!tx.inputs.find(inp =>
    ['p2wsh', 'p2wpkh', 'p2tr'].includes(inp.accountType)
  )
  const segwitFlag = hasSegwit ? 0.5 : 0
  const overheadSize = nVersion + inCount + outCount + nlockTime + segwitFlag

  // inputs size
  const outpoint = 36 // txId plus vout index number
  const scriptSigLength = 1
  const nSequence = 4
  const inputsSize = tx.inputs.reduce((t, inp) => {
    const scriptSig =
      inp.accountType === 'p2pkh' ? 107 : inp.accountType === 'p2sh' ? 254 : 0
    const witnessItemCount = hasSegwit ? 0.25 : 0
    const witnessItems =
      inp.accountType === 'p2wpkh'
        ? 27
        : inp.accountType === 'p2wsh'
          ? 63.5
          : inp.accountType === 'p2tr'
            ? 16.5
            : 0
    t +=
      outpoint +
      scriptSigLength +
      nSequence +
      scriptSig +
      witnessItemCount +
      witnessItems
    return t
  }, 0)

  // outputs size
  const nValue = 8
  const scriptPubKeyLength = 1

  const outputsSize = tx.outputs.reduce((t, out) => {
    const type = guessAddressType(out.address)

    const scriptPubKey =
      type === 'p2pkh'
        ? 25
        : type === 'p2wpkh'
          ? 22
          : type === 'p2sh'
            ? 23
            : type === 'p2wsh'
              ? 34
              : 34 // default to the largest size (p2tr included)
    t += nValue + scriptPubKeyLength + scriptPubKey
    return t
  }, 0)

  return overheadSize + inputsSize + outputsSize
}
export const guessAddressType = (a = '') => {
  if (a.startsWith('1') || a.startsWith('n')) return 'p2pkh'
  if (a.startsWith('3') || a.startsWith('2')) return 'p2sh'
  if (a.startsWith('bc1q') || a.startsWith('tb1q'))
    return a.length === 42 ? 'p2wpkh' : 'p2wsh'
  if (a.startsWith('bc1p') || a.startsWith('tb1p')) return 'p2tr'
}

export const ACCOUNT_TYPES = {
  p2tr: 'Taproot, BIP86, P2TR, Bech32m',
  p2wpkh: 'SegWit, BIP84, P2WPKH, Bech32',
  p2sh: 'BIP49, P2SH-P2WPKH, Base58',
  p2pkh: 'Legacy, BIP44, P2PKH, Base58'
}

export const getAccountDescription = type =>
  ACCOUNT_TYPES[type] || 'nonstandard'

export const readFromSerialPort = reader => {
  let partialChunk
  let fulliness = []

  const readStringUntil = async (separator = '\n') => {
    if (fulliness.length) return {value: fulliness.shift().trim(), done: false}
    const chunks = []
    if (partialChunk) {
      // leftovers from previous read
      chunks.push(partialChunk)
      partialChunk = undefined
    }
    while (true) {
      const {value, done} = await reader.read()
      if (value) {
        const values = value.split(separator)
        // found one or more separators
        if (values.length > 1) {
          chunks.push(values.shift()) // first element
          partialChunk = values.pop() // last element
          fulliness = values // full lines
          return {value: chunks.join('').trim(), done: false}
        }
        chunks.push(value)
      }
      if (done) return {value: chunks.join('').trim(), done: true}
    }
  }
  return readStringUntil
}

export function satOrBtc(val, showUnit = true, showSats = false) {
  const value = showSats
    ? LNbits.utils.formatSat(val)
    : val == 0
      ? 0.0
      : (val / 100000000).toFixed(8)
  if (!showUnit) return value
  return showSats ? value + ' sat' : value + ' BTC'
}

export function loadTemplateAsync(path) {
  const result = new Promise(resolve => {
    const xhttp = new XMLHttpRequest()

    xhttp.onreadystatechange = function () {
      if (this.readyState == 4) {
        if (this.status == 200) resolve(this.responseText)

        if (this.status == 404) resolve(`<div>Page not found: ${path}</div>`)
      }
    }

    xhttp.open('GET', path, true)
    xhttp.send()
  })

  return result
}

export function findAccountPathIssues(path = '') {
  const p = path.split('/')
  if (p[0] !== 'm') return "Path must start with 'm/'"
  for (let i = 1; i < p.length; i++) {
    if (!/^\d+'?$/.test(p[i]) || Number(p[i].replace("'", '')) >= 0x80000000)
      return `${p[i]} is not a valid value`
  }
}

export function asciiToUint8Array(str) {
  var chars = []
  for (var i = 0; i < str.length; ++i) {
    chars.push(str.charCodeAt(i))
  }
  return new Uint8Array(chars)
}

// Parse BIP21 amounts as decimal satoshis, without floating-point rounding.
export function parseBitcoinRequest(value) {
  const text = value.trim()
  if (!/^bitcoin:/i.test(text)) return {address: text}
  const request = text.slice(8)
  const [encodedAddress, query = ''] = request.split('?')
  const params = new URLSearchParams(query)
  if (
    !encodedAddress ||
    encodedAddress.startsWith('//') ||
    request.includes('#')
  )
    throw new Error('Invalid bitcoin payment link')
  for (const key of params.keys()) {
    if (key.startsWith('req-'))
      throw new Error('This payment link requires an unsupported feature')
  }
  if (params.getAll('amount').length > 1)
    throw new Error('Payment link contains more than one amount')
  const result = {address: decodeURIComponent(encodedAddress)}
  if (params.has('amount')) {
    const amount = params.get('amount')
    if (!/^\d+(\.\d{1,8})?$/.test(amount))
      throw new Error('Payment link has an invalid bitcoin amount')
    const [whole, fraction = ''] = amount.split('.')
    const sats = Number(whole) * 100000000 + Number(fraction.padEnd(8, '0'))
    if (!Number.isSafeInteger(sats) || sats <= 0 || sats > 2100000000000000)
      throw new Error('Payment link amount is out of range')
    result.amount = sats
  }
  return result
}

// Single-path descriptors can expose the same address on both logical branches.
export function addressBalance(addresses) {
  const amounts = new Map()
  for (const address of addresses) {
    amounts.set(
      address.address,
      Math.max(amounts.get(address.address) || 0, address.amount)
    )
  }
  return [...amounts.values()].reduce((total, amount) => total + amount, 0)
}
