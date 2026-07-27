import {existsSync} from 'node:fs'
import {join, resolve} from 'node:path'

import {
  expect,
  installDetailedScreenshots,
  isRecord,
  randomHex,
  test
} from './fixtures'
import {
  extensionApi,
  extensionFrame,
  installAndEnableExtension,
  login
} from './extension-helpers'
import {SUPPORTCHAT} from './extensions'

const supportchatDir =
  process.env.LNBITS_E2E_SUPPORTCHAT_DIR ??
  resolve('data/extensions/supportchat')

test.skip(
  !existsSync(join(supportchatDir, 'config.json')),
  'Support Chat E2E requires LNBITS_E2E_SUPPORTCHAT_DIR or data/extensions/supportchat.'
)

test('install Support Chat and run the visitor-to-agent support workflow', async ({
  page,
  browser,
  lnbitsServer
}, testInfo) => {
  await login(page, lnbitsServer)
  await installAndEnableExtension(page, SUPPORTCHAT)

  await page.goto('/ext/supportchat')
  let adminFrame = await extensionFrame(page, 'Support Chat')
  await expect(
    adminFrame.getByRole('heading', {name: 'Support Chat'})
  ).toBeVisible({timeout: 60_000})

  const inboxName = `Playwright Support ${randomHex()}`
  const inboxForm = adminFrame.locator('#inbox-form')
  const createInboxButton = inboxForm.getByRole('button', {
    name: 'Create inbox'
  })
  await expect(createInboxButton).toBeEnabled()
  await inboxForm.locator('[name="name"]').fill(inboxName)
  await inboxForm
    .locator('[name="welcomeMessage"]')
    .fill('How can the Playwright support team help?')
  await inboxForm.locator('[name="launcherText"]').fill('Ask Playwright')
  await inboxForm
    .locator('[name="offlineMessage"]')
    .fill('Playwright support is offline; leave a message.')
  await inboxForm.locator('[name="officeHoursEnabled"]').check()
  await inboxForm.locator('[name="officeHoursStart"]').fill('0')
  await inboxForm.locator('[name="officeHoursEnd"]').fill('0')
  await createInboxButton.click()
  await expect(adminFrame.getByText(inboxName).first()).toBeVisible({
    timeout: 60_000
  })

  const inbox = await supportInbox(page, inboxName)
  const publicPath = `/ext/supportchat/i/${encodeURIComponent(String(inbox.id))}`
  const visitorContext = await browser.newContext({
    baseURL: lnbitsServer.baseUrl,
    viewport: {width: 430, height: 820}
  })
  const visitorPage = await visitorContext.newPage()
  visitorPage.setDefaultTimeout(60_000)
  const visitorRecorder = await installDetailedScreenshots(
    visitorPage,
    testInfo
  )

  try {
    await visitorPage.goto(publicPath)
    let visitorFrame = await extensionFrame(visitorPage, 'Support Chat')
    await expect(visitorFrame.getByText(inboxName)).toBeVisible()
    await expect(
      visitorFrame.getByText('Playwright support is offline; leave a message.')
    ).toBeVisible()

    const startForm = visitorFrame.locator('#start-box')
    await startForm.locator('[name="name"]').fill('Alice Visitor')
    await startForm
      .locator('[name="email"]')
      .fill('alice.playwright@example.com')
    await startForm.locator('[name="subject"]').fill('Checkout is stuck')
    await startForm
      .locator('[name="body"]')
      .fill('The checkout spinner never finishes.')
    await startForm.getByTestId('start-conversation').click()
    await expect(visitorPage).toHaveURL(/\/ext\/supportchat\/c\/[a-f0-9]+$/i, {
      timeout: 60_000
    })
    visitorFrame = await extensionFrame(visitorPage, 'Support Chat')
    await expect(
      visitorFrame.getByText('The checkout spinner never finishes.')
    ).toBeVisible()

    await page.goto('/ext/supportchat')
    adminFrame = await extensionFrame(page, 'Support Chat')
    await expect(adminFrame.getByText('Checkout is stuck')).toBeVisible({
      timeout: 60_000
    })
    await expect(adminFrame.getByTestId('unread-count')).toHaveText('1')
    await adminFrame.getByText('Checkout is stuck').click()
    await expect(
      adminFrame.getByText('The checkout spinner never finishes.')
    ).toBeVisible()

    const cannedForm = adminFrame.locator('#canned-reply-form')
    await cannedForm.locator('[name="title"]').fill('Investigating')
    await cannedForm
      .locator('[name="body"]')
      .fill('Thanks — we are investigating this now.')
    await cannedForm.getByRole('button', {name: 'Add canned reply'}).click()
    await expect(
      adminFrame.getByRole('button', {name: 'Investigating', exact: true})
    ).toBeVisible()

    await adminFrame.getByTestId('conversation-status').selectOption('pending')
    await adminFrame.getByTestId('conversation-priority').selectOption('urgent')
    await adminFrame.getByTestId('conversation-tags').fill('checkout, browser')
    const ticketUpdated = page.waitForResponse(
      response =>
        response.request().method() === 'PUT' &&
        response.url().includes('/api/v1/ext/supportchat/conversations/')
    )
    await adminFrame.getByRole('button', {name: 'Save ticket'}).click()
    await ticketUpdated
    await expect(adminFrame.locator('main.sc-shell')).toHaveAttribute(
      'data-loading',
      ''
    )
    await expect(adminFrame.getByTestId('conversation-status')).toHaveValue(
      'pending'
    )
    await expect(adminFrame.getByTestId('conversation-priority')).toHaveValue(
      'urgent'
    )
    await expect(adminFrame.getByTestId('conversation-tags')).toHaveValue(
      'checkout, browser'
    )

    await adminFrame
      .getByTestId('internal-note')
      .fill('Only agents should see this diagnostic note.')
    await adminFrame.getByRole('button', {name: 'Add internal note'}).click()
    await expect(
      adminFrame.getByText('Only agents should see this diagnostic note.')
    ).toBeVisible()

    await adminFrame
      .getByRole('button', {name: 'Investigating', exact: true})
      .click()
    await expect(adminFrame.getByTestId('agent-reply')).toHaveValue(
      'Thanks — we are investigating this now.'
    )
    await adminFrame.getByRole('button', {name: 'Send'}).click()
    await expect(
      visitorFrame.getByText('Thanks — we are investigating this now.')
    ).toBeVisible({timeout: 60_000})
    await expect(
      visitorFrame.getByText('Only agents should see this diagnostic note.')
    ).toHaveCount(0)

    await visitorPage.waitForTimeout(1_100)
    await visitorFrame
      .locator('#message-box [name="body"]')
      .fill('It also happens in a private window.')
    await visitorFrame.getByTestId('visitor-send').click()
    await expect(
      adminFrame.getByText('It also happens in a private window.')
    ).toBeVisible({timeout: 60_000})
    await expect(adminFrame.getByTestId('unread-count')).toHaveText('1')

    await adminFrame.getByRole('button', {name: 'Resolve'}).click()
    await expect(visitorFrame.getByText('resolved').first()).toBeVisible({
      timeout: 60_000
    })
    await expect(adminFrame.locator('main.sc-shell')).toHaveAttribute(
      'data-loading',
      ''
    )
    await expect(adminFrame.getByTestId('conversation-status')).toHaveValue(
      'resolved'
    )
    await adminFrame.getByTestId('conversation-status').selectOption('open')
    const ticketReopened = page.waitForResponse(
      response =>
        response.request().method() === 'PUT' &&
        response.url().includes('/api/v1/ext/supportchat/conversations/')
    )
    await adminFrame.getByRole('button', {name: 'Save ticket'}).click()
    await ticketReopened
    await expect(adminFrame.locator('main.sc-shell')).toHaveAttribute(
      'data-loading',
      ''
    )
    await expect(visitorFrame.getByText('open').first()).toBeVisible({
      timeout: 60_000
    })

    await visitorPage.goto(publicPath)
    visitorFrame = await extensionFrame(visitorPage, 'Support Chat')
    await expect(
      visitorFrame.getByText('Thanks — we are investigating this now.')
    ).toBeVisible({timeout: 60_000})
  } finally {
    await visitorRecorder.finish()
    await visitorContext.close()
  }
})

async function supportInbox(
  page: Parameters<typeof extensionApi>[0],
  inboxName: string
): Promise<Record<string, unknown>> {
  const response = await extensionApi(
    page,
    SUPPORTCHAT.extId,
    'GET',
    '/inboxes?rowsPerPage=100'
  )
  const inboxes = Array.isArray(response.inboxes)
    ? response.inboxes.filter(isRecord)
    : []
  const inbox = inboxes.find(item => item.name === inboxName)
  if (!inbox) {
    throw new Error(`Support inbox not found: ${JSON.stringify(response)}`)
  }
  return inbox
}
