import type {Page, Response} from '@playwright/test'

import {
  test,
  expect,
  installDetailedScreenshots,
  randomHex,
  waitForResult,
  isRecord
} from './fixtures'
import {
  createWallet,
  extensionApi,
  extensionFrame,
  fundWalletWithFakeBalance,
  grantBackgroundPaymentPermission,
  installAndEnableExtension,
  login,
  payInvoiceWithWallet,
  superuserWallet,
  waitForWalletBalance
} from './extension-helpers'
import {LNURLPayServer} from './lnurl-helpers'
import {LIVE_EXTENSIONS, PINGPONG} from './extensions'

type GameInvoice = {
  gameId: string
  invoice: {
    checkingId: string
    paymentHash: string
    paymentRequest: string
  }
  playerSlot: 'player1' | 'player2'
  playerToken: string
}

test('install Ping Pong, play public game, and pay winner with fake wallet', async ({
  page,
  browser,
  lnbitsServer
}, testInfo) => {
  await login(page, lnbitsServer)
  const escrow = await superuserWallet(page)
  const player1EntryWallet = await createWallet(
    page,
    `PingPong player 1 entry ${randomHex()}`
  )
  const player2EntryWallet = await createWallet(
    page,
    `PingPong player 2 entry ${randomHex()}`
  )
  const player1PayoutTarget = await createWallet(
    page,
    `PingPong player 1 payout ${randomHex()}`
  )
  const player2PayoutTarget = await createWallet(
    page,
    `PingPong player 2 payout ${randomHex()}`
  )
  await fundWalletWithFakeBalance(page, player1EntryWallet.id, {
    amountSats: 100
  })
  await fundWalletWithFakeBalance(page, player2EntryWallet.id, {
    amountSats: 100
  })

  await installAndEnableExtension(page, PINGPONG, {
    preloadExtensions: LIVE_EXTENSIONS
  })
  await grantBackgroundPaymentPermission(page, PINGPONG.extId, escrow.id, {
    maxAmountSats: 100
  })

  await page.goto('/ext/pingpong')
  const adminFrame = await extensionFrame(page, 'Ping Pong')
  await expect(adminFrame.getByText('Lightning Pong tables')).toBeVisible({
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

  const player1LnurlServer = await LNURLPayServer.start(
    lnbitsServer.baseUrl,
    player1PayoutTarget
  )
  const player2LnurlServer = await LNURLPayServer.start(
    lnbitsServer.baseUrl,
    player2PayoutTarget
  )

  const player2Context = await browser.newContext({
    baseURL: lnbitsServer.baseUrl,
    viewport: {width: 1280, height: 900}
  })
  const player2Page = await player2Context.newPage()
  player2Page.setDefaultTimeout(60_000)
  const player2Recorder = await installDetailedScreenshots(
    player2Page,
    testInfo
  )

  try {
    const player1Game = await createPublicGame(
      page,
      String(table.id),
      tableName,
      player1LnurlServer.lnurl
    )
    await payInvoiceWithWallet(
      page,
      player1EntryWallet,
      player1Game.invoice.paymentRequest
    )
    await waitForResult(
      'Ping Pong player 1 payment to be recorded',
      async () =>
        pingpongGameIfPlayer1Paid(
          page,
          player1Game.gameId,
          player1Game.playerToken
        ),
      {timeout: 30_000}
    )
    await page.goto(publicGamePath(player1Game.gameId))
    const player1WaitingFrame = await extensionFrame(page, 'Ping Pong')
    const waitingGame = await publicGame(
      page,
      player1Game.gameId,
      player1Game.playerToken
    )
    expect(waitingGame.status).toBe('waiting_opponent')
    await expect(player1WaitingFrame.locator('#game-note')).toContainText(
      'Share the game link with player 2.'
    )

    const player2Game = await joinPublicGame(
      player2Page,
      player1Game.gameId,
      tableName,
      player2LnurlServer.lnurl
    )
    await payInvoiceWithWallet(
      player2Page,
      player2EntryWallet,
      player2Game.invoice.paymentRequest
    )
    await waitForResult(
      'Ping Pong game to start playing after both players paid',
      async () => {
        const game = await publicGame(
          page,
          player1Game.gameId,
          player1Game.playerToken
        )
        return game.status === 'playing' &&
          game.player1Paid === true &&
          game.player2Paid === true
          ? game
          : null
      },
      {timeout: 60_000}
    )

    await page.goto(publicGamePath(player1Game.gameId))
    await player2Page.goto(publicGamePath(player1Game.gameId))
    const player1PlayingFrame = await extensionFrame(page, 'Ping Pong')
    const player2PlayingFrame = await extensionFrame(player2Page, 'Ping Pong')
    await expect(player1PlayingFrame.locator('#game-status')).toHaveText(
      'playing',
      {timeout: 60_000}
    )
    await expect(player2PlayingFrame.locator('#game-status')).toHaveText(
      'playing',
      {timeout: 60_000}
    )
    await expect(player1PlayingFrame.locator('#game-note')).toContainText(
      'You control the left paddle.'
    )
    await expect(player2PlayingFrame.locator('#game-note')).toContainText(
      'You control the right paddle.'
    )

    const finished = await extensionApi(
      page,
      PINGPONG.extId,
      'POST',
      `/games/${player1Game.gameId}/finish`,
      {
        playerToken: player1Game.playerToken,
        winnerSlot: 'player1',
        player1Wins: 1,
        player2Wins: 0,
        currentPlayer1Score: 11,
        currentPlayer2Score: 0
      }
    )
    expect(finished.winnerSlot).toBe('player1')

    const paidGame = await waitForResult(
      'Ping Pong winner payout to be paid',
      async () => {
        const game = await publicGame(
          page,
          player1Game.gameId,
          player1Game.playerToken
        )
        return game.status === 'paid' && game.payoutStatus === 'paid'
          ? game
          : null
      },
      {timeout: 60_000, interval: 2_000}
    )
    expect(paidGame.winnerSlot).toBe('player1')
    await waitForWalletBalance(page, player1PayoutTarget, {
      expectedSats: Number(
        (paidGame.table as Record<string, unknown>).winnerPayoutSats
      ),
      timeout: 60_000
    })

    await page.goto(publicGamePath(player1Game.gameId))
    await player2Page.goto(publicGamePath(player1Game.gameId))
    const player1PaidFrame = await extensionFrame(page, 'Ping Pong')
    const player2PaidFrame = await extensionFrame(player2Page, 'Ping Pong')
    await expect(player1PaidFrame.locator('#game-status')).toHaveText(
      'Player 1 won',
      {timeout: 60_000}
    )
    await expect(player2PaidFrame.locator('#game-status')).toHaveText(
      'Player 1 won',
      {timeout: 60_000}
    )
    await expect(player1PaidFrame.locator('#game-note')).toContainText(
      'Player 1 won. Payout status: paid.'
    )
  } finally {
    await player2Recorder.finish()
    await player2Context.close()
    await player1LnurlServer.close()
    await player2LnurlServer.close()
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
  const game = await publicGame(page, gameId, playerToken)
  return game.player1Paid === true ? game : null
}

async function createPublicGame(
  page: Page,
  tableId: string,
  tableName: string,
  lnurl: string
): Promise<GameInvoice> {
  await page.goto(publicTablePath(tableId))
  const frame = await extensionFrame(page, 'Ping Pong')
  await expect(frame.locator('#table-view')).toBeVisible({timeout: 60_000})
  await expect(frame.locator('#table-name')).toHaveText(tableName)
  await frame.locator('#create-lnurl').fill(lnurl)

  const responsePromise = page.waitForResponse(
    response =>
      response.request().method() === 'POST' &&
      response
        .url()
        .includes(`/api/v1/ext/${PINGPONG.extId}/tables/${tableId}/games`)
  )
  await frame.locator('#create-game').click()
  const game = await gameInvoiceFromResponse(await responsePromise)
  await expect(frame.locator('#payment-view')).toBeVisible({timeout: 60_000})
  await expect(frame.locator('#invoice-text')).toHaveText(
    game.invoice.paymentRequest,
    {timeout: 60_000}
  )
  return game
}

async function joinPublicGame(
  page: Page,
  gameId: string,
  tableName: string,
  lnurl: string
): Promise<GameInvoice> {
  await page.goto(publicGamePath(gameId))
  const frame = await extensionFrame(page, 'Ping Pong')
  await expect(frame.locator('#game-view')).toBeVisible({timeout: 60_000})
  await expect(frame.locator('#game-meta')).toContainText(tableName)
  await expect(frame.locator('#join-panel')).toBeVisible({timeout: 60_000})
  await frame.locator('#join-lnurl').fill(lnurl)

  const responsePromise = page.waitForResponse(
    response =>
      response.request().method() === 'POST' &&
      response
        .url()
        .includes(`/api/v1/ext/${PINGPONG.extId}/games/${gameId}/join`)
  )
  await frame.locator('#join-game').click()
  const game = await gameInvoiceFromResponse(await responsePromise)
  await expect(frame.locator('#payment-view')).toBeVisible({timeout: 60_000})
  await expect(frame.locator('#invoice-text')).toHaveText(
    game.invoice.paymentRequest,
    {timeout: 60_000}
  )
  return game
}

async function publicGame(
  page: Page,
  gameId: string,
  playerToken: string
): Promise<Record<string, unknown>> {
  return extensionApi(
    page,
    PINGPONG.extId,
    'GET',
    `/games/${gameId}/public?playerToken=${playerToken}`
  )
}

async function gameInvoiceFromResponse(
  response: Response
): Promise<GameInvoice> {
  const body = await response.json()
  const data = isRecord(body) && isRecord(body.data) ? body.data : body
  if (!isRecord(data) || !isRecord(data.invoice)) {
    throw new Error(
      `Ping Pong game invoice response is invalid: ${JSON.stringify(body)}`
    )
  }
  const paymentRequest = data.invoice.paymentRequest
  const paymentHash = data.invoice.paymentHash
  const checkingId = data.invoice.checkingId
  if (
    typeof data.gameId !== 'string' ||
    typeof data.playerSlot !== 'string' ||
    typeof data.playerToken !== 'string' ||
    typeof paymentRequest !== 'string' ||
    typeof paymentHash !== 'string' ||
    typeof checkingId !== 'string'
  ) {
    throw new Error(
      `Ping Pong game invoice response is incomplete: ${JSON.stringify(body)}`
    )
  }
  expect(paymentRequest.toLowerCase()).toMatch(/^lnbc/)
  return {
    gameId: data.gameId,
    playerSlot: data.playerSlot as GameInvoice['playerSlot'],
    playerToken: data.playerToken,
    invoice: {
      checkingId,
      paymentHash,
      paymentRequest
    }
  }
}

function publicTablePath(tableId: string): string {
  return `/ext/${PINGPONG.extId}/t/${encodeURIComponent(tableId)}`
}

function publicGamePath(gameId: string): string {
  return `/ext/${PINGPONG.extId}/g/${encodeURIComponent(gameId)}`
}
