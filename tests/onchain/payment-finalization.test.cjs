const assert = require('node:assert/strict')
const {readFileSync} = require('./source.cjs')
const {resolve} = require('node:path')
const {test} = require('node:test')
const vm = require('node:vm')

function harness(request) {
  let component
  const events = []
  const context = {
    window: {app: {component: (_, value) => (component = value)}},
    LNbits: {api: {request}, utils: {notifyApiError() {}}}
  }
  vm.runInNewContext(
    readFileSync(
      resolve(__dirname, '../../lnbits/onchain/static/components/payment.js'),
      'utf8'
    ),
    context
  )
  const instance = {
    ...component.data(),
    network: 'Testnet',
    adminkey: 'test-key',
    $q: {notify() {}},
    $emit: (...args) => events.push(args)
  }
  for (const [key, method] of Object.entries(component.methods))
    instance[key] = method.bind(instance)
  return {instance, events}
}

test('broadcast stays busy, rejects duplicate clicks and allows retry after failure', async () => {
  let finish
  let calls = 0
  const {instance: payment, events} = harness(() => {
    calls++
    return new Promise((resolve, reject) => {
      finish = {resolve, reject}
    })
  })
  payment.signedTxHex = 'signed-hex'
  payment.showFinalTx = true
  const first = payment.broadcastTransaction()
  assert.equal(payment.showChecking, true)
  await payment.broadcastTransaction()
  assert.equal(calls, 1)
  finish.reject(new Error('Connection failed'))
  await first
  assert.equal(payment.showChecking, false)
  assert.equal(payment.showFinalTx, true)
  assert.equal(payment.signedTxHex, 'signed-hex')
  const retry = payment.broadcastTransaction()
  finish.resolve({data: 'broadcast-txid'})
  await retry
  assert.equal(payment.showChecking, false)
  assert.equal(payment.showFinalTx, false)
  assert.equal(events.length, 1)
  assert.equal(events[0][1], 'broadcast-txid')
})

test('clearing the last change account resets its address without throwing', () => {
  const {instance: payment} = harness()
  payment.accounts = []
  payment.addresses = []
  payment.changeWallet = {id: 'removed-account'}
  payment.changeAddress = {address: 'old-address'}
  payment.updateChangeAddress()
  assert.equal(payment.changeWallet, undefined)
  assert.equal(payment.changeAddress.address, undefined)
})

test('signed PSBT posts the browser payload and opens only the finalized transaction', async () => {
  const calls = []
  const {instance: payment} = harness(async (...args) => {
    calls.push(args)
    return {data: {tx_hex: 'signed-hex', tx_json: '{"fee":141}'}}
  })
  payment.tx = {inputs: [{tx_hex: 'previous-tx'}]}
  payment.psbtBase64 = 'unsigned-psbt'
  await payment.updateSignedPsbt('signed-psbt')
  assert.equal(calls[0][1], '/onchain/api/v1/psbt/extract')
  assert.equal(calls[0][3].psbtBase64, 'signed-psbt')
  assert.equal(calls[0][3].expectedPsbtBase64, 'unsigned-psbt')
  assert.equal(calls[0][3].inputs[0].tx_hex, 'previous-tx')
  assert.equal(payment.showFinalTx, true)
  assert.equal(payment.signedTxHex, 'signed-hex')
  assert.equal(payment.signedTx.fee, 141)
  assert.equal(payment.showChecking, false)
})

for (const failure of ['http-error', 'empty-hex']) {
  test(`PSBT finalization ${failure} clears stale transaction and prevents broadcast`, async () => {
    const calls = []
    const {instance: payment} = harness(async (...args) => {
      calls.push(args)
      if (failure === 'http-error') throw new Error('HTTP 400')
      return {data: {tx_hex: '', tx_json: '{}'}}
    })
    Object.assign(payment, {
      tx: {inputs: []},
      showFinalTx: true,
      signedTx: {fee: 99},
      signedTxHex: 'previous-signed-hex'
    })
    payment.fetchUtxoHexForPsbt = async () => []
    await payment.updateSignedPsbt('signed-psbt')
    assert.equal(payment.psbtBase64Signed, 'signed-psbt')
    assert.equal(payment.showFinalTx, false)
    assert.equal(payment.signedTx, null)
    assert.equal(payment.signedTxHex, null)
    assert.equal(payment.showChecking, false)
    await payment.broadcastTransaction()
    assert.equal(calls.length, 1)
  })
}

test('A failed PSBT build cannot sign a previously exported transaction', async () => {
  const {instance: payment} = harness(async () => {
    throw new Error('HTTP 400')
  })
  payment.psbtBase64 = 'stale-psbt'
  payment.utxos = []
  payment.createTx = () => ({inputs: [], outputs: []})
  payment.serialSignerRef = {
    isConnected: () => true,
    isAuthenticated: () => true,
    hwwSendPsbt: () => assert.fail('Must not sign a stale PSBT')
  }
  await payment.checkAndSend()
  assert.equal(payment.psbtBase64, null)
})

test('Imported PSBTs fetch their own previous transactions instead of stale payment inputs', async () => {
  const {instance: payment} = harness(async () => ({
    data: [{tx_id: 'imported-txid'}]
  }))
  payment.tx = {inputs: [{tx_hex: 'stale-transaction'}]}
  payment.fetchTxHex = async txid => {
    assert.equal(txid, 'imported-txid')
    return 'imported-previous-transaction'
  }
  const inputs = await payment.fetchUtxoHexForPsbt('imported-psbt')
  assert.equal(inputs[0].tx_hex, 'imported-previous-transaction')
})

test('PSBT matching keeps the reviewed transaction across asynchronous finalization', async () => {
  let payload
  const {instance: payment} = harness(async (...args) => {
    payload = args[3]
    return {data: {tx_hex: 'signed-hex', tx_json: '{}'}}
  })
  payment.psbtBase64 = 'original-psbt'
  payment.fetchUtxoHexForPsbt = async () => {
    payment.psbtBase64 = null
    return []
  }
  await payment.updateSignedPsbt('signed-psbt')
  assert.equal(payload.expectedPsbtBase64, 'original-psbt')
})

test('Signing stays busy until asynchronous finalization completes', async () => {
  let finish
  let finalization
  const {instance: payment} = harness(
    async () =>
      new Promise(resolve => {
        finish = resolve
      })
  )
  payment.utxos = []
  payment.createPsbt = async () => {
    payment.tx = {
      inputs: [{amount: 10000}],
      outputs: [{amount: 9000}],
      fee_rate: 1
    }
    payment.psbtBase64 = 'unsigned-psbt'
  }
  payment.serialSignerRef = {
    isConnected: () => true,
    isAuthenticated: () => true,
    hwwSendPsbt: async () => {
      finalization = payment.updateSignedPsbt('signed-psbt')
    },
    isSendingPsbt: async () => false
  }
  await payment.checkAndSend()
  assert.equal(payment.showChecking, true)
  finish({data: {tx_hex: 'signed-hex', tx_json: '{}'}})
  await finalization
  assert.equal(payment.showChecking, false)
  assert.equal(payment.signedTxHex, 'signed-hex')
})

test('Change amount is captured before fetching previous transactions', async () => {
  let payload
  const {instance: payment} = harness(async (...args) => {
    payload = args[3]
    return {data: 'unsigned-psbt'}
  })
  payment.changeAmount = 1234
  payment.createTx = () => ({
    inputs: [{tx_id: 'txid'}],
    outputs: [{branch_index: 1}]
  })
  payment.fetchTxHex = async () => {
    payment.changeAmount = 9876
    return 'previous-transaction'
  }
  await payment.createPsbt()
  assert.equal(payload.outputs[0].amount, 1234)
})

test('broadcast waits for finalization and still accepts native Trezor transactions', async () => {
  const calls = []
  const {instance: payment, events} = harness(async (...args) => {
    calls.push(args)
    if (args[1] === '/onchain/api/v1/tx/extract')
      return {data: {tx_json: {outputs: []}}}
    return {data: 'txid'}
  })
  await payment.updateSignedTx({serializedTx: 'trezor-hex', feeValue: 141})
  payment.showChecking = true
  await payment.broadcastTransaction()
  assert.equal(calls.length, 1)
  payment.showChecking = false
  await payment.broadcastTransaction()
  assert.equal(calls[1][0], 'POST')
  assert.equal(calls[1][3].tx_hex, 'trezor-hex')
  assert.deepEqual(events, [['broadcast-done', 'txid']])
})
