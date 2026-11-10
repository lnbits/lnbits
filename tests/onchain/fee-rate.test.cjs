const assert = require('node:assert/strict')
const {readFileSync} = require('node:fs')
const {resolve} = require('node:path')
const {test} = require('node:test')
const vm = require('node:vm')

function harness() {
  let component
  const events = []
  const recommended = {fastestFee: 20, halfHourFee: 7, hourFee: 3}
  vm.runInNewContext(
    readFileSync(
      resolve(
        __dirname,
        '../../lnbits/static/js/components/onchain/fee-rate.js'
      ),
      'utf8'
    ),
    {
      window: {app: {component: (_, value) => (component = value)}},
      LNbits: {
        onchain: {
          utils: {retryWithDelay: fn => fn()},
          mempoolJS: () => ({
            bitcoin: {
              fees: {getFeesRecommended: async () => ({...recommended})}
            }
          })
        }
      }
    }
  )
  const instance = {
    ...component.data(),
    rate: 1,
    $q: {notify: assert.fail},
    $emit(event, value) {
      events.push([event, value])
      this.rate = value
    }
  }
  for (const [name, property] of Object.entries(component.computed)) {
    Object.defineProperty(instance, name, {
      get: property.get.bind(instance),
      set: property.set.bind(instance)
    })
  }
  for (const [name, method] of Object.entries(component.methods))
    instance[name] = method.bind(instance)
  return {
    instance,
    events,
    recommended,
    initialize: () => component.created.call(instance)
  }
}

test('logarithmic slider positions emit actual integer fee rates', () => {
  const {instance, events} = harness()
  for (const [position, rate] of [
    [0, 1],
    [0.5, 3],
    [1, 10],
    [1.5, 32],
    [2, 100],
    [2.5, 316],
    [3, 1000]
  ]) {
    instance.sliderPosition = position
    assert.equal(instance.feeRate, rate)
    assert.deepEqual(events.at(-1), ['update:rate', rate])
  }
})

test('the initial slider selection follows the recommended fee', async () => {
  const {instance, initialize} = harness()
  await initialize()
  assert.equal(instance.feeRate, 7)
  assert.equal(instance.sliderPosition, Math.log10(7))
  assert.equal(
    instance.getFeeRateLabel(instance.feeRate),
    'Medium Priority (7 sat/vB)'
  )
})

test('numeric entry keeps exact values while the slider stays within its range', () => {
  const {instance} = harness()
  for (const [rate, position] of [
    [1, 0],
    [2.5, Math.log10(2.5)],
    [10, 1],
    [100, 2],
    [150, Math.log10(150)],
    [1000, 3],
    [1500, 3]
  ]) {
    instance.feeRate = rate
    assert.equal(instance.sliderPosition, position)
    assert.equal(instance.feeRate, rate)
  }
  instance.feeRate = ''
  assert.equal(instance.sliderPosition, 0)
})

test('refreshing recommendations selects the updated recommended fee', async () => {
  const {instance, initialize, recommended} = harness()
  await initialize()
  instance.feeRate = 12
  recommended.halfHourFee = 10
  await instance.refreshRecommendedFees()
  assert.equal(instance.recommededFees.halfHourFee, 10)
  assert.equal(instance.feeRate, 10)
  assert.equal(instance.sliderPosition, 1)
})
