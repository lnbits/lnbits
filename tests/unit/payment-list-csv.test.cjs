const assert = require('node:assert/strict')
const {readFileSync} = require('node:fs')
const {resolve} = require('node:path')
const {test} = require('node:test')
const vm = require('node:vm')

const root = resolve(__dirname, '../..')

async function exportPaymentsCSV(payments) {
  let component
  let csv
  const context = {
    window: {
      app: {component: (_, value) => (component = value)},
      i18n: {global: {locale: 'en'}}
    },
    Quasar: {
      date: {formatDate: date => date.toISOString()},
      exportFile: (_, content) => ((csv = content), true)
    },
    moment: {utc: () => ({local: () => ({fromNow: () => ''})})},
    URLSearchParams
  }
  vm.createContext(context)
  for (const file of ['utils.js', 'components/lnbits-payment-list.js']) {
    vm.runInContext(
      readFileSync(resolve(root, 'lnbits/static/js', file), 'utf8'),
      context
    )
  }
  context.LNbits = {
    utils: context.window._lnbitsUtils,
    api: {
      getPayments: async () => ({
        data: {data: payments, total: payments.length}
      })
    }
  }
  const instance = {
    $t: key => key,
    utils: context.window._lnbitsUtils,
    wallet: {name: 'wallet'}
  }
  for (const [name, method] of Object.entries(component.methods)) {
    instance[name] = method.bind(instance)
  }
  Object.assign(instance, component.data.call(instance))
  await instance.exportCSV()
  return csv
}

function payment(sat, extra) {
  return {
    checking_id: `id-${sat}`,
    payment_hash: `hash-${sat}`,
    status: 'success',
    amount: sat * 1000,
    fee: 0,
    memo: '',
    created_at: '2026-02-18T00:37:00Z',
    expiry: '2026-02-18T01:37:00Z',
    extra
  }
}

test('CSV export writes fiat amounts with the currency decimals', async () => {
  const csv = await exportPaymentsCSV([
    payment(700, {wallet_fiat_currency: 'USD', wallet_fiat_amount: 0.472}),
    // a 2 EUR TPoS sale: TPoS rounds the sats up, so the stored value is 2.001
    payment(2501, {wallet_fiat_currency: 'EUR', wallet_fiat_amount: 2.001}),
    payment(704, {wallet_fiat_currency: 'USD', wallet_fiat_amount: 0.475}),
    payment(1000, {wallet_fiat_currency: 'JPY', wallet_fiat_amount: 1234.567}),
    payment(21, {})
  ])
  const [header, ...rows] = csv
    .split('\r\n')
    .map(line => line.slice(1, -1).split('","'))
  const fiatAmount = header.indexOf('Fiat Amount')
  // "0.472" and "2.001" are read as 472 and 2001 by spreadsheets that use
  // "." as the thousands separator (e.g. German locale)
  assert.deepEqual(
    rows.map(row => row[fiatAmount]),
    ['0.47', '2.00', '0.48', '1235', '']
  )
})
