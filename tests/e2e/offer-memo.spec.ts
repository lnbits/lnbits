import {test, expect, randomHex} from './fixtures'
import {
  createInvoice,
  createWallet,
  fundWalletWithFakeBalance,
  invoicePaymentRequest,
  login
} from './extension-helpers'

test('offer memo becomes a payer note or falls back to the offer description', async ({
  page,
  lnbitsServer
}) => {
  await login(page, lnbitsServer)
  const source = await createWallet(page, `Offer payer ${randomHex()}`)
  const recipient = await createWallet(page, `Invoice recipient ${randomHex()}`)
  await fundWalletWithFakeBalance(page, source.id, {amountSats: 1000})
  await page.goto(`/wallet/${source.id}`)

  const offer =
    'lno1pgx9getnwss8vetrw3hhyuckyypwa3eyt44h6txtxquqh7lz5djge4afgfjn7k4rgrkuag0jsd5xvxg'
  await page.getByRole('button', {name: /^send$/i}).click()
  await page.locator('.q-dialog textarea').fill(offer)
  await page.getByRole('button', {name: /^read$/i}).click()
  const noteInput = page.getByLabel('Memo (optional)', {exact: true})
  const note = '  Thank you ☕ & = +\n' + 'long note '.repeat(30) + '  '
  await expect(noteInput).toBeVisible()
  await expect(page.locator('.q-dialog h6', {hasText: 'Test vectors'})).toBeVisible()
  await expect(noteInput).toHaveValue('')
  await noteInput.fill(note)
  await page.locator('.q-dialog input[type="number"]').fill('21')
  await page
    .getByLabel('Internal memo (optional)', {exact: true})
    .fill('Private memo')

  const memoResponse = page.waitForResponse(
    response =>
      response.url().endsWith('/api/v1/payments') &&
      response.request().method() === 'POST'
  )
  await page.getByRole('button', {name: /^pay$/i}).click()
  const paidWithMemo = await memoResponse
  expect(paidWithMemo.request().postDataJSON()).toEqual({
    out: true,
    payment_request: offer,
    amount: 21,
    unit: 'sat',
    extra: {internal_memo: 'Private memo'},
    memo: note
  })
  expect(paidWithMemo.status()).toBe(201)
  const memoPayment = await paidWithMemo.json()
  expect(memoPayment.status).toBe('success')
  expect(memoPayment.memo).toBe(note)
  expect(memoPayment.extra.payer_note).toBe(note)
  expect(memoPayment.extra.bolt12_offer_description).toBe('Test vectors')
  expect(memoPayment.extra.internal_memo).toBe('Private memo')

  // Empty notes fall back to the offer description without sending a payer note.
  await expect(noteInput).toBeHidden()
  await page.getByRole('button', {name: /^send$/i}).click()
  await page.locator('.q-dialog textarea').fill(offer)
  await page.getByRole('button', {name: /^read$/i}).click()
  await expect(noteInput).toHaveValue('')
  await page.locator('.q-dialog input[type="number"]').fill('21')
  await page
    .getByLabel('Internal memo (optional)', {exact: true})
    .fill('Private memo')
  const offerResponse = page.waitForResponse(
    response =>
      response.url().endsWith('/api/v1/payments') &&
      response.request().method() === 'POST'
  )
  await page.getByRole('button', {name: /^pay$/i}).click()
  const paidOffer = await offerResponse
  expect(paidOffer.request().postDataJSON()).not.toHaveProperty('memo')
  expect(paidOffer.status()).toBe(201)
  const offerPayment = await paidOffer.json()
  expect(offerPayment.status).toBe('success')
  expect(offerPayment.memo).toBe('Test vectors')
  expect(offerPayment.extra).not.toHaveProperty('payer_note')
  expect(offerPayment.extra).not.toHaveProperty('bolt12_offer_description')
  expect(offerPayment.extra.internal_memo).toBe('Private memo')
  await expect(noteInput).toBeHidden()

  // Opening another payment clears the previous note.
  await page.getByRole('button', {name: /^send$/i}).click()
  await page.locator('.q-dialog textarea').fill(offer)
  await page.getByRole('button', {name: /^read$/i}).click()
  await expect(noteInput).toHaveValue('')
  await noteInput.fill('Must not carry over')
  await page.getByRole('button', {name: /^cancel$/i}).click()

  const invoice = await createInvoice(page, recipient, {
    amountSats: 10,
    memo: 'BOLT11 recipient memo'
  })
  await page.getByRole('button', {name: /^send$/i}).click()
  await page.locator('.q-dialog textarea').fill(invoicePaymentRequest(invoice))
  await page.getByRole('button', {name: /^read$/i}).click()
  await expect(noteInput).toBeHidden()

  const invoiceResponse = page.waitForResponse(
    response =>
      response.url().endsWith('/api/v1/payments') &&
      response.request().method() === 'POST'
  )
  await page.getByRole('button', {name: /^pay$/i}).click()
  const paidInvoice = await invoiceResponse
  expect(paidInvoice.request().postDataJSON()).toEqual({
    out: true,
    payment_request: invoicePaymentRequest(invoice)
  })
  expect(paidInvoice.status()).toBe(201)
  expect((await paidInvoice.json()).status).toBe('success')
})
