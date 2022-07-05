const blockTimeToDate = blockTime =>
  blockTime ? moment(blockTime * 1000).format('LLL') : ''

const currentDateTime = () => moment().format('LLL')

const sleep = ms => new Promise(r => setTimeout(r, ms))

const retryWithDelay = async function (fn, retryCount = 0) {
  try {
    await sleep(25)
    // Do not return the call directly, use result.
    // Otherwise the error will not be cought in this try-catch block.
    const result = await fn()
    return result
  } catch (err) {
    if (retryCount > 100) throw err
    await sleep((retryCount + 1) * 1000)
    return retryWithDelay(fn, retryCount + 1)
  }
}

const txSize = tx => {
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
const guessAddressType = (a = '') => {
  if (a.startsWith('1') || a.startsWith('n')) return 'p2pkh'
  if (a.startsWith('3') || a.startsWith('2')) return 'p2sh'
  if (a.startsWith('bc1q') || a.startsWith('tb1q'))
    return a.length === 42 ? 'p2wpkh' : 'p2wsh'
  if (a.startsWith('bc1p') || a.startsWith('tb1p')) return 'p2tr'
}

const ACCOUNT_TYPES = {
  p2tr: 'Taproot, BIP86, P2TR, Bech32m',
  p2wpkh: 'SegWit, BIP84, P2WPKH, Bech32',
  p2sh: 'BIP49, P2SH-P2WPKH, Base58',
  p2pkh: 'Legacy, BIP44, P2PKH, Base58'
}

const getAccountDescription = type => ACCOUNT_TYPES[type] || 'nonstandard'
