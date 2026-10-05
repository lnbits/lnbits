const assert = require('node:assert/strict')
const {readFileSync} = require('node:fs')
const {resolve} = require('node:path')
const {test} = require('node:test')
const vm = require('node:vm')

function harness() {
  let component
  vm.runInNewContext(
    readFileSync(
      resolve(
        __dirname,
        '../../lnbits/static/js/components/onchain/address-list.js'
      ),
      'utf8'
    ),
    {window: {app: {component: (_, value) => (component = value)}}}
  )
  const instance = {
    ...component.data(),
    accounts: [{id: 'wallet', onchain_address_no: -1}],
    addresses: [
      {id: 'used', addressIndex: 0, hasActivity: true, amount: 0},
      {id: 'funded', addressIndex: 1, hasActivity: false, amount: 1000},
      {id: 'gap', addressIndex: 2, hasActivity: false, amount: 0},
      {
        id: 'change',
        addressIndex: 0,
        isChange: true,
        hasActivity: true,
        amount: 0
      }
    ].map(address => ({wallet: 'wallet', isChange: false, ...address}))
  }
  const visible = () =>
    component.methods.getFilteredAddresses
      .call(instance)
      .map(address => address.id)
  return {instance, visible}
}

test('restored used and funded addresses are visible before an address is issued', () => {
  const {visible} = harness()
  assert.deepEqual(visible(), ['used', 'funded'])
})

test('issued unused addresses remain visible while unused gap addresses stay hidden', () => {
  const {instance, visible} = harness()
  instance.accounts[0].onchain_address_no = 2
  assert.deepEqual(visible(), ['used', 'funded', 'gap'])
})

test('restored addresses still respect change, gap, and amount filters', () => {
  const {instance, visible} = harness()
  instance.filterValues = ['Show Change Addresses']
  assert.deepEqual(visible(), ['used', 'funded', 'change'])
  instance.filterValues = ['Show Gap Addresses']
  assert.deepEqual(visible(), ['used', 'funded', 'gap'])
  instance.filterValues = ['Only With Amount']
  assert.deepEqual(visible(), ['funded'])
})
