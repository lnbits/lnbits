const assert = require('node:assert/strict')
const {readFileSync} = require('./source.cjs')
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
        '../../lnbits/onchain/static/components/hot-wallet.js'
      ),
      'utf8'
    ),
    context
  )
  const instance = {...component.data(), $emit() {}, adminkey: 'test-key'}
  for (const [name, fn] of Object.entries(component.methods))
    instance[name] = fn.bind(instance)
  for (const [name, fn] of Object.entries(component.computed))
    Object.defineProperty(instance, name, {get: () => fn.call(instance)})
  instance.openBackup({id: 'wallet', title: 'Test'})
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
  assert.equal(calls[1], '/onchain/api/v1/hot-wallet/wallet/backup/confirm')
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
