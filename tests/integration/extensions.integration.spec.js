const {test, expect} = require('@playwright/test')

const {
  apiKeyHeaders,
  clearMirror,
  createAccount,
  createWallet,
  decodePayment,
  expectStatus,
  fetchManifest,
  getPayment,
  getPayments,
  getWallet,
  initServer,
  jsonRequest,
  latestRelease,
  loginAdmin,
  lnurlScan,
  mirrorUrl,
  pageStatus,
  pollPayment,
  pollWalletBalance,
  responseJson,
  textRequest,
  topUpWallet,
  uninstallExtension
} = require('./helpers')

test.describe.configure({mode: 'serial'})

let baseURL
let adminContext
let adminWallet
let adminSession
let extensionById
let contextFactory
const contexts = []
const browserContexts = []

async function newContext() {
  const context = await contextFactory.newContext({
    baseURL,
    extraHTTPHeaders: {
      Accept: 'application/json, text/plain, */*'
    }
  })
  contexts.push(context)
  return context
}

async function newUser(name) {
  const context = await newContext()
  const account = await createAccount(context, `${name}-${Date.now()}`)
  return {context, ...account}
}

async function newBrowserSession(browser, account) {
  const uiContext = await browser.newContext({baseURL})
  browserContexts.push(uiContext)
  if (account?.userId) {
    await textRequest(uiContext.request, 'get', '/')
    await jsonRequest(uiContext.request, 'post', '/api/v1/auth/usr', {
      data: {usr: account.userId}
    })
  } else {
    await loginAdmin(uiContext.request)
  }
  const page = await uiContext.newPage()
  page.setDefaultTimeout(45_000)
  return {uiContext, page}
}

async function newUserWithUi(browser, name) {
  const user = await newUser(name)
  return {...user, ...(await newBrowserSession(browser, user))}
}

async function getAdminSession(browser) {
  if (!adminSession) {
    adminSession = {
      ...adminWallet,
      ...(await newBrowserSession(browser))
    }
  }
  return adminSession
}

function extensionName(extensionId) {
  return extensionById?.get(extensionId)?.name || extensionId
}

async function refreshExtensionCatalog(context = adminContext) {
  const extensions = await jsonRequest(context, 'get', '/api/v1/extension')
  for (const extension of extensions) {
    const id = extension.id || extension.code
    if (id) {
      extensionById.set(id, {
        id,
        name: extension.name || extension.title || id
      })
    }
  }
}

function responsePath(response) {
  return new URL(response.url()).pathname
}

function responseMatches(response, method, path) {
  return (
    response.request().method() === method && responsePath(response) === path
  )
}

async function clickAndCheckResponse(
  page,
  method,
  path,
  action,
  expected = 200,
  timeout = 45_000
) {
  const responsePromise = page.waitForResponse(
    response => responseMatches(response, method, path),
    {timeout}
  )
  await action()
  const response = await responsePromise
  await expectStatus(response, expected, `${method} ${path}`)
  return response
}

async function clickAndGetJsonResponse(
  page,
  method,
  path,
  action,
  expected = 200
) {
  const response = await clickAndCheckResponse(
    page,
    method,
    path,
    action,
    expected
  )
  return responseJson(response)
}

async function gotoPage(page, path, expected = 200) {
  const response = await page.goto(path)
  if (response) {
    await expectStatus(response, expected, `GET ${path}`)
  }
  await page.waitForFunction(() => window.LNbits && window.g)
  const credentialsButton = page.getByRole('button', {name: /i understand/i})
  if (await credentialsButton.isVisible({timeout: 1000}).catch(() => false)) {
    await credentialsButton.click()
  }
  return response
}

async function gotoWallet(session, walletId = session.walletId) {
  await gotoPage(session.page, `/wallet/${walletId}`)
  await expect(
    session.page.getByRole('button', {name: /receive/i})
  ).toBeVisible()
}

async function fillQuasarField(scope, label, value) {
  const field = scope
    .locator('.q-field')
    .filter({hasText: label})
    .locator('input, textarea')
    .first()
  await field.fill(String(value))
}

async function createInvoiceViaUi(session, amount, memo) {
  await gotoWallet(session)
  await session.page.getByRole('button', {name: /receive/i}).click()
  const dialog = session.page
    .locator('.q-dialog')
    .filter({hasText: 'Create Invoice'})
    .last()
  await fillQuasarField(dialog, 'Amount (sat)', amount)
  await fillQuasarField(dialog, 'Memo', memo)
  const invoice = await clickAndGetJsonResponse(
    session.page,
    'POST',
    '/api/v1/payments',
    () => dialog.getByRole('button', {name: /create invoice/i}).click(),
    [200, 201]
  )
  expect(invoice.bolt11).toBeTruthy()
  return invoice
}

async function payInvoiceViaUi(session, bolt11, expected = 201) {
  await gotoWallet(session)
  await session.page.getByRole('button', {name: /send/i}).click()
  const dialog = session.page.locator('.q-dialog').last()
  await fillQuasarField(dialog, 'Paste an invoice', bolt11)
  await dialog.getByRole('button', {name: /read/i}).click()
  await expect(dialog.getByRole('button', {name: /^pay$/i})).toBeVisible()
  return clickAndGetJsonResponse(
    session.page,
    'POST',
    '/api/v1/payments',
    () => dialog.getByRole('button', {name: /^pay$/i}).click(),
    expected
  )
}

async function payLnurlViaUi(session, lnurl, amountMsat, comment) {
  await gotoWallet(session)
  await session.page.getByRole('button', {name: /send/i}).click()
  const dialog = session.page.locator('.q-dialog').last()
  await fillQuasarField(dialog, 'Paste an invoice', lnurl)
  await clickAndCheckResponse(session.page, 'POST', '/api/v1/lnurlscan', () =>
    dialog.getByRole('button', {name: /read/i}).click()
  )
  await fillQuasarField(dialog, 'Amount (sat)', amountMsat / 1000)
  if (comment) {
    await fillQuasarField(dialog, 'Comment (optional)', comment)
  }
  const payment = await clickAndGetJsonResponse(
    session.page,
    'POST',
    '/api/v1/payments/lnurl',
    () => dialog.getByRole('button', {name: /^send$/i}).click()
  )
  expect(payment.payment_hash).toBeTruthy()
  return payment
}

async function withdrawLnurlViaUi(
  session,
  lnurl,
  amount = 10,
  memo = 'withdraw 1',
  walletId = session.walletId
) {
  await gotoWallet(session, walletId)
  await session.page.getByRole('button', {name: /send/i}).click()
  const scanDialog = session.page.locator('.q-dialog').last()
  await fillQuasarField(scanDialog, 'Paste an invoice', lnurl)
  await clickAndCheckResponse(session.page, 'POST', '/api/v1/lnurlscan', () =>
    scanDialog.getByRole('button', {name: /read/i}).click()
  )
  const withdrawDialog = session.page
    .locator('.q-dialog')
    .filter({hasText: 'Withdraw from'})
    .last()
  await fillQuasarField(withdrawDialog, 'Amount (sat)', amount)
  await fillQuasarField(withdrawDialog, 'Memo', memo)
  const payment = await clickAndGetJsonResponse(
    session.page,
    'POST',
    '/api/v1/payments',
    () => withdrawDialog.getByRole('button', {name: /withdraw from/i}).click(),
    [200, 201]
  )
  expect(payment.payment_hash).toBeTruthy()
  return payment
}

async function openExtensionsPage(session, tab = 'installed') {
  const extensionsLoaded = session.page
    .waitForResponse(response =>
      responseMatches(response, 'GET', '/api/v1/extension')
    )
    .catch(() => null)
  await gotoPage(session.page, '/extensions')
  await extensionsLoaded
  await session.page.waitForLoadState('networkidle').catch(() => null)
  await session.page.getByLabel(/search extensions/i).waitFor()
  const tabButton = session.page.getByRole('tab', {
    name: new RegExp(`^${tab}$`, 'i')
  })
  await tabButton.click()
  await expect(tabButton).toHaveAttribute('aria-selected', 'true')
}

async function findExtensionCard(session, extensionId, tab = 'installed') {
  await openExtensionsPage(session, tab)
  const name = extensionName(extensionId)
  await session.page.getByLabel(/search extensions/i).fill(name)
  const card = session.page
    .locator('.q-card')
    .filter({
      has: session.page.locator('.text-h5').filter({
        hasText: new RegExp(`^${name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}$`)
      })
    })
    .first()
  await expect(card).toBeVisible()
  return card
}

async function openExtensionManager(session, extensionId, tab = 'installed') {
  const card = await findExtensionCard(session, extensionId, tab)
  await clickAndCheckResponse(
    session.page,
    'GET',
    `/api/v1/extension/${extensionId}/releases`,
    () => card.getByRole('button', {name: /manage/i}).click()
  )
  const dialog = session.page.locator('.q-dialog').filter({hasText: 'Releases'})
  await expect(dialog.last()).toBeVisible()
  return dialog.last()
}

async function installExtensionVersionViaUi(session, extensionId, version) {
  let dialog
  try {
    dialog = await openExtensionManager(session, extensionId, 'installed')
  } catch {
    dialog = await openExtensionManager(session, extensionId, 'all')
  }
  const versionLabel = dialog.getByText(version, {exact: true}).first()
  if (!(await versionLabel.isVisible({timeout: 1000}).catch(() => false))) {
    await dialog
      .getByRole('button', {name: /expand/i})
      .first()
      .click()
  }
  await versionLabel.click()
  const installButton = dialog.getByRole('button', {name: /^install$/i}).first()
  if (!(await installButton.isVisible({timeout: 1000}).catch(() => false))) {
    await dialog.getByRole('button', {name: /close/i}).last().click()
    return null
  }
  const activatePromise = session.page
    .waitForResponse(response =>
      responseMatches(
        response,
        'PUT',
        `/api/v1/extension/${extensionId}/activate`
      )
    )
    .catch(() => null)
  let installResponsePromise = session.page.waitForResponse(response =>
    responseMatches(response, 'POST', '/api/v1/extension')
  )
  await installButton.click()
  const grantButton = session.page.getByRole('button', {
    name: /grant and install/i
  })
  if (await grantButton.isVisible({timeout: 1000}).catch(() => false)) {
    installResponsePromise.catch(() => null)
    installResponsePromise = session.page.waitForResponse(response =>
      responseMatches(response, 'POST', '/api/v1/extension')
    )
    await grantButton.click()
  }
  const installResponse = await installResponsePromise
  await expectStatus(installResponse, [200, 201], 'POST /api/v1/extension')
  const activateResponse = await activatePromise
  if (activateResponse) {
    await expectStatus(
      activateResponse,
      200,
      `PUT /api/v1/extension/${extensionId}/activate`
    )
  }
  return responseJson(installResponse)
}

async function installLatestExtensionViaUi(session, extensionId) {
  const release = await latestRelease(session.uiContext.request, extensionId)
  return installExtensionVersionViaUi(session, extensionId, release.version)
}

async function ensureExtensionsInstalledViaUi(session, extensionIds) {
  for (const extensionId of extensionIds) {
    const installed = await findExtensionCard(session, extensionId, 'installed')
      .then(() => true)
      .catch(() => false)
    if (!installed) {
      await installLatestExtensionViaUi(session, extensionId)
    }
    await setExtensionActiveViaUi(session, extensionId, true)
  }
}

async function enableExtensionViaUi(session, extensionId) {
  const card = await findExtensionCard(session, extensionId)
  const alreadyEnabled =
    (await card.getByRole('button', {name: /open/i}).isVisible()) ||
    (await card.getByRole('button', {name: /^disable$/i}).isVisible())
  if (alreadyEnabled) {
    return null
  }
  const payToEnableButton = card.getByRole('button', {name: /pay to enable/i})
  if (await payToEnableButton.isVisible()) {
    await payToEnableButton.click()
    const dialog = session.page
      .locator('.q-dialog')
      .filter({hasText: 'Recheck'})
    await expect(dialog.last()).toBeVisible()
    return clickAndGetJsonResponse(
      session.page,
      'PUT',
      `/api/v1/extension/${extensionId}/enable`,
      () => session.page.getByText(/recheck/i).click()
    )
  }
  return clickAndGetJsonResponse(
    session.page,
    'PUT',
    `/api/v1/extension/${extensionId}/enable`,
    () => card.getByRole('button', {name: /^enable$/i}).click()
  )
}

async function disableExtensionViaUi(session, extensionId) {
  const card = await findExtensionCard(session, extensionId)
  if (!(await card.getByRole('button', {name: /^disable$/i}).isVisible())) {
    return null
  }
  return clickAndGetJsonResponse(
    session.page,
    'PUT',
    `/api/v1/extension/${extensionId}/disable`,
    () => card.getByRole('button', {name: /^disable$/i}).click()
  )
}

async function setExtensionActiveViaUi(
  session,
  extensionId,
  active,
  expected = 200
) {
  const card = await findExtensionCard(session, extensionId)
  const action = active ? 'activate' : 'deactivate'
  const toggle = card.locator('.q-toggle').first()
  const alreadySet = await toggle
    .innerText()
    .then(text =>
      text.toLowerCase().includes(active ? 'activated' : 'deactivated')
    )
  if (alreadySet && expected === 200) return null
  return clickAndGetJsonResponse(
    session.page,
    'PUT',
    `/api/v1/extension/${extensionId}/${action}`,
    () => toggle.click(),
    expected
  )
}

async function payToEnableExtensionViaUi(session, extensionId) {
  const card = await findExtensionCard(session, extensionId)
  await card.getByRole('button', {name: /pay to enable/i}).click()
  const dialog = session.page.locator('.q-dialog').filter({hasText: 'Recheck'})
  await expect(dialog.last()).toBeVisible()
  const invoice = await clickAndGetJsonResponse(
    session.page,
    'PUT',
    `/api/v1/extension/${extensionId}/invoice/enable`,
    () =>
      dialog
        .last()
        .getByRole('button', {name: /show qr/i})
        .click()
  )
  await dialog.last().getByRole('button', {name: /close/i}).click()
  await payInvoiceViaUi(session, invoice.payment_request || invoice.bolt11)
  const cardAfterPayment = await findExtensionCard(session, extensionId)
  if (
    await cardAfterPayment.getByRole('button', {name: /^enable$/i}).isVisible()
  ) {
    return clickAndGetJsonResponse(
      session.page,
      'PUT',
      `/api/v1/extension/${extensionId}/enable`,
      () => cardAfterPayment.getByRole('button', {name: /^enable$/i}).click()
    )
  }
  await cardAfterPayment.getByRole('button', {name: /pay to enable/i}).click()
  return clickAndGetJsonResponse(
    session.page,
    'PUT',
    `/api/v1/extension/${extensionId}/enable`,
    () => session.page.getByText(/recheck/i).click()
  )
}

async function createPayLink(context, account, index, overrides = {}) {
  const data = compactObject({
    description: `receive payments ${index}`,
    min: 11,
    comment_chars: 128,
    webhook_url: mirrorUrl(),
    webhook_headers: '{"h1": "1"}',
    webhook_body: '{"b2": 2}',
    success_text: 'All goood!',
    success_url: 'https://lnbits.com',
    max: Number(`${index}1`),
    ...overrides
  })
  const link = await jsonRequest(context, 'post', '/lnurlp/api/v1/links', {
    headers: apiKeyHeaders(account.adminkey),
    data,
    expected: 201
  })

  expect(link.id).toBeTruthy()
  expect(link.wallet).toBe(account.walletId)
  return link
}

async function createWithdrawLink(context, account, index, overrides = {}) {
  const link = await jsonRequest(context, 'post', '/withdraw/api/v1/links', {
    headers: apiKeyHeaders(account.adminkey),
    data: {
      is_unique: false,
      use_custom: false,
      title: `withdraw ${index}`,
      min_withdrawable: 10,
      max_withdrawable: index * 10,
      uses: 5,
      wait_time: 1,
      webhook_url: mirrorUrl(),
      webhook_headers: '{"h1": "1"}',
      webhook_body: '{"b2": 2}',
      custom_url: null,
      ...overrides
    },
    expected: 201
  })

  expect(link.id).toBeTruthy()
  expect(link.wallet).toBe(account.walletId)
  expect(link.title).toBe(`withdraw ${index}`)
  return link
}

async function withdrawLnurl(
  context,
  receiveWallet,
  withdrawResponse,
  amount = 10,
  memo = 'withdraw 1'
) {
  return jsonRequest(context, 'post', '/api/v1/payments', {
    headers: apiKeyHeaders(receiveWallet.inkey),
    data: {
      out: false,
      amount,
      memo,
      unit: 'sat',
      lnurl_withdraw: withdrawResponse
    },
    expected: 201
  })
}

async function lndhubHeaders(accessToken) {
  return {Authorization: `Bearer ${accessToken}`}
}

async function createNip5Domain(context, account, extra = {}) {
  const {cost_extra: extraCost = {}, ...extraFields} = extra
  return jsonRequest(context, 'post', '/nostrnip5/api/v1/domain', {
    headers: apiKeyHeaders(account.adminkey),
    data: {
      cost_extra: {
        max_years: '3',
        char_count_cost: [],
        rank_cost: [],
        ...extraCost
      },
      wallet: account.walletId,
      currency: 'USD',
      domain: `nostr-${Date.now()}.com`,
      cost: '100',
      ...extraFields
    },
    expected: 201
  })
}

async function createUserNip5Address(context, account, domainId, localPart) {
  const address = await jsonRequest(
    context,
    'post',
    `/nostrnip5/api/v1/user/domain/${domainId}/address`,
    {
      headers: apiKeyHeaders(account.adminkey),
      data: {
        config: {relays: ['relay.nostr.com']},
        pubkey:
          '04c915daefee38317fa734444acee390a8269fe5810b2241e5e6dd343dfbecc9',
        local_part: localPart,
        domain_id: domainId
      },
      expected: 201
    }
  )
  expect(address.id).toBeTruthy()
  return address
}

async function createNip5Address(
  context,
  account,
  domainId,
  localPart,
  pubkey
) {
  const address = await jsonRequest(
    context,
    'post',
    `/nostrnip5/api/v1/domain/${domainId}/address`,
    {
      headers: apiKeyHeaders(account.adminkey),
      data: {
        config: {relays: ['relay.nostr.com']},
        pubkey,
        local_part: localPart,
        domain_id: domainId
      },
      expected: 201
    }
  )
  expect(address.id).toBeTruthy()
  return address
}

async function activateNip5Address(context, account, domainId, addressId) {
  return jsonRequest(
    context,
    'put',
    `/nostrnip5/api/v1/domain/${domainId}/address/${addressId}/activate`,
    {
      headers: apiKeyHeaders(account.adminkey)
    }
  )
}

async function getNostrJson(context, domainId, name, expected = 200) {
  return jsonRequest(
    context,
    'get',
    `/nostrnip5/api/v1/domain/${domainId}/nostr.json`,
    {
      params: {name},
      expected
    }
  )
}

async function buyNip5Address(context, account, domainId, localPart, options) {
  return jsonRequest(
    context,
    'post',
    `/nostrnip5/api/v1/user/domain/${domainId}/address`,
    {
      headers: apiKeyHeaders(account.adminkey),
      data: {
        domain_id: domainId,
        local_part: localPart,
        pubkey: options.pubkey,
        years: options.years,
        promo_code: options.promo_code ?? null,
        referer: options.referer ?? null,
        create_invoice: options.create_invoice ?? false
      },
      expected: options.expected ?? 200
    }
  )
}

async function createAuctionRoom(context, owner, data) {
  const room = await jsonRequest(
    context,
    'post',
    '/auction_house/api/v1/auction_room',
    {
      headers: apiKeyHeaders(owner.adminkey),
      data,
      expected: 201
    }
  )
  expect(room.id).toBeTruthy()
  return room
}

async function updateAuctionRoom(context, owner, data) {
  const room = await jsonRequest(
    context,
    'put',
    '/auction_house/api/v1/auction_room',
    {
      headers: apiKeyHeaders(owner.adminkey),
      data
    }
  )
  expect(room.id).toBe(data.id)
  return room
}

async function createAuctionItem(context, seller, roomId, data) {
  const item = await jsonRequest(
    context,
    'post',
    `/auction_house/api/v1/items/${roomId}`,
    {
      headers: apiKeyHeaders(seller.adminkey),
      data,
      expected: 201
    }
  )
  expect(item.id).toBeTruthy()
  return item
}

async function bidOnItem(context, bidder, itemId, amount, memo) {
  const bid = await jsonRequest(
    context,
    'put',
    `/auction_house/api/v1/bids/${itemId}`,
    {
      headers: apiKeyHeaders(bidder.adminkey),
      data: {amount, ln_address: '', memo},
      expected: 201
    }
  )
  expect(bid.payment_request).toBeTruthy()
  return bid
}

test.beforeAll(async ({playwright}, testInfo) => {
  baseURL = testInfo.project.use.baseURL
  contextFactory = playwright.request
  adminContext = await newContext()
  adminWallet = await initServer(adminContext)
  const manifest = await fetchManifest()
  extensionById = new Map(
    manifest.extensions.map(extension => [extension.id, extension])
  )
})

test.afterAll(async () => {
  await Promise.all(contexts.map(context => context.dispose()))
  await Promise.all(browserContexts.map(context => context.close()))
})

function compactObject(value) {
  return Object.fromEntries(
    Object.entries(value).filter(([, entry]) => entry !== undefined)
  )
}

test('001 extensions can be installed, enabled, disabled, and re-enabled', async ({
  browser
}) => {
  test.setTimeout(45 * 60 * 1000)

  const admin = await getAdminSession(browser)
  const excluded = new Set([
    'discordbot',
    'usermanager',
    'lnurldevice',
    'scheduler',
    'deezy',
    'webpages'
  ])
  const adminExtensions = new Set(['nostrclient'])
  const extensionIds = [...new Set([...extensionById.keys()])]
    .filter(extension => !excluded.has(extension))
    .sort()

  expect(extensionIds.length).toBeGreaterThan(0)

  for (const extension of extensionIds) {
    await uninstallExtension(adminContext, extension)
    await pageStatus(adminContext, `/${extension}`, [200, 403, 404])
  }

  for (const extension of extensionIds) {
    await installLatestExtensionViaUi(admin, extension)
    await pageStatus(adminContext, `/${extension}`, [200, 403, 404])
    await enableExtensionViaUi(admin, extension)
    await pageStatus(
      adminContext,
      `/${extension}`,
      adminExtensions.has(extension) ? [200, 403] : 200
    )
    await disableExtensionViaUi(admin, extension)
    await pageStatus(adminContext, `/${extension}`, [200, 403, 404])
    await enableExtensionViaUi(admin, extension)
    await pageStatus(
      adminContext,
      `/${extension}`,
      adminExtensions.has(extension) ? [200, 403] : 200
    )
  }
})

test('002 lnurlp and withdraw scenarios', async ({browser}) => {
  test.setTimeout(5 * 60 * 1000)
  await clearMirror()

  const admin = await getAdminSession(browser)
  await ensureExtensionsInstalledViaUi(admin, ['lnurlp', 'withdraw'])
  const user = await newUserWithUi(browser, 'lnurl')
  await enableExtensionViaUi(user, 'lnurlp')
  await pageStatus(user.context, '/lnurlp/')

  const initialPayLinks = await jsonRequest(
    user.context,
    'get',
    '/lnurlp/api/v1/links',
    {
      headers: apiKeyHeaders(user.inkey),
      params: {all_wallets: true}
    }
  )
  expect(initialPayLinks).toEqual([])

  let userBalanceSats = 0
  for (const index of [1, 2, 3]) {
    const payLink = await createPayLink(user.context, user, index)
    await pageStatus(user.context, `/lnurlp/link/${payLink.id}`)
    const fetched = await jsonRequest(
      user.context,
      'get',
      `/lnurlp/api/v1/links/${payLink.id}`,
      {
        headers: apiKeyHeaders(user.inkey),
        params: {all_wallets: true}
      }
    )
    expect(fetched.description).toBe(`receive payments ${index}`)

    const lnurlResponse = await lnurlScan(
      user.context,
      fetched.lnurl,
      user.adminkey
    )
    expect(lnurlResponse.tag).toBe('payRequest')
    expect(lnurlResponse.commentAllowed).toBe(128)

    for (let paymentIndex = 0; paymentIndex < 2; paymentIndex++) {
      const payment = await payLnurlViaUi(
        admin,
        fetched.lnurl,
        (10 + index) * 1000,
        `receive payments ${index}`
      )
      expect(payment.payment_hash).toBeTruthy()
      userBalanceSats += 10 + index
      await pollWalletBalance(user.context, user.inkey, userBalanceSats * 1000)
      const stored = await pollPayment(
        user.context,
        user.inkey,
        payment.payment_hash,
        result => Boolean(result?.details?.extra?.wh_response)
      )
      expect(stored.details.extra.wh_response).toContain('"b2":2')
      expect(stored.details.extra.wh_response).toContain(payment.payment_hash)
    }
  }

  await enableExtensionViaUi(user, 'withdraw')
  await pageStatus(user.context, '/withdraw/')
  const initialWithdrawLinks = await jsonRequest(
    user.context,
    'get',
    '/withdraw/api/v1/links',
    {
      headers: apiKeyHeaders(user.inkey),
      params: {all_wallets: true}
    }
  )
  expect(initialWithdrawLinks.data ?? initialWithdrawLinks).toEqual([])

  const receiveWallet = await createWallet(user.context, 'receive wallet')

  for (const index of [1, 2, 3]) {
    const withdrawLink = await createWithdrawLink(user.context, user, index)
    await pageStatus(user.context, `/withdraw/${withdrawLink.id}`)
    const fetched = await jsonRequest(
      user.context,
      'get',
      `/withdraw/api/v1/links/${withdrawLink.id}`,
      {
        headers: apiKeyHeaders(user.inkey),
        params: {all_wallets: true}
      }
    )
    expect(fetched.title).toBe(`withdraw ${index}`)
    const lnurlResponse = await lnurlScan(
      user.context,
      fetched.lnurl,
      user.adminkey
    )
    expect(lnurlResponse.tag).toBe('withdrawRequest')

    for (let withdrawIndex = 0; withdrawIndex < 2; withdrawIndex++) {
      const withdrawal = await withdrawLnurlViaUi(
        user,
        fetched.lnurl,
        10,
        `withdraw ${index}`,
        receiveWallet.walletId
      )
      expect(withdrawal.payment_hash).toBeTruthy()
      userBalanceSats -= 10
      await pollWalletBalance(user.context, user.inkey, userBalanceSats * 1000)
      await getPayment(
        user.context,
        receiveWallet.inkey,
        withdrawal.payment_hash
      )
    }
  }

  await pollWalletBalance(user.context, receiveWallet.inkey, 60_000)
})

test('003 tpos payments, tips, and ATM withdraw', async ({browser}) => {
  test.setTimeout(5 * 60 * 1000)

  const admin = await getAdminSession(browser)
  await ensureExtensionsInstalledViaUi(admin, ['tpos'])
  const user = await newUserWithUi(browser, 'tpos')
  await enableExtensionViaUi(user, 'tpos')
  await pageStatus(user.context, '/tpos/')

  const tposs = await jsonRequest(user.context, 'get', '/tpos/api/v1/tposs', {
    headers: apiKeyHeaders(user.inkey),
    params: {all_wallets: true}
  })
  expect(tposs).toEqual([])

  const tipsWallet = await createWallet(user.context, 'tips wallet')
  expect(tipsWallet.userId).toBe(user.userId)

  const tpos = await jsonRequest(user.context, 'post', '/tpos/api/v1/tposs', {
    headers: apiKeyHeaders(user.adminkey),
    data: {name: 'Test', wallet: user.walletId, currency: 'USD'},
    expected: 201
  })
  expect(tpos.wallet).toBe(user.walletId)

  const updated = await jsonRequest(
    user.context,
    'put',
    `/tpos/api/v1/tposs/${tpos.id}`,
    {
      headers: apiKeyHeaders(user.adminkey),
      data: {
        name: 'Test',
        wallet: user.walletId,
        currency: 'USD',
        tip_options: '[2, 5]',
        tip_wallet: tipsWallet.walletId
      }
    }
  )
  expect(updated.tip_wallet).toBe(tipsWallet.walletId)

  const atm = await jsonRequest(user.context, 'post', '/tpos/api/v1/tposs', {
    headers: apiKeyHeaders(user.adminkey),
    data: {
      withdraw_pin: 2222,
      withdraw_between: 1,
      name: 'Test ATM',
      wallet: user.walletId,
      currency: 'EUR',
      withdraw_limit: 100000
    },
    expected: 201
  })
  expect(atm.wallet).toBe(user.walletId)

  await pageStatus(user.context, `/tpos/${tpos.id}`)
  await jsonRequest(user.context, 'get', '/api/v1/rate/EUR')

  let expectedMerchantBalance = 0
  for (const amount of [21, 42]) {
    const invoice = await jsonRequest(
      user.context,
      'post',
      `/tpos/api/v1/tposs/${tpos.id}/invoices`,
      {
        headers: apiKeyHeaders(user.inkey),
        data: {
          amount,
          memo: 'TPoS test',
          ...(amount === 42 ? {tipAmount: 3} : {})
        },
        expected: 201
      }
    )
    expect(invoice.bolt11).toBeTruthy()
    await payInvoiceViaUi(admin, invoice.bolt11)
    await jsonRequest(
      user.context,
      'get',
      `/tpos/api/v1/tposs/${tpos.id}/invoices/${invoice.payment_hash}`,
      {headers: apiKeyHeaders(user.inkey)}
    )
    expectedMerchantBalance += amount
    await pollWalletBalance(
      user.context,
      user.inkey,
      expectedMerchantBalance * 1000
    )
  }

  await pageStatus(user.context, `/tpos/${atm.id}`)
  await jsonRequest(user.context, 'get', '/api/v1/rate/EUR')
  const atmInvoice = await jsonRequest(
    user.context,
    'post',
    `/tpos/api/v1/tposs/${atm.id}/invoices`,
    {
      headers: apiKeyHeaders(user.inkey),
      data: {amount: 11000, memo: 'TPoS test'},
      expected: 201
    }
  )
  await payInvoiceViaUi(admin, atmInvoice.bolt11)

  const beforeAdmin = await getWallet(adminContext, adminWallet.inkey)
  const beforeUser = await getWallet(user.context, user.inkey)
  const atmPin = await jsonRequest(
    user.context,
    'get',
    `/tpos/api/v1/atm/${atm.id}/2222`,
    {
      headers: apiKeyHeaders(adminWallet.adminkey)
    }
  )
  expect(atmPin.id).toBeTruthy()
  const withdraw = await jsonRequest(
    user.context,
    'get',
    `/tpos/api/v1/atm/withdraw/${atmPin.id}/100`,
    {
      headers: apiKeyHeaders(adminWallet.adminkey)
    }
  )
  const withdrawResponse = await jsonRequest(
    user.context,
    'get',
    `/tpos/api/v1/lnurl/${withdraw.id}/100`,
    {headers: apiKeyHeaders(adminWallet.adminkey)}
  )
  const payment = await withdrawLnurl(
    user.context,
    adminWallet,
    withdrawResponse,
    100,
    'TPoS withdraw'
  )
  expect(payment.payment_hash).toBeTruthy()
  await pollWalletBalance(
    adminContext,
    adminWallet.inkey,
    beforeAdmin.balance + 100_000
  )
  await pollWalletBalance(
    user.context,
    user.inkey,
    beforeUser.balance - 100_000
  )
})

test('004 tpos pay-to-enable flow', async ({browser}) => {
  test.setTimeout(5 * 60 * 1000)

  const admin = await getAdminSession(browser)
  await ensureExtensionsInstalledViaUi(admin, ['tpos'])
  const user = await newUserWithUi(browser, 'pay-to-enable')
  await topUpWallet(adminContext, user.walletId, 1000)

  const release = await latestRelease(adminContext, 'tpos')
  expect(release.version).toBeTruthy()
  await enableExtensionViaUi(admin, 'tpos')
  await jsonRequest(adminContext, 'put', '/api/v1/extension/tpos/sell', {
    data: {required: true, amount: 21, wallet: adminWallet.walletId}
  })

  await pageStatus(adminContext, '/tpos')

  await pageStatus(user.context, '/tpos', [200, 402, 403])
  const lowInvoice = await jsonRequest(
    user.context,
    'put',
    '/api/v1/extension/tpos/invoice/enable',
    {data: {amount: 1}, expected: 400}
  )
  expect(JSON.stringify(lowInvoice)).toContain('21')

  await jsonRequest(user.context, 'put', '/api/v1/extension/tpos/enable', {
    expected: 402
  })
  await payToEnableExtensionViaUi(user, 'tpos')
  await pageStatus(user.context, '/tpos')
  await disableExtensionViaUi(user, 'tpos')
  await enableExtensionViaUi(user, 'tpos')
  await pageStatus(user.context, '/tpos')

  await jsonRequest(adminContext, 'put', '/api/v1/extension/tpos/sell', {
    data: {required: false, amount: 0, wallet: adminWallet.walletId}
  })
})

test('005 lnurlw race limits successful withdrawals', async ({browser}) => {
  test.setTimeout(5 * 60 * 1000)

  const admin = await getAdminSession(browser)
  await ensureExtensionsInstalledViaUi(admin, ['lnurlp', 'withdraw'])
  const user = await newUserWithUi(browser, 'lnurl-race')
  await enableExtensionViaUi(user, 'lnurlp')
  await enableExtensionViaUi(user, 'withdraw')

  const payLink = await createPayLink(user.context, user, 1, {
    description: 'receive payments',
    min: 1,
    max: 100_000_000,
    webhook_url: undefined,
    webhook_headers: undefined,
    webhook_body: undefined
  })
  const payResponse = await jsonRequest(
    user.context,
    'get',
    `/lnurlp/${payLink.id}`
  )
  expect(payResponse.tag).toBe('payRequest')
  await payLnurlViaUi(admin, payLink.lnurl, 10_000_000, 'receive payments')

  const receiveWallet = await createWallet(user.context, 'race receive wallet')
  const withdrawLink = await createWithdrawLink(user.context, user, 1, {
    uses: 2,
    max_withdrawable: 10
  })
  const withdrawResponse = await jsonRequest(
    user.context,
    'get',
    `/withdraw/api/v1/lnurl/${withdrawLink.unique_hash}`
  )

  // The race assertion is intentionally API-driven: it needs concurrent calls,
  // not serialized browser clicks.
  const attempts = Array.from({length: 100}, () =>
    withdrawLnurl(
      user.context,
      receiveWallet,
      withdrawResponse,
      10,
      'withdraw 1'
    )
  )
  await Promise.all(attempts)

  const payments = await getPayments(user.context, receiveWallet.inkey)
  expect(payments).toHaveLength(100)
  const successCount = payments.filter(
    payment => payment.status === 'success'
  ).length
  expect(successCount).toBe(2)
})

test('006 watchonly, satspay, and tipjar scenario', async ({browser}) => {
  test.setTimeout(7 * 60 * 1000)
  await clearMirror()

  const admin = await getAdminSession(browser)
  await ensureExtensionsInstalledViaUi(admin, [
    'watchonly',
    'satspay',
    'tipjar'
  ])
  const user = await newUserWithUi(browser, 'watchonly-satspay-tipjar')
  await enableExtensionViaUi(user, 'watchonly')
  await pageStatus(user.context, `/watchonly/?usr=${user.userId}`)
  await jsonRequest(user.context, 'get', '/watchonly/api/v1/config', {
    headers: apiKeyHeaders(user.inkey)
  })
  await jsonRequest(user.context, 'get', '/watchonly/api/v1/wallet', {
    headers: apiKeyHeaders(user.inkey),
    params: {network: 'Mainnet'}
  })
  const onchain = await jsonRequest(
    user.context,
    'post',
    '/watchonly/api/v1/wallet',
    {
      headers: apiKeyHeaders(user.adminkey),
      data: {
        title: 'segwit',
        masterpub:
          'zpub6rsRjqj6BTbD9DjqrY4p14tUx5kdA8ZGCTJD99wZTxD5wfvCkyXKrK3s7M3B1eFN6NbRhmbDDRDC8LF3Bn5gmxxN9rF8mDpZsGC6isGrK1g',
        network: 'Mainnet',
        meta: '{"accountPath":"m/84\'/0\'/0\'"}'
      },
      expected: 201
    }
  )
  expect(onchain.id).toBeTruthy()
  await jsonRequest(
    user.context,
    'get',
    `/watchonly/api/v1/addresses/${onchain.id}`,
    {
      headers: apiKeyHeaders(user.inkey)
    }
  )
  await jsonRequest(
    user.context,
    'get',
    `/watchonly/api/v1/address/${onchain.id}`,
    {
      headers: apiKeyHeaders(user.inkey)
    }
  )

  await enableExtensionViaUi(user, 'satspay')
  await pageStatus(user.context, '/satspay/')
  await jsonRequest(user.context, 'get', '/satspay/api/v1/charges', {
    headers: apiKeyHeaders(user.inkey)
  })
  const onchainCharge = await jsonRequest(
    user.context,
    'post',
    '/satspay/api/v1/charge',
    {
      headers: apiKeyHeaders(user.adminkey),
      data: {
        onchain: true,
        onchainwallet: onchain.id,
        lnbits: false,
        description: 'Onchain Charge',
        time: 1111,
        amount: 1111,
        lnbitswallet: null
      },
      expected: 201
    }
  )
  expect(onchainCharge.id).toBeTruthy()

  await jsonRequest(user.context, 'post', '/satspay/api/v1/charge', {
    headers: apiKeyHeaders(user.adminkey),
    data: {
      onchain: false,
      onchainwallet: null,
      lnbits: true,
      description: 'lightning charge - to expire',
      time: 1,
      amount: 10,
      lnbitswallet: user.walletId,
      webhook: 'https://google.com',
      completelink: 'https://twitter.com',
      completelinktext: 'Have Fun'
    },
    expected: 201
  })

  let expectedBalanceSats = 0
  for (let index = 1; index <= 5; index++) {
    const amount = 9 + index
    const charge = await jsonRequest(
      user.context,
      'post',
      '/satspay/api/v1/charge',
      {
        headers: apiKeyHeaders(user.adminkey),
        data: {
          onchain: false,
          onchainwallet: null,
          lnbits: true,
          description: `lightning charge [${index}]`,
          time: 1220,
          amount,
          lnbitswallet: user.walletId,
          webhook: mirrorUrl(),
          completelink: 'https://twitter.com',
          completelinktext: 'Have Fun'
        },
        expected: 201
      }
    )
    expect(charge.payment_request).toBeTruthy()
    await pageStatus(user.context, `/satspay/${charge.id}`)
    await jsonRequest(
      user.context,
      'get',
      `/satspay/api/v1/charge/balance/${charge.id}`
    )
    await payInvoiceViaUi(admin, charge.payment_request)
    await expect
      .poll(async () => {
        const updatedCharge = await jsonRequest(
          user.context,
          'get',
          `/satspay/api/v1/charge/${charge.id}`
        )
        return Boolean(updatedCharge.paid || updatedCharge.lnbitswallet)
      })
      .toBeTruthy()
    expectedBalanceSats += amount
  }

  await pollWalletBalance(user.context, user.inkey, expectedBalanceSats * 1000)
  const charges = await jsonRequest(
    user.context,
    'get',
    '/satspay/api/v1/charges',
    {
      headers: apiKeyHeaders(user.inkey)
    }
  )
  expect(charges.length).toBeGreaterThanOrEqual(7)
  const payments = await getPayments(user.context, user.inkey)
  expect(payments.length).toBeGreaterThanOrEqual(6)

  await enableExtensionViaUi(user, 'tipjar')
  await pageStatus(user.context, `/tipjar/?usr=${user.userId}`)
  await jsonRequest(user.context, 'get', '/tipjar/api/v1/tipjars', {
    headers: apiKeyHeaders(user.inkey)
  })
  const tipjar = await jsonRequest(
    user.context,
    'post',
    '/tipjar/api/v1/tipjars',
    {
      headers: apiKeyHeaders(user.adminkey),
      data: {wallet: user.walletId, name: 'Nakamoto', webhook: mirrorUrl()},
      expected: 201
    }
  )
  expect(tipjar.id).toBeTruthy()
  await pageStatus(user.context, `/tipjar/${tipjar.id}`)

  for (let index = 1; index <= 5; index++) {
    const tip = await jsonRequest(user.context, 'post', '/tipjar/api/v1/tips', {
      headers: apiKeyHeaders(user.adminkey),
      data: {
        tipjar: tipjar.id,
        name: 'Hal',
        sats: 21,
        message: `Let's go ...${index}!`
      },
      expected: 201
    })
    expect(tip.redirect_url).toBeTruthy()
    const tipChargeId = tip.redirect_url.split('/').filter(Boolean).at(-1)
    const charge = await jsonRequest(
      user.context,
      'get',
      `/satspay/api/v1/charge/${tipChargeId}`
    )
    expect(charge.description).toBe(`Let's go ...${index}!`)
    const tips = await jsonRequest(user.context, 'get', '/tipjar/api/v1/tips', {
      headers: apiKeyHeaders(user.inkey)
    })
    expect(tips.length).toBe(index)
    await payInvoiceViaUi(admin, tip.payment_request || charge.payment_request)
    expectedBalanceSats += 21
    await pollWalletBalance(
      user.context,
      user.inkey,
      expectedBalanceSats * 1000
    )
  }
})

test('007 lndhub mobile wallet API scenario', async ({browser}) => {
  test.setTimeout(5 * 60 * 1000)

  const admin = await getAdminSession(browser)
  await ensureExtensionsInstalledViaUi(admin, ['lndhub'])
  const user = await newUserWithUi(browser, 'lndhub')
  await enableExtensionViaUi(user, 'lndhub')
  await pageStatus(user.context, '/lndhub/')
  await jsonRequest(user.context, 'post', '/api/v1/auth/logout')
  await jsonRequest(user.context, 'get', '/lndhub/ext/getinfo')

  for (const index of [1, 2, 3]) {
    const userInvoice = await createInvoiceViaUi(
      user,
      21,
      `user invoice ${index}`
    )
    await payInvoiceViaUi(admin, userInvoice.bolt11)
    const adminInvoice = await createInvoiceViaUi(
      admin,
      1,
      `admin invoice ${index}`
    )
    await payInvoiceViaUi(user, adminInvoice.bolt11)
  }

  const auth = await jsonRequest(user.context, 'post', '/lndhub/ext/auth', {
    data: {login: 'some_user', password: user.adminkey, refresh_token: ''}
  })
  expect(auth.access_token).toBeTruthy()
  const authHeaders = await lndhubHeaders(auth.access_token)

  const balance = await jsonRequest(
    user.context,
    'get',
    '/lndhub/ext/balance',
    {
      headers: authHeaders
    }
  )
  expect(balance.BTC.AvailableBalance).toBe(60)
  const txs = await jsonRequest(user.context, 'get', '/lndhub/ext/gettxs', {
    headers: authHeaders
  })
  expect(txs).toHaveLength(3)
  expect(txs.every(tx => tx.value === -1)).toBeTruthy()
  const invoices = await jsonRequest(
    user.context,
    'get',
    '/lndhub/ext/getuserinvoices',
    {
      headers: authHeaders
    }
  )
  expect(invoices).toHaveLength(3)
  expect(invoices.every(invoice => invoice.amt === 21)).toBeTruthy()

  const mobileInvoice = await jsonRequest(
    user.context,
    'post',
    '/lndhub/ext/addinvoice',
    {
      headers: authHeaders,
      data: {amt: 50, memo: '50 sats'}
    }
  )
  await payInvoiceViaUi(admin, mobileInvoice.payment_request)
  const invoicesAfter = await jsonRequest(
    user.context,
    'get',
    '/lndhub/ext/getuserinvoices',
    {
      headers: authHeaders
    }
  )
  expect(invoicesAfter).toHaveLength(4)

  const adminInvoice = await createInvoiceViaUi(admin, 30, '30 sats')
  const paid = await jsonRequest(
    user.context,
    'post',
    '/lndhub/ext/payinvoice',
    {
      headers: authHeaders,
      data: {invoice: adminInvoice.bolt11}
    }
  )
  expect(JSON.stringify(paid)).toContain('30 sats')
  const txsAfter = await jsonRequest(
    user.context,
    'get',
    '/lndhub/ext/gettxs',
    {
      headers: authHeaders
    }
  )
  expect(txsAfter).toHaveLength(4)
  const balanceAfter = await jsonRequest(
    user.context,
    'get',
    '/lndhub/ext/balance',
    {
      headers: authHeaders
    }
  )
  expect(balanceAfter.BTC.AvailableBalance).toBe(80)

  for (const [method, path, data] of [
    ['get', '/lndhub/ext/balance'],
    ['get', '/lndhub/ext/gettxs'],
    ['get', '/lndhub/ext/getuserinvoices'],
    ['post', '/lndhub/ext/addinvoice', {amt: 50, memo: '50 sats'}],
    ['post', '/lndhub/ext/payinvoice', {invoice: adminInvoice.bolt11}]
  ]) {
    await jsonRequest(user.context, method, path, {data, expected: 400})
  }
})

test('008 lnaddress and lnurlp redirect conflict handling', async ({
  browser
}) => {
  test.setTimeout(10 * 60 * 1000)

  const admin = await getAdminSession(browser)
  await jsonRequest(adminContext, 'patch', '/admin/api/v1/settings', {
    data: {
      lnbits_extensions_manifests: [
        'https://raw.githubusercontent.com/lnbits/lnbits-extensions/main/extensions.json',
        'https://raw.githubusercontent.com/lnbits/lnaddress/refs/heads/main/manifest.json'
      ]
    }
  })
  await refreshExtensionCatalog(adminContext)
  await uninstallExtension(adminContext, 'lnaddress')

  await installLatestExtensionViaUi(admin, 'lnurlp')
  await installLatestExtensionViaUi(admin, 'lnaddress')
  await setExtensionActiveViaUi(admin, 'lnurlp', false)
  const conflict = await setExtensionActiveViaUi(admin, 'lnurlp', true, 400)
  expect(JSON.stringify(conflict)).toContain('Already mapped')
  await setExtensionActiveViaUi(admin, 'lnaddress', false)
  await setExtensionActiveViaUi(admin, 'lnurlp', true)
})

test('009 example extension can downgrade and upgrade data shape', async ({
  browser
}) => {
  test.setTimeout(10 * 60 * 1000)

  const admin = await getAdminSession(browser)
  async function installAndCheck(testVersion, extensionVersion) {
    const releases = await jsonRequest(
      adminContext,
      'get',
      '/api/v1/extension/example/releases'
    )
    const release = releases.find(item => item.version === extensionVersion)
    expect(release).toBeTruthy()
    await installExtensionVersionViaUi(admin, 'example', release.version)
    await enableExtensionViaUi(admin, 'example')
    const page = await textRequest(adminContext, 'get', '/example')
    expect(page).toContain(
      `Do not remove. Test install extension version: ${testVersion}`
    )
    const response = await jsonRequest(
      adminContext,
      'get',
      '/example/api/v1/test/00000000'
    )
    expect(response.version).toBe(String(testVersion))
    expect(response.test_id).toBe('00000000')
  }

  await installAndCheck(1, '1.0.1')
  await installAndCheck(2, '1.0.6')
  await installAndCheck(1, '1.0.1')
  await installAndCheck(2, '1.0.6')
  await installAndCheck(1, '1.0.1')
})

test('010 nostrnip5 domain, search, pricing, and referral flow', async ({
  browser
}) => {
  test.setTimeout(10 * 60 * 1000)

  const admin = await getAdminSession(browser)
  await ensureExtensionsInstalledViaUi(admin, ['nostrnip5', 'lnurlp'])
  const anonymous = await newContext()
  await textRequest(anonymous, 'patch', '/nostrnip5/api/v1/domain/ranking/0', {
    data: 'reserved_a\r\nreserved_b',
    headers: {'content-type': 'text/plain'},
    expected: 401
  })
  await enableExtensionViaUi(admin, 'nostrnip5')
  await enableExtensionViaUi(admin, 'lnurlp')
  await textRequest(
    adminContext,
    'patch',
    '/nostrnip5/api/v1/domain/ranking/0',
    {
      data: 'reserved_a\r\nreserved_b',
      headers: {'content-type': 'text/plain'}
    }
  )
  await textRequest(
    adminContext,
    'patch',
    '/nostrnip5/api/v1/domain/ranking/200',
    {
      data: 'rank_200_a\r\nrank_200_b\r\nyyy',
      headers: {'content-type': 'text/plain'}
    }
  )
  await textRequest(
    adminContext,
    'patch',
    '/nostrnip5/api/v1/domain/ranking/1000',
    {
      data: 'rank_1000_a\r\nrank_1000_b\r\nrank_1000_c\r\nxxx',
      headers: {'content-type': 'text/plain'}
    }
  )
  await jsonRequest(adminContext, 'put', '/nostrnip5/api/v1/settings', {
    headers: apiKeyHeaders(adminWallet.adminkey),
    data: {
      lnaddress_api_endpoint: baseURL,
      lnaddress_api_admin_key: adminWallet.adminkey
    }
  })

  const owner = await newUserWithUi(browser, 'nostrnip5-owner')
  await enableExtensionViaUi(owner, 'nostrnip5')
  await enableExtensionViaUi(owner, 'lnurlp')
  await textRequest(
    owner.context,
    'patch',
    '/nostrnip5/api/v1/domain/ranking/0',
    {
      data: 'reserved_a\r\nreserved_b',
      headers: {'content-type': 'text/plain'},
      expected: 403
    }
  )

  const domain = await createNip5Domain(owner.context, owner)
  const domainId = domain.id
  await jsonRequest(
    owner.context,
    'get',
    `/nostrnip5/api/v1/domain/${domainId}`,
    {
      headers: apiKeyHeaders(owner.inkey)
    }
  )

  await jsonRequest(owner.context, 'put', '/nostrnip5/api/v1/domain', {
    headers: apiKeyHeaders(owner.adminkey),
    data: {
      cost: 100,
      cost_extra: {
        char_count_cost: [
          {bracket: '1', amount: '1001'},
          {bracket: '2', amount: '505'},
          {bracket: '3', amount: '202'}
        ],
        max_years: '5',
        promotions: [
          {
            code: 'code_10',
            buyer_discount_percent: '10',
            referer_bonus_percent: '0'
          },
          {
            code: 'code_20',
            buyer_discount_percent: '20',
            referer_bonus_percent: '5'
          },
          {
            code: 'code_alan',
            buyer_discount_percent: '25',
            referer_bonus_percent: '20',
            selected_referer: 'alan'
          }
        ],
        rank_cost: [
          {bracket: 200, amount: '10000'},
          {bracket: 1000, amount: '500'}
        ]
      },
      currency: 'USD',
      domain: domain.domain,
      id: domainId,
      wallet: owner.walletId
    }
  })

  const identifierOne = `one_${Date.now()}`
  const identifierTwo = `two_${Date.now()}`
  const identifierThree = `three_${Date.now()}`
  const address = await createNip5Address(
    owner.context,
    owner,
    domainId,
    identifierOne,
    '04c915daefee38317fa734444acee390a8269fe5810b2241e5e6dd343dfbecc9'
  )
  await getNostrJson(owner.context, domainId, identifierOne, 404)
  await activateNip5Address(owner.context, owner, domainId, address.id)
  let nostrJson = await getNostrJson(owner.context, domainId, identifierOne)
  expect(nostrJson.names[identifierOne]).toBeTruthy()

  await jsonRequest(
    owner.context,
    'put',
    `/nostrnip5/api/v1/domain/${domainId}/address/${address.id}`,
    {
      headers: apiKeyHeaders(owner.adminkey),
      data: {
        pubkey:
          '04c915daefee38317fa734444acee390a8269fe5810b2241e5e6dd343dfbeeee',
        relays: ['wss://relay.nostr.com', 'ws://relay.nostr.org']
      }
    }
  )
  nostrJson = await getNostrJson(owner.context, domainId, identifierOne)
  expect(nostrJson.relays).toBeTruthy()

  const second = await createNip5Address(
    owner.context,
    owner,
    domainId,
    identifierTwo,
    '04c915daefee38317fa734444acee390a8269fe5810b2241e5e6dd343dfaaaaa'
  )
  await activateNip5Address(owner.context, owner, domainId, second.id)
  let addresses = await jsonRequest(
    owner.context,
    'get',
    '/nostrnip5/api/v1/addresses/paginated',
    {
      headers: apiKeyHeaders(owner.inkey),
      params: {
        all_wallets: true,
        limit: 10,
        offset: 0,
        sortby: 'time',
        direction: 'asc'
      }
    }
  )
  expect(JSON.stringify(addresses)).toContain(identifierTwo)

  await jsonRequest(
    owner.context,
    'delete',
    `/nostrnip5/api/v1/domain/${domainId}/address/${address.id}`,
    {
      headers: apiKeyHeaders(owner.adminkey)
    }
  )
  await getNostrJson(owner.context, domainId, identifierOne, 404)

  const alan = await createNip5Address(
    owner.context,
    owner,
    domainId,
    'alan',
    '04c915daefee38317fa734444acee390a8269fe5810b2241e5e6dd343dfaaabb'
  )
  await activateNip5Address(owner.context, owner, domainId, alan.id)
  const alanWallet = await createWallet(owner.context, 'Alan Wallet')
  await jsonRequest(
    owner.context,
    'put',
    `/nostrnip5/api/v1/user/domain/${domainId}/address/${alan.id}/lnaddress`,
    {
      headers: apiKeyHeaders(owner.adminkey),
      data: {wallet: alanWallet.walletId, min: 5, max: '100005'}
    }
  )

  for (const [query, expectedAvailable] of [
    ['a', true],
    ['aa', true],
    ['aaa', true],
    ['aaaa', true],
    [identifierTwo, false],
    ['reserved_a', false],
    ['rank_200_b', true],
    ['rank_1000_b', true],
    ['yyy', true],
    ['xxx', true]
  ]) {
    const result = await jsonRequest(
      owner.context,
      'get',
      `/nostrnip5/api/v1/domain/${domainId}/search`,
      {
        headers: apiKeyHeaders(owner.inkey),
        params: {q: query}
      }
    )
    expect(Boolean(result.available)).toBe(expectedAvailable)
  }

  const client = await newUserWithUi(browser, 'nostrnip5-client')
  await enableExtensionViaUi(client, 'nostrnip5')
  await enableExtensionViaUi(client, 'lnurlp')

  await buyNip5Address(client.context, client, domainId, 'abc1', {
    pubkey: '04c915daefee38317fa734444acee390a8269fe5810b2241e5e6dd343dfaaaaa',
    years: 3
  })
  await buyNip5Address(client.context, client, domainId, 'a1', {
    pubkey: '04c915daefee38317fa734444acee390a8269fe5810b2241e5e6dd343dfaaaaa',
    years: 3
  })
  const cartItems = await jsonRequest(
    client.context,
    'get',
    '/nostrnip5/api/v1/user/addresses',
    {
      headers: apiKeyHeaders(client.inkey),
      params: {active: false}
    }
  )
  expect(JSON.stringify(cartItems)).toContain('abc1')
  expect(JSON.stringify(cartItems)).toContain('a1')

  const priceChecks = [
    ['abc1', 3, null, false, 300.0],
    ['abc1', 5, null, true, 500.0],
    ['abc1', 7, null, false, null, 400],
    ['abc1', 3, 'code_10', true, 270.0],
    ['abc1', 3, 'code_20', false, 240.0],
    ['abc1', 3, 'code_alan', true, 225.0],
    ['xyz', 3, null, false, 606.0],
    ['xyz', 5, null, true, 1010.0],
    ['xyz', 7, null, false, null, 400],
    ['xyz', 3, 'code_10', true, 545.4],
    ['xyz', 3, 'code_20', false, 484.8],
    ['xyz', 3, 'code_alan', true, 454.5]
  ]

  for (const [
    localPart,
    years,
    promoCode,
    createInvoiceFlag,
    expectedPrice,
    expectedStatus
  ] of priceChecks) {
    const result = await buyNip5Address(
      client.context,
      client,
      domainId,
      localPart,
      {
        pubkey:
          '04c915daefee38317fa734444acee390a8269fe5810b2241e5e6dd343dfaaaaa',
        years,
        promo_code: promoCode,
        create_invoice: createInvoiceFlag,
        expected: expectedStatus || 200
      }
    )
    if (expectedPrice !== null) {
      expect(result.extra.price).toBeCloseTo(expectedPrice)
    }
    if (createInvoiceFlag && result.payment_request) {
      const decoded = await decodePayment(
        client.context,
        result.payment_request
      )
      expect(Number(result.extra.price_in_sats) * 1000).toBe(
        decoded.amount_msat
      )
    }
  }

  const paidOne = await buyNip5Address(
    client.context,
    client,
    domainId,
    identifierOne,
    {
      pubkey:
        '04c915daefee38317fa734444acee390a8269fe5810b2241e5e6dd343dfaaaab',
      years: 3,
      create_invoice: true
    }
  )
  await payInvoiceViaUi(admin, paidOne.payment_request)
  await getNostrJson(client.context, domainId, identifierOne)

  const quoteThree = await buyNip5Address(
    client.context,
    client,
    domainId,
    identifierThree,
    {
      pubkey:
        '04c915daefee38317fa734444acee390a8269fe5810b2241e5e6dd343dfaaaac',
      years: 5
    }
  )
  expect(quoteThree.extra.price).toBeCloseTo(500.0)
  const paidThree = await buyNip5Address(
    client.context,
    client,
    domainId,
    identifierThree,
    {
      pubkey:
        '04c915daefee38317fa734444acee390a8269fe5810b2241e5e6dd343dfaaaac',
      years: 5,
      promo_code: 'code_alan',
      create_invoice: true
    }
  )
  await payInvoiceViaUi(admin, paidThree.payment_request)
  await getNostrJson(client.context, domainId, identifierThree)

  const alanBalance = await getWallet(owner.context, alanWallet.inkey)
  const refererBonus = Math.floor(paidThree.extra.price_in_sats / 5)
  expect(
    Math.abs(Math.floor(alanBalance.balance / 1000) - refererBonus)
  ).toBeLessThanOrEqual(100)
})

test('011 auction house transfers NIP5 addresses through bids and fixed-price sale', async ({
  browser
}) => {
  test.setTimeout(10 * 60 * 1000)

  const admin = await getAdminSession(browser)
  await ensureExtensionsInstalledViaUi(admin, [
    'auction_house',
    'nostrnip5',
    'lnurlp'
  ])
  await enableExtensionViaUi(admin, 'nostrnip5')
  await enableExtensionViaUi(admin, 'lnurlp')
  await jsonRequest(adminContext, 'put', '/nostrnip5/api/v1/settings', {
    headers: apiKeyHeaders(adminWallet.adminkey),
    data: {
      lnaddress_api_endpoint: baseURL,
      lnaddress_api_admin_key: adminWallet.adminkey
    }
  })

  const owner = await newUserWithUi(browser, 'auction-owner')
  await enableExtensionViaUi(owner, 'auction_house')
  await enableExtensionViaUi(owner, 'nostrnip5')
  await enableExtensionViaUi(owner, 'lnurlp')
  const domain = await createNip5Domain(owner.context, owner, {
    cost_extra: {transfer_secret: '1234'}
  })
  const domainId = domain.id

  await jsonRequest(owner.context, 'put', '/nostrnip5/api/v1/settings', {
    headers: apiKeyHeaders(owner.adminkey),
    data: {
      lnaddress_api_endpoint: baseURL,
      lnaddress_api_admin_key: adminWallet.adminkey
    }
  })

  const seller = await newUserWithUi(browser, 'auction-seller')
  await enableExtensionViaUi(seller, 'auction_house')
  await enableExtensionViaUi(seller, 'nostrnip5')

  const createdAddresses = []
  for (let index = 1; index <= 10; index++) {
    const address = await createUserNip5Address(
      seller.context,
      seller,
      domainId,
      `id_${index}__${domainId}`
    )
    await activateNip5Address(seller.context, seller, domainId, address.id)
    createdAddresses.push(address)
  }

  const sellRoom = await createAuctionRoom(owner.context, owner, {
    name: 'nip5 sales',
    description: 'Auctions for Nip5',
    fee_wallet_id: owner.walletId,
    currency: 'USD',
    type: 'fixed_price'
  })
  await updateAuctionRoom(owner.context, owner, {
    id: sellRoom.id,
    name: 'nip5 sells',
    description: 'Sells for Nip5',
    currency: 'sat',
    type: 'fixed_price',
    room_percentage: 20,
    fee_wallet_id: owner.walletId,
    is_open_room: true,
    extra: auctionNip5Webhooks(domainId)
  })

  const auctionRoom = await createAuctionRoom(owner.context, owner, {
    name: 'nip5 auctions',
    description: 'Auctions for Nip5',
    fee_wallet_id: owner.walletId,
    currency: 'USD',
    type: 'auction'
  })
  await updateAuctionRoom(owner.context, owner, {
    id: auctionRoom.id,
    name: 'nip5 auctions',
    description: 'Auctions for Nip5',
    currency: 'sat',
    type: 'auction',
    min_bid_up_percentage: 5,
    room_percentage: 10,
    fee_wallet_id: owner.walletId,
    is_open_room: true,
    extra: auctionNip5Webhooks(domainId)
  })

  const sellerAddresses = await jsonRequest(
    seller.context,
    'get',
    '/nostrnip5/api/v1/user/addresses',
    {
      headers: apiKeyHeaders(seller.inkey),
      params: {active: true}
    }
  )
  expect(Array.isArray(sellerAddresses)).toBeTruthy()
  const addressForAuction = createdAddresses[0]
  const transfer = await jsonRequest(
    seller.context,
    'get',
    `/nostrnip5/api/v1/domain/${domainId}/address/${addressForAuction.id}/transfer`,
    {headers: apiKeyHeaders(seller.adminkey)}
  )
  expect(transfer.transfer_code).toBeTruthy()

  const item = await createAuctionItem(seller.context, seller, auctionRoom.id, {
    name: addressForAuction.local_part,
    ask_price: 10.1,
    transfer_code: transfer.transfer_code
  })

  let winningBidder
  for (let index = 1; index <= 15; index++) {
    const bidder = await newUser(`auction-bidder-${index}`)
    const bid = await bidOnItem(
      bidder.context,
      bidder,
      item.id,
      index * 100,
      `bid index: ${index}`
    )
    await payInvoiceViaUi(admin, bid.payment_request)
    winningBidder = bidder
  }

  const itemAfterBids = await jsonRequest(
    owner.context,
    'get',
    `/auction_house/api/v1/items/${item.id}`,
    {
      headers: apiKeyHeaders(owner.inkey)
    }
  )
  expect(itemAfterBids.bids.length).toBeGreaterThanOrEqual(15)
  await getPayments(owner.context, owner.inkey)
  await jsonRequest(
    owner.context,
    'delete',
    `/auction_house/api/v1/items/${item.id}`,
    {
      headers: apiKeyHeaders(owner.adminkey),
      params: {force_close: true}
    }
  )
  const winnerAddresses = await jsonRequest(
    winningBidder.context,
    'get',
    '/nostrnip5/api/v1/user/addresses',
    {
      headers: apiKeyHeaders(winningBidder.inkey),
      params: {active: true}
    }
  )
  expect(JSON.stringify(winnerAddresses)).toContain(
    addressForAuction.local_part
  )

  const fixedPriceAddress = createdAddresses[1]
  const fixedItems = await jsonRequest(
    seller.context,
    'get',
    `/auction_house/api/v1/items/${auctionRoom.id}/paginated`,
    {
      headers: apiKeyHeaders(seller.inkey),
      params: {
        sortby: 'ask_price',
        direction: 'asc',
        name: fixedPriceAddress.local_part
      }
    }
  )
  if (fixedItems.data?.[0]?.id) {
    await jsonRequest(
      seller.context,
      'delete',
      `/auction_house/api/v1/items/${fixedItems.data[0].id}`,
      {
        headers: apiKeyHeaders(seller.adminkey),
        params: {force_close: true}
      }
    )
  }

  const fixedTransfer = await jsonRequest(
    seller.context,
    'get',
    `/nostrnip5/api/v1/domain/${domainId}/address/${fixedPriceAddress.id}/transfer`,
    {headers: apiKeyHeaders(seller.adminkey)}
  )
  const sellItem = await createAuctionItem(
    seller.context,
    seller,
    sellRoom.id,
    {
      name: fixedPriceAddress.local_part,
      ask_price: 5000,
      transfer_code: fixedTransfer.transfer_code
    }
  )
  const buyer = await newUser('auction-buyer')
  const buy = await bidOnItem(
    buyer.context,
    buyer,
    sellItem.id,
    5000,
    'fixed price buy'
  )
  await payInvoiceViaUi(admin, buy.payment_request)
  const buyerAddresses = await jsonRequest(
    buyer.context,
    'get',
    '/nostrnip5/api/v1/user/addresses',
    {
      headers: apiKeyHeaders(buyer.inkey),
      params: {active: true}
    }
  )
  expect(JSON.stringify(buyerAddresses)).toContain(fixedPriceAddress.local_part)
})

function auctionNip5Webhooks(domainId) {
  return {
    duration: {days: 7, hours: 0, minutes: 0},
    lock_webhook: {
      method: 'PUT',
      url: `${baseURL}/nostrnip5/api/v1/domain/${domainId}/address/lock`,
      headers: '',
      data: '{\n "transfer_code": "${transfer_code}"\n}'
    },
    unlock_webhook: {
      method: 'PUT',
      url: `${baseURL}/nostrnip5/api/v1/domain/${domainId}/address/unlock`,
      headers: '',
      data: '{\n "lock_code": "${lock_code}"\n}'
    },
    transfer_webhook: {
      method: 'PUT',
      url: `${baseURL}/nostrnip5/api/v1/domain/${domainId}/address/transfer`,
      headers: '',
      data: '{\n "lock_code": "${lock_code}",\n "new_owner_id": "${new_owner_id}"\n}'
    }
  }
}
