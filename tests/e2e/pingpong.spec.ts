import {test, expect, randomHex, waitForResult} from './fixtures'
import type {Page} from '@playwright/test'
import {
  createWallet,
  extensionApi,
  extensionFrame,
  fundWalletWithFakeBalance,
  grantBackgroundPaymentPermission,
  installAndEnableExtension,
  login,
  payInvoiceWithWallet,
  superuserWallet
} from './extension-helpers'
import {LNURLPayServer} from './lnurl-helpers'
import {LIVE_EXTENSIONS, PINGPONG} from './extensions'

test('install Ping Pong and pay entry invoice with fake wallet', async ({
  page,
  lnbitsServer
}) => {
  await login(page, lnbitsServer)
  const escrow = await superuserWallet(page)
  const payer = await createWallet(page, `PingPong payer ${randomHex()}`)
  const payoutTarget = await createWallet(
    page,
    `PingPong payout ${randomHex()}`
  )
  await fundWalletWithFakeBalance(page, payer.id, {amountSats: 100})

  await installAndEnableExtension(page, PINGPONG, {
    preloadExtensions: LIVE_EXTENSIONS
  })
  await grantBackgroundPaymentPermission(page, PINGPONG.extId, escrow.id, {
    maxAmountSats: 100
  })

  await page.goto('/ext/pingpong')
  const frame = await extensionFrame(page, 'Ping Pong')
  await expect(frame.getByText('Lightning Pong tables')).toBeVisible({
    timeout: 60_000
  })

  const tableName = `Playwright Pong ${randomHex()}`
  const table = await extensionApi(page, PINGPONG.extId, 'POST', '/tables', {
    name: tableName,
    description: 'Playwright fake wallet table',
    walletId: escrow.id,
    entrySats: 3,
    gamesToWin: 1,
    hostPercent: 0
  })
  expect(table.name).toBe(tableName)

  const lnurlServer = await LNURLPayServer.start(
    lnbitsServer.baseUrl,
    payoutTarget
  )
  let game: Record<string, unknown>
  try {
    game = await extensionApi(
      page,
      PINGPONG.extId,
      'POST',
      `/tables/${table.id}/games`,
      {lnurl: lnurlServer.lnurl}
    )
    const invoice = game.invoice as Record<string, unknown>
    const paymentRequest = String(invoice.paymentRequest)
    expect(paymentRequest.toLowerCase()).toMatch(/^lnbc/)

    await payInvoiceWithWallet(page, payer, paymentRequest)
    const paidGame = await waitForResult(
      'Ping Pong player 1 payment to be recorded',
      async () =>
        pingpongGameIfPlayer1Paid(
          page,
          String(game.gameId),
          String(game.playerToken)
        ),
      {timeout: 30_000}
    )
    expect(paidGame.status).toBe('waiting_opponent')
    expect(paidGame.player1Paid).toBe(true)
  } finally {
    await lnurlServer.close()
  }

  await page.goto('/ext/pingpong')
  const updatedFrame = await extensionFrame(page, 'Ping Pong')
  await expect(updatedFrame.getByText(tableName)).toBeVisible({timeout: 60_000})
})

async function pingpongGameIfPlayer1Paid(
  page: Page,
  gameId: string,
  playerToken: string
): Promise<Record<string, unknown> | null> {
  const game = await extensionApi(
    page,
    PINGPONG.extId,
    'GET',
    `/games/${gameId}/public?playerToken=${playerToken}`
  )
  return game.player1Paid === true ? game : null
}
