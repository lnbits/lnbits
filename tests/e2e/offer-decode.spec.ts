import {test, expect, randomHex} from './fixtures'
import {
  createWallet,
  fundWalletWithFakeBalance,
  login
} from './extension-helpers'

// BOLT12 offers-test.json: 10,000 msat and USD 100.00 respectively.
const amountOffer =
  'lno1pqpzwyq2p32x2um5ypmx2cm5dae8x93pqthvwfzadd7jejes8q9lhc4rvjxd022zv5l44g6qah82ru5rdpnpj'
const currencyOffer =
  'lno1qcp4256ypqpzwyq2p32x2um5ypmx2cm5dae8x93pqthvwfzadd7jejes8q9lhc4rvjxd022zv5l44g6qah82ru5rdpnpj'
const descriptionOffer =
  'lno1pgx9getnwss8vetrw3hhyuckyypwa3eyt44h6txtxquqh7lz5djge4afgfjn7k4rgrkuag0jsd5xvxg'
const minimalOffer =
  'lno1zcss9mk8y3wkklfvevcrszlmu23kfrxh49px20665dqwmn4p72pksese'

test('offer metadata prefills sats and keeps the description separate from the payer note', async ({
  page,
  lnbitsServer
}) => {
  await login(page, lnbitsServer)
  const wallet = await createWallet(page, `Offer decode ${randomHex()}`)
  await fundWalletWithFakeBalance(page, wallet.id, {amountSats: 1000})
  await page.goto(`/wallet/${wallet.id}`)

  await page.getByRole('button', {name: /^send$/i}).click()
  // URI wrappers, uppercase and wrapped offers are normalized by the backend.
  const wrapped = amountOffer.slice(0, 20) + '+\n  ' + amountOffer.slice(20)
  await page
    .locator('.q-dialog textarea')
    .fill('LIGHTNING://' + wrapped.toUpperCase())
  await page.getByRole('button', {name: /^read$/i}).click()
  const amountInput = page.locator('.q-dialog input[type="number"]')
  await expect(amountInput).toHaveValue('10')
  await expect(
    page.locator('.q-dialog h6', {hasText: 'Test vectors'})
  ).toBeVisible()
  await expect(page.getByLabel('Memo (optional)', {exact: true})).toHaveValue(
    ''
  )

  const paymentResponse = page.waitForResponse(
    response =>
      response.url().endsWith('/api/v1/payments') &&
      response.request().method() === 'POST'
  )
  await page.getByRole('button', {name: /^pay$/i}).click()
  const paid = await paymentResponse
  expect(paid.request().postDataJSON()).toEqual({
    out: true,
    payment_request: amountOffer,
    amount: 10,
    unit: 'sat'
  })
  expect(paid.status()).toBe(201)
  const payment = await paid.json()
  expect(payment.memo).toBe('Test vectors')
  expect(payment.extra).not.toHaveProperty('payer_note')
  await expect(amountInput).toBeHidden()

  for (const offer of [
    currencyOffer,
    descriptionOffer,
    minimalOffer,
    // 1,500 msat: do not silently round to whole sats.
    'lno1pqpqthq2p32x2um5ypmx2cm5dae8x93pqthvwfzadd7jejes8q9lhc4rvjxd022zv5l44g6qah82ru5rdpnpj',
    // 2**53 + 1 msat: do not prefill an imprecise JavaScript number.
    'lno1pqrjqqqqqqqqqqg2p32x2um5ypmx2cm5dae8x93pqthvwfzadd7jejes8q9lhc4rvjxd022zv5l44g6qah82ru5rdpnpj'
  ]) {
    await page.getByRole('button', {name: /^send$/i}).click()
    await page.locator('.q-dialog textarea').fill(offer)
    await page.getByRole('button', {name: /^read$/i}).click()
    await expect(amountInput).toHaveValue('0')
    await expect(page.getByRole('button', {name: /^pay$/i})).toBeDisabled()
    await expect(page.getByLabel('Memo (optional)', {exact: true})).toHaveValue(
      ''
    )
    const description = page.locator('.q-dialog h6', {hasText: 'Test vectors'})
    if (offer === minimalOffer) {
      await expect(description).toBeHidden()
    } else {
      await expect(description).toBeVisible()
    }
    await amountInput.fill('21')
    await expect(page.getByRole('button', {name: /^pay$/i})).toBeEnabled()
    await page.getByRole('button', {name: /^cancel$/i}).click()
    await expect(amountInput).toBeHidden()
  }
})

test('invalid offers show a decode error and allow correction', async ({
  page,
  lnbitsServer
}) => {
  await login(page, lnbitsServer)
  await page.getByRole('button', {name: /^send$/i}).click()
  await page.locator('.q-dialog textarea').fill('lno1!!!')
  await page.getByRole('button', {name: /^read$/i}).click()
  await expect(
    page.getByText('Invalid BOLT12 offer.', {exact: true})
  ).toBeVisible()
  await expect(page.locator('.q-dialog input[type="number"]')).toBeHidden()
  await page.locator('.q-dialog textarea').fill(amountOffer)
  await page.getByRole('button', {name: /^read$/i}).click()
  await expect(page.locator('.q-dialog input[type="number"]')).toHaveValue('10')
})

test('a late offer decode cannot replace a newly opened payment form', async ({
  page,
  lnbitsServer
}) => {
  await login(page, lnbitsServer)
  let releaseResponse: () => void = () => {}
  const responseReady = new Promise<void>(resolve => {
    releaseResponse = resolve
  })
  let decodeStarted: () => void = () => {}
  const requestStarted = new Promise<void>(resolve => {
    decodeStarted = resolve
  })
  await page.route('**/api/v1/payments/decode', async route => {
    const response = await route.fetch()
    decodeStarted()
    await responseReady
    await route.fulfill({response})
  })
  await page.getByRole('button', {name: /^send$/i}).click()
  await page.locator('.q-dialog textarea').fill(amountOffer)
  await page.getByRole('button', {name: /^read$/i}).click()
  await requestStarted
  await page.getByRole('button', {name: /^cancel$/i}).click()
  await expect(page.locator('.q-dialog textarea')).toBeHidden()
  await page.getByRole('button', {name: /^send$/i}).click()
  await page.locator('.q-dialog textarea').fill(minimalOffer)
  const decoded = page.waitForResponse('**/api/v1/payments/decode')
  releaseResponse()
  await decoded
  await page.unroute('**/api/v1/payments/decode')
  await expect(page.locator('.q-dialog textarea')).toHaveValue(minimalOffer)
  await page.getByRole('button', {name: /^read$/i}).click()
  await expect(page.locator('.q-dialog input[type="number"]')).toHaveValue('0')
  await expect(
    page.locator('.q-dialog h6', {hasText: 'Test vectors'})
  ).toBeHidden()
})
