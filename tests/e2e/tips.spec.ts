import type {Page} from '@playwright/test'

import {test, expect, apiJson, randomHex} from './fixtures'
import {
  extensionFrame,
  fundWalletWithFakeBalance,
  installAndEnableExtension,
  login,
  superuserWallet
} from './extension-helpers'
import {LIVE_EXTENSIONS, TIPS} from './extensions'

test('install Tips extension and pay tip with fake wallet', async ({
  page,
  lnbitsServer
}) => {
  await login(page, lnbitsServer)
  const wallet = await superuserWallet(page)

  await installAndEnableExtension(page, TIPS, {
    preloadExtensions: LIVE_EXTENSIONS
  })
  await fundWalletWithFakeBalance(page, wallet.id, {amountSats: 10_000})

  const jarTitle = `Playwright Tips ${randomHex()}`
  const tipMessage = `fake wallet tip ${randomHex()}`
  const publicUrl = await createTipJar(page, jarTitle)
  const paymentRequest = await createPublicTipInvoice(
    page,
    publicUrl,
    tipMessage
  )

  await apiJson(
    lnbitsServer.baseUrl,
    'POST',
    '/api/v1/payments',
    {out: true, bolt11: paymentRequest},
    wallet.adminkey
  )

  const publicFrame = await tipsFrame(page)
  await expect(publicFrame.locator('#invoice-status')).toHaveText(
    'Payment received',
    {timeout: 30_000}
  )

  await page.goto('/ext/tips')
  const adminFrame = await tipsFrame(page)
  await expect(
    adminFrame.getByRole('cell', {name: jarTitle}).first()
  ).toBeVisible({
    timeout: 60_000
  })
  await adminFrame.getByRole('button', {name: 'Refresh'}).click()
  await expect(
    adminFrame.getByRole('cell', {name: tipMessage}).first()
  ).toBeVisible({
    timeout: 60_000
  })
  await expect(
    adminFrame.getByRole('cell', {name: 'Paid'}).first()
  ).toBeVisible()
})

async function createTipJar(page: Page, jarTitle: string): Promise<string> {
  await page.goto('/ext/tips')
  const frame = await tipsFrame(page)
  await expect(frame.getByText('Create Jar')).toBeVisible({timeout: 60_000})
  await frame.getByLabel('Title').fill(jarTitle)
  await frame.getByRole('button', {name: /^create$/i}).click()
  await expect(frame.getByRole('cell', {name: jarTitle})).toBeVisible({
    timeout: 60_000
  })
  await frame.waitForFunction(() =>
    [...document.querySelectorAll('input')].some(input =>
      input.value.includes('/ext/tips/jars/')
    )
  )
  const publicUrl = await frame.evaluate(() =>
    [...document.querySelectorAll('input')]
      .map(input => input.value)
      .find(value => value.includes('/ext/tips/jars/'))
  )
  if (typeof publicUrl !== 'string' || !publicUrl.includes('/ext/tips/jars/')) {
    throw new Error(`Tip jar public URL was not found: ${String(publicUrl)}`)
  }
  return publicUrl
}

async function createPublicTipInvoice(
  page: Page,
  publicUrl: string,
  tipMessage: string
): Promise<string> {
  await page.goto(publicUrl)
  const frame = await tipsFrame(page)
  await expect(frame.getByRole('heading', {name: 'Leave a Tip'})).toBeVisible({
    timeout: 60_000
  })
  await frame.getByLabel('Name').fill('Playwright')
  await frame.getByLabel('Message').fill(tipMessage)
  await frame.getByRole('button', {name: 'Create Invoice'}).click()
  await expect(frame.getByText('Waiting for payment')).toBeVisible({
    timeout: 60_000
  })
  await frame.waitForFunction(() =>
    Boolean(document.querySelector('#copy-invoice-button')?.dataset.invoice)
  )
  const paymentRequest = await frame
    .locator('#copy-invoice-button')
    .evaluate(button => button.dataset.invoice)
  if (
    typeof paymentRequest !== 'string' ||
    !paymentRequest.toLowerCase().startsWith('lnbc')
  ) {
    throw new Error(
      `Tip invoice payment request was not found: ${String(paymentRequest)}`
    )
  }
  return paymentRequest
}

async function tipsFrame(page: Page) {
  return extensionFrame(page, 'Tips')
}
