import {test, expect, randomHex} from './fixtures'
import {
  createInvoice,
  createWallet,
  extensionApi,
  extensionFrame,
  fundWalletWithFakeBalance,
  grantBackgroundPaymentPermission,
  grantWalletPaymentsWatchPermission,
  installAndEnableExtension,
  invoicePaymentRequest,
  login,
  payInvoiceWithWallet,
  waitForWalletBalance
} from './extension-helpers'
import {LNURLPayServer} from './lnurl-helpers'
import {LIVE_EXTENSIONS, PAYSPLIT} from './extensions'

test('install PaySplit and split incoming payment with fake wallet', async ({
  page,
  lnbitsServer
}) => {
  await login(page, lnbitsServer)
  const source = await createWallet(page, `PaySplit source ${randomHex()}`)
  const target = await createWallet(page, `PaySplit target ${randomHex()}`)
  const payer = await createWallet(page, `PaySplit payer ${randomHex()}`)
  await fundWalletWithFakeBalance(page, payer.id, {amountSats: 250})

  await installAndEnableExtension(page, PAYSPLIT, {
    preloadExtensions: LIVE_EXTENSIONS
  })
  await grantWalletPaymentsWatchPermission(page, PAYSPLIT.extId, source.id)
  await grantBackgroundPaymentPermission(page, PAYSPLIT.extId, source.id, {
    maxAmountSats: 100
  })

  const lnurlServer = await LNURLPayServer.start(lnbitsServer.baseUrl, target)
  try {
    const saved = await extensionApi(page, PAYSPLIT.extId, 'POST', '/sources', {
      enabled: true,
      maxAmount: 100,
      targets: [
        {
          alias: 'Playwright target',
          lnurl: lnurlServer.lnurl,
          percent: 25
        }
      ],
      walletId: source.id,
      walletName: source.name
    })
    const sourceConfig = saved.source as Record<string, unknown>
    const targets = saved.targets as Record<string, unknown>[]
    expect(sourceConfig.wallet_id).toBe(source.id)
    expect(targets[0].percent).toBe(25)

    await page.goto('/ext/paysplit')
    const frame = await extensionFrame(page, 'PaySplit')
    await frame.locator('#walletSelect').selectOption(source.id)
    await expect(frame.locator('.target-lnurl').first()).toHaveValue(
      lnurlServer.lnurl,
      {timeout: 60_000}
    )

    const invoice = await createInvoice(page, source, {
      amountSats: 100,
      memo: 'PaySplit Playwright source'
    })
    await payInvoiceWithWallet(page, payer, invoicePaymentRequest(invoice))
    await waitForWalletBalance(page, target, {
      expectedSats: 25,
      timeout: 45_000
    })
  } finally {
    await lnurlServer.close()
  }

  const sourceConfig = await extensionApi(
    page,
    PAYSPLIT.extId,
    'GET',
    `/sources/${source.id}`
  )
  const sourceData = sourceConfig.source as Record<string, unknown>
  const targets = sourceConfig.targets as Record<string, unknown>[]
  expect(sourceData.enabled).toBe(true)
  expect(targets[0].alias).toBe('Playwright target')
})
