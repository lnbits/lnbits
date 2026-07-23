import {test, expect, randomHex} from './fixtures'
import {
  createInvoice,
  createWallet,
  extensionApi,
  extensionFrame,
  fundWalletWithFakeBalance,
  installAndEnableExtension,
  invoicePaymentRequest,
  login,
  waitForWalletBalance
} from './extension-helpers'
import {BIGPAYMENT, LIVE_EXTENSIONS} from './extensions'

test('install BigPayment and pay large invoice with fake wallet', async ({
  page,
  lnbitsServer
}) => {
  await login(page, lnbitsServer)
  await installAndEnableExtension(page, BIGPAYMENT, {
    preloadExtensions: LIVE_EXTENSIONS
  })

  const collector = await createWallet(
    page,
    `BigPayment collector ${randomHex()}`
  )
  const source = await createWallet(page, `BigPayment source ${randomHex()}`)
  const recipient = await createWallet(
    page,
    `BigPayment recipient ${randomHex()}`
  )
  await fundWalletWithFakeBalance(page, source.id, {amountSats: 750})

  await page.goto('/ext/bigpayment')
  const frame = await extensionFrame(page, 'BigPayment')
  await expect(frame.getByText('Pay large Lightning invoices')).toBeVisible({
    timeout: 60_000
  })

  const invoice = await createInvoice(page, recipient, {
    amountSats: 500,
    memo: 'BigPayment Playwright recipient'
  })
  const selection = await extensionApi(
    page,
    BIGPAYMENT.extId,
    'POST',
    '/selection',
    {
      walletIds: [collector.id, source.id],
      collectorWalletId: collector.id
    }
  )
  expect(selection.collectorWalletId).toBe(collector.id)

  const payment = await extensionApi(
    page,
    BIGPAYMENT.extId,
    'POST',
    '/payments',
    {
      paymentRequest: invoicePaymentRequest(invoice),
      walletIds: [collector.id, source.id],
      collectorWalletId: collector.id,
      memo: 'BigPayment Playwright payment'
    }
  )
  expect(payment.paid).toBe(true)
  expect(payment.direct).toBe(false)
  expect(payment.amountSat).toBe(500)
  expect(Array.isArray(payment.transfers)).toBe(true)
  expect((payment.transfers as Record<string, unknown>[])[0].fromWalletId).toBe(
    source.id
  )
  await waitForWalletBalance(page, recipient, {expectedSats: 500})
})
