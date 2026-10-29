const assert = require('node:assert/strict')
const {readFileSync} = require('node:fs')
const {resolve} = require('node:path')
const {test} = require('node:test')
const vm = require('node:vm')

function harness() {
  let component
  const calls = []
  const document = {hidden: false}
  const context = {
    window: {
      app: {
        component: (_, c) => {
          component = c
        }
      }
    },
    document,
    _: {shuffle: list => list.slice().reverse()},
    LNbits: {
      api: {
        async request(method, path) {
          calls.push(path)
          return {
            data: {mnemonic: Array(23).fill('abandon').join(' ') + ' art'}
          }
        }
      }
    }
  }
  vm.runInNewContext(
    readFileSync(
      resolve(
        __dirname,
        '../../lnbits/static/js/components/onchain/hot-wallet.js'
      ),
      'utf8'
    ),
    context
  )
  const instance = {
    ...component.data(),
    $emit() {},
    adminkey: 'test-key',
    network: 'Mainnet',
    g: {wallet: {name: 'Bitcoin wallet'}}
  }
  for (const [name, fn] of Object.entries(component.methods))
    instance[name] = fn.bind(instance)
  for (const [name, fn] of Object.entries(component.computed))
    Object.defineProperty(instance, name, {get: () => fn.call(instance)})
  instance.openBackup({id: 'wallet', name: 'Test'})
  return {instance, calls, document, context}
}

test('backup requires four correct words before confirming and clears secrets on completion', async () => {
  const {instance, calls} = harness()
  assert.equal(instance.wordsVisible, false)
  assert.equal(instance.phrase, '')
  instance.prepareChallenge()
  assert.equal(instance.backupStep, 1)
  await instance.revealBackup()
  instance.prepareChallenge()
  assert.equal(instance.wordsVisible, false)
  assert.equal(instance.backupStep, 2)
  assert.equal(new Set(instance.challenge).size, 4)
  await instance.confirmBackup()
  assert.match(instance.error, /incorrect/)
  assert.equal(calls.length, 1)
  for (const index of instance.challenge)
    instance.answers[index] =
      ' ' + instance.seedWords[index].word.toUpperCase() + ' '
  await instance.confirmBackup()
  assert.equal(calls[1], '/api/v1/onchain/hot-wallet/wallet/backup/confirm')
  assert.equal(instance.show, false)
  assert.equal(instance.phrase, '')
  assert.equal(instance.challenge.length, 0)
  assert.equal(Object.keys(instance.answers).length, 0)
})

test('hiding the page clears the phrase, answers, and verification step', async () => {
  const {instance, document, calls} = harness()
  await instance.revealBackup()
  instance.prepareChallenge()
  instance.answers[0] = 'abandon'
  document.hidden = true
  instance.hideSecrets()
  assert.equal(instance.backupStep, 1)
  assert.equal(instance.phrase, '')
  assert.equal(instance.wordsVisible, false)
  assert.equal(Object.keys(instance.answers).length, 0)
  await instance.confirmBackup()
  assert.equal(calls.length, 1)
})

test('late backup responses cannot reveal secrets after closing and reopening', async () => {
  const {instance, context} = harness()
  let finish
  context.LNbits.api.request = () =>
    new Promise(resolve => {
      finish = resolve
    })
  const reveal = instance.revealBackup()
  instance.resetSecrets()
  instance.openBackup({id: 'different-wallet'})
  finish({data: {mnemonic: 'abandon '.repeat(11) + 'about'}})
  await reveal
  assert.equal(instance.phrase, '')
  assert.equal(instance.wordsVisible, false)
})

test('restored twelve-word phrases use their actual length and Back masks the grid', async () => {
  const {instance} = harness()
  instance.phrase = 'abandon '.repeat(11) + 'about'
  instance.prepareChallenge()
  assert.equal(instance.seedWords.length, 12)
  assert.ok(instance.challenge.every(index => index < 12))
  instance.answers[11] = 'about'
  instance.backToWords()
  assert.equal(instance.wordsVisible, false)
  assert.equal(instance.backupStep, 1)
  assert.equal(Object.keys(instance.answers).length, 0)
})

test('standard hot wallet paths follow the selected address type and network', () => {
  const {instance} = harness()
  assert.equal(instance.scriptType, 'p2wpkh')
  assert.equal(instance.accountPath, "m/84'/0'/0'")
  for (const network of ['Mainnet', 'Testnet', 'Testnet4']) {
    instance.network = network
    for (const [type, purpose] of [
      ['p2pkh', 44],
      ['p2sh', 49],
      ['p2wpkh', 84],
      ['p2tr', 86]
    ]) {
      instance.scriptType = type
      const coin = network === 'Mainnet' ? 0 : 1
      assert.equal(instance.accountPath, `m/${purpose}'/${coin}'/0'`)
    }
  }
  instance.useCustomPath = true
  instance.customPath = " m/84'/0'/7' "
  instance.scriptType = 'p2pkh'
  assert.equal(instance.accountPath, "m/84'/0'/7'")
})

test('custom path validation rejects invalid indexes and receiving/change suffixes', async () => {
  const {instance, calls} = harness()
  for (const path of ["m/84'/0'/7'", 'm/84h/0H/7h', "m/0'", "m/100'/7/3'"])
    assert.equal(instance.validateAccountPath(path), true)
  for (const path of [
    '',
    'm',
    "84'/0'/0'",
    "m/84'/0'/-1'",
    "m/84'/0'/2147483648'",
    "m/84'/0'/0'/0/0",
    "m/84'/0'/0'/1",
    "m/84'/0'/0'/*",
    "m/84'/0'/0'/<0;1>/*",
    "m/84'/0'/0'/",
    'm' + "/0'".repeat(254)
  ]) {
    instance.useCustomPath = true
    instance.customPath = path
    await instance.createWallet()
    assert.ok(instance.error)
  }
  assert.equal(calls.length, 0)
})

for (const mode of ['create', 'restore']) {
  test(`${mode} sends the selected type and custom path and shows saved backup information`, async () => {
    const {instance, context} = harness()
    instance.mode = mode
    instance.scriptType = 'p2tr'
    instance.useCustomPath = true
    instance.customPath = "m/86'/0'/7'"
    instance.mnemonic = 'abandon '.repeat(11) + 'about'
    const requests = []
    context.LNbits.api.request = async (...args) => {
      requests.push(args)
      return {
        data: {
          id: 'wallet',
          onchain_meta: {script_type: 'p2tr', accountPath: "m/86'/0'/7'"}
        }
      }
    }
    await instance.createWallet()
    const [method, path, key, body, options] = requests[0]
    assert.equal(method, 'POST')
    assert.equal(path, '/api/v1/onchain/hot-wallet')
    assert.equal(key, 'test-key')
    assert.equal(body.script_type, 'p2tr')
    assert.equal(body.account_path, "m/86'/0'/7'")
    assert.equal(body.title, 'Bitcoin wallet')
    assert.equal(body.mnemonic, undefined)
    assert.equal(
      options.headers?.['X-Onchain-Recovery-Phrase'],
      mode === 'restore' ? 'abandon '.repeat(11) + 'about' : undefined
    )
    assert.equal(instance.mode, 'backup')
    assert.equal(instance.mnemonic, '')
    instance.scriptType = 'p2wpkh'
    assert.equal(instance.backupAddressType, 'Taproot')
    assert.equal(instance.wallet.onchain_meta.accountPath, "m/86'/0'/7'")
    await instance.openCreate()
    assert.equal(instance.useCustomPath, false)
    assert.equal(instance.accountPath, "m/84'/0'/0'")
  })
}
