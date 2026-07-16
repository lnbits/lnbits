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

const state = {
  baseURL: null,
  adminContext: null,
  adminWallet: null,
  adminSession: null,
  extensionById: null,
  contextFactory: null
}

const contexts = []
const browserContexts = []

async function newContext() {
  const context = await state.contextFactory.newContext({
    baseURL: state.baseURL,
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
  const uiContext = await browser.newContext({baseURL: state.baseURL})
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
  if (!state.adminSession) {
    state.adminSession = {
      ...state.adminWallet,
      ...(await newBrowserSession(browser))
    }
  }
  return state.adminSession
}

function extensionName(extensionId) {
  return state.extensionById?.get(extensionId)?.name || extensionId
}

function escapeRegExp(value) {
  return String(value).replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

function extensionSearchTerms(extensionId) {
  return [...new Set([extensionName(extensionId), extensionId].filter(Boolean))]
}

async function refreshExtensionCatalog(context = state.adminContext) {
  const extensions = await jsonRequest(context, 'get', '/api/v1/extension')
  for (const extension of extensions) {
    const id = extension.id || extension.code
    if (id) {
      state.extensionById.set(id, {
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

async function clickAndMaybeGetJsonResponse(
  page,
  method,
  path,
  action,
  expected = 200,
  timeout = 10_000
) {
  const responsePromise = page
    .waitForResponse(response => responseMatches(response, method, path), {
      timeout
    })
    .catch(() => null)
  await action()
  const response = await responsePromise
  if (!response) return null
  await expectStatus(response, expected, `${method} ${path}`)
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
  const search = session.page.getByLabel(/search extensions/i)
  const cards = session.page.locator('.q-card').filter({
    visible: true,
    has: session.page.getByRole('button', {
      name: /manage|enable|disable|open|pay to enable/i
    })
  })
  for (const term of extensionSearchTerms(extensionId)) {
    await search.fill(term)
    const matchingCard = cards
      .filter({hasText: new RegExp(escapeRegExp(term), 'i')})
      .first()
    if (await matchingCard.isVisible({timeout: 1500}).catch(() => false)) {
      return matchingCard
    }

    if ((await cards.count()) === 1) {
      return cards.first()
    }
  }
  throw new Error(`Could not find extension card for ${extensionId}`)
}

async function openExtensionManager(session, extensionId, tab = 'installed') {
  const card = await findExtensionCard(session, extensionId, tab)
  const releasesResponsePromise = session.page
    .waitForResponse(
      response =>
        responseMatches(
          response,
          'GET',
          `/api/v1/extension/${extensionId}/releases`
        ),
      {timeout: 10_000}
    )
    .catch(() => null)
  await card.getByRole('button', {name: /manage/i}).click()
  const releasesResponse = await releasesResponsePromise
  if (releasesResponse) {
    await expectStatus(
      releasesResponse,
      200,
      `GET /api/v1/extension/${extensionId}/releases`
    )
  }
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
  const versionLabels = [
    ...new Set([version, version.replace(/^v/i, '')].filter(Boolean))
  ]
  let releaseVersion = null
  for (const label of versionLabels) {
    const candidate = dialog
      .getByText(label, {exact: true})
      .filter({visible: true})
      .first()
    if (await candidate.isVisible({timeout: 1000}).catch(() => false)) {
      releaseVersion = candidate
      break
    }
  }
  if (!releaseVersion) {
    const expandButton = dialog.getByRole('button', {name: /expand/i}).first()
    if (!(await expandButton.isVisible({timeout: 1000}).catch(() => false))) {
      const alreadyInstalled = await dialog
        .getByRole('button', {name: /uninstall/i})
        .isVisible({timeout: 500})
        .catch(() => false)
      await dialog.getByRole('button', {name: /close/i}).last().click()
      return alreadyInstalled ? {alreadyInstalled: true} : null
    }
    await expandButton.click()
    for (const label of versionLabels) {
      const candidate = dialog
        .getByText(label, {exact: true})
        .filter({visible: true})
        .first()
      if (await candidate.isVisible({timeout: 1000}).catch(() => false)) {
        releaseVersion = candidate
        break
      }
    }
  }
  if (!releaseVersion) {
    releaseVersion = dialog
      .getByText(versionLabels[0], {exact: true})
      .filter({visible: true})
      .first()
  }
  await expect(releaseVersion).toBeVisible()
  await releaseVersion.click()
  const installButton = dialog.getByRole('button', {name: /^install$/i}).first()
  if (!(await installButton.isVisible({timeout: 1000}).catch(() => false))) {
    const alreadyInstalled = await dialog
      .getByRole('button', {name: /uninstall/i})
      .isVisible({timeout: 500})
      .catch(() => false)
    await dialog.getByRole('button', {name: /close/i}).last().click()
    return alreadyInstalled ? {alreadyInstalled: true} : null
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
  const enableButton = card.getByRole('button', {name: /^enable$/i})
  const result = await clickAndMaybeGetJsonResponse(
    session.page,
    'PUT',
    `/api/v1/extension/${extensionId}/enable`,
    () => enableButton.click()
  )
  if (result) return result

  const cardAfterEnable = await findExtensionCard(session, extensionId)
  await expect(
    cardAfterEnable.getByRole('button', {name: /^disable$/i})
  ).toBeVisible()
  return {success: true}
}

async function disableExtensionViaUi(session, extensionId) {
  const card = await findExtensionCard(session, extensionId)
  if (!(await card.getByRole('button', {name: /^disable$/i}).isVisible())) {
    return null
  }
  const disableButton = card.getByRole('button', {name: /^disable$/i})
  const result = await clickAndMaybeGetJsonResponse(
    session.page,
    'PUT',
    `/api/v1/extension/${extensionId}/disable`,
    () => disableButton.click()
  )
  if (result) return result

  const cardAfterDisable = await findExtensionCard(session, extensionId)
  await expect(
    cardAfterDisable.getByRole('button', {name: /^enable$/i})
  ).toBeVisible()
  return {success: true}
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
  const result = await clickAndMaybeGetJsonResponse(
    session.page,
    'PUT',
    `/api/v1/extension/${extensionId}/${action}`,
    () => toggle.click(),
    expected
  )
  if (result) return result

  const cardAfterToggle = await findExtensionCard(session, extensionId)
  await expect(cardAfterToggle.locator('.q-toggle').first()).toContainText(
    active ? 'Activated' : 'Deactivated'
  )
  return {success: true}
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
  const url = `/nostrnip5/api/v1/domain/${domainId}/nostr.json`
  const response = await context.get(url, {
    params: {name},
    failOnStatusCode: false
  })
  await expectStatus(
    response,
    expected === 404 ? [404, 200] : expected,
    `GET ${url}`
  )

  if (response.status() === 404) return null

  const data = await responseJson(response)
  if (expected === 404) {
    expect(data.names ?? {}).toEqual({})
    expect(data.relays ?? {}).toEqual({})
  }
  return data
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
      expected: options.expected ?? 201
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

function setupIntegration() {
  test.beforeAll(async ({playwright}, testInfo) => {
    state.baseURL = testInfo.project.use.baseURL
    state.contextFactory = playwright.request
    state.adminSession = null
    state.adminContext = await newContext()
    state.adminWallet = await initServer(state.adminContext)
    const manifest = await fetchManifest()
    state.extensionById = new Map(
      manifest.extensions.map(extension => [extension.id, extension])
    )
  })

  test.afterAll(async () => {
    await Promise.all(contexts.map(context => context.dispose()))
    await Promise.all(browserContexts.map(context => context.close()))
    contexts.splice(0, contexts.length)
    browserContexts.splice(0, browserContexts.length)
    state.baseURL = null
    state.adminContext = null
    state.adminWallet = null
    state.adminSession = null
    state.extensionById = null
    state.contextFactory = null
  })
}

function compactObject(value) {
  return Object.fromEntries(
    Object.entries(value).filter(([, entry]) => entry !== undefined)
  )
}

function auctionNip5Webhooks(domainId) {
  return {
    duration: {days: 7, hours: 0, minutes: 0},
    lock_webhook: {
      method: 'PUT',
      url: `${state.baseURL}/nostrnip5/api/v1/domain/${domainId}/address/lock`,
      headers: '',
      data: '{\n "transfer_code": "${transfer_code}"\n}'
    },
    unlock_webhook: {
      method: 'PUT',
      url: `${state.baseURL}/nostrnip5/api/v1/domain/${domainId}/address/unlock`,
      headers: '',
      data: '{\n "lock_code": "${lock_code}"\n}'
    },
    transfer_webhook: {
      method: 'PUT',
      url: `${state.baseURL}/nostrnip5/api/v1/domain/${domainId}/address/transfer`,
      headers: '',
      data: '{\n "lock_code": "${lock_code}",\n "new_owner_id": "${new_owner_id}"\n}'
    }
  }
}

module.exports = {
  test,
  expect,
  setupIntegration,
  state,
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
  uninstallExtension,
  newContext,
  newUser,
  newBrowserSession,
  newUserWithUi,
  getAdminSession,
  extensionName,
  refreshExtensionCatalog,
  responsePath,
  responseMatches,
  clickAndCheckResponse,
  clickAndGetJsonResponse,
  gotoPage,
  gotoWallet,
  fillQuasarField,
  createInvoiceViaUi,
  payInvoiceViaUi,
  payLnurlViaUi,
  withdrawLnurlViaUi,
  openExtensionsPage,
  findExtensionCard,
  openExtensionManager,
  installExtensionVersionViaUi,
  installLatestExtensionViaUi,
  ensureExtensionsInstalledViaUi,
  enableExtensionViaUi,
  disableExtensionViaUi,
  setExtensionActiveViaUi,
  payToEnableExtensionViaUi,
  createPayLink,
  createWithdrawLink,
  withdrawLnurl,
  lndhubHeaders,
  createNip5Domain,
  createUserNip5Address,
  createNip5Address,
  activateNip5Address,
  getNostrJson,
  buyNip5Address,
  createAuctionRoom,
  updateAuctionRoom,
  createAuctionItem,
  bidOnItem,
  compactObject,
  auctionNip5Webhooks
}
