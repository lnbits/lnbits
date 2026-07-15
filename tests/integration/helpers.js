const {expect} = require('@playwright/test')

const DEFAULT_MANIFEST_URL =
  'https://raw.githubusercontent.com/lnbits/lnbits-extensions/main/extensions.json'

function apiKeyHeaders(key) {
  return key ? {'X-Api-Key': key} : {}
}

async function expectStatus(response, expected, label) {
  const statuses = Array.isArray(expected) ? expected : [expected]
  if (!statuses.includes(response.status())) {
    const body = await response.text()
    throw new Error(
      `${label || response.url()} expected status ${statuses.join(
        '/'
      )}, got ${response.status()}: ${body.slice(0, 800)}`
    )
  }
}

async function responseJson(response) {
  const text = await response.text()
  if (!text) return null
  try {
    return JSON.parse(text)
  } catch (error) {
    throw new Error(
      `Expected JSON from ${response.url()}: ${text.slice(0, 800)}`
    )
  }
}

async function jsonRequest(context, method, url, options = {}) {
  const response = await context[method](url, {
    data: options.data,
    form: options.form,
    headers: options.headers,
    params: options.params,
    failOnStatusCode: false,
    maxRedirects: options.maxRedirects
  })
  await expectStatus(
    response,
    options.expected ?? 200,
    `${method.toUpperCase()} ${url}`
  )
  return responseJson(response)
}

async function textRequest(context, method, url, options = {}) {
  const response = await context[method](url, {
    data: options.data,
    headers: options.headers,
    params: options.params,
    failOnStatusCode: false,
    maxRedirects: options.maxRedirects
  })
  await expectStatus(
    response,
    options.expected ?? 200,
    `${method.toUpperCase()} ${url}`
  )
  return response.text()
}

async function loginAdmin(context) {
  await jsonRequest(context, 'post', '/api/v1/auth', {
    data: {username: 'admin', password: 'secret1234'}
  })
}

async function initServer(context) {
  const home = await context.get('/', {
    failOnStatusCode: false,
    maxRedirects: 0
  })
  const location = home.headers().location || ''
  if (
    [301, 302, 303, 307, 308].includes(home.status()) &&
    location.includes('first_install')
  ) {
    await jsonRequest(context, 'put', '/api/v1/auth/first_install', {
      data: {
        username: 'admin',
        password: 'secret1234',
        password_repeat: 'secret1234'
      }
    })
  }

  await loginAdmin(context)

  const wallets = await jsonRequest(context, 'get', '/api/v1/wallets')
  expect(wallets.length).toBeGreaterThan(0)
  const adminWallet = wallets[0]

  await jsonRequest(context, 'put', '/admin/api/v1/settings', {
    data: {lnbits_callback_url_rules: []}
  })
  await topUpWallet(context, adminWallet.id, 1_000_000)

  return {
    walletId: adminWallet.id,
    inkey: adminWallet.inkey,
    adminkey: adminWallet.adminkey
  }
}

async function logout(context) {
  await jsonRequest(context, 'post', '/api/v1/auth/logout')
}

async function createAccount(context, name) {
  await textRequest(context, 'get', '/')
  const wallet = await jsonRequest(context, 'post', '/api/v1/account', {
    data: {name}
  })
  await jsonRequest(context, 'post', '/api/v1/auth/usr', {
    data: {usr: wallet.user}
  })
  return {
    userId: wallet.user,
    walletId: wallet.id,
    inkey: wallet.inkey,
    adminkey: wallet.adminkey,
    raw: wallet
  }
}

async function createWallet(context, name) {
  const wallet = await jsonRequest(context, 'post', '/api/v1/wallet', {
    data: {name}
  })
  return {
    userId: wallet.user,
    walletId: wallet.id,
    inkey: wallet.inkey,
    adminkey: wallet.adminkey,
    raw: wallet
  }
}

async function topUpWallet(adminContext, walletId, amount) {
  return jsonRequest(adminContext, 'put', '/users/api/v1/balance', {
    data: {amount: String(amount), id: walletId}
  })
}

async function enableExtension(context, extension) {
  const enabled = await jsonRequest(
    context,
    'put',
    `/api/v1/extension/${extension}/enable`,
    {
      form: {enable: extension}
    }
  )
  if (enabled && Object.prototype.hasOwnProperty.call(enabled, 'is_enabled')) {
    expect(enabled.is_enabled).toBeTruthy()
  }
  return enabled
}

async function disableExtension(context, extension) {
  return jsonRequest(context, 'put', `/api/v1/extension/${extension}/disable`, {
    form: {enable: extension}
  })
}

async function deactivateExtension(context, extension) {
  return jsonRequest(
    context,
    'put',
    `/api/v1/extension/${extension}/deactivate`
  )
}

async function activateExtension(context, extension, expected = 200) {
  return jsonRequest(
    context,
    'put',
    `/api/v1/extension/${extension}/activate`,
    {
      expected
    }
  )
}

async function uninstallExtension(context, extension) {
  const response = await context.delete(`/api/v1/extension/${extension}`, {
    failOnStatusCode: false
  })
  await expectStatus(
    response,
    [200, 204, 404],
    `DELETE /api/v1/extension/${extension}`
  )
}

async function pageStatus(context, path, expected = 200) {
  const response = await context.get(path, {failOnStatusCode: false})
  await expectStatus(response, expected, `GET ${path}`)
  return response
}

async function getWallet(context, inkey) {
  return jsonRequest(context, 'get', '/api/v1/wallet', {
    headers: apiKeyHeaders(inkey)
  })
}

async function getPayments(context, inkey, params) {
  return jsonRequest(context, 'get', '/api/v1/payments', {
    headers: apiKeyHeaders(inkey),
    params
  })
}

async function createInvoice(context, adminkey, amount, memo) {
  return jsonRequest(context, 'post', '/api/v1/payments', {
    headers: apiKeyHeaders(adminkey),
    data: {out: false, amount, memo}
  })
}

async function payInvoice(context, adminkey, bolt11, expected = 201) {
  return jsonRequest(context, 'post', '/api/v1/payments', {
    headers: apiKeyHeaders(adminkey),
    data: {out: true, bolt11},
    expected
  })
}

async function getPayment(context, inkey, paymentHash) {
  return jsonRequest(context, 'get', `/api/v1/payments/${paymentHash}`, {
    headers: apiKeyHeaders(inkey)
  })
}

async function decodePayment(context, data) {
  return jsonRequest(context, 'post', '/api/v1/payments/decode', {
    data: {data}
  })
}

async function lnurlScan(context, lnurl) {
  return jsonRequest(
    context,
    'get',
    `/api/v1/lnurlscan/${encodeURIComponent(lnurl)}`
  )
}

async function clearMirror() {
  const response = await fetch(mirrorUrl('/__mirror__/clear'))
  if (response.status !== 204) {
    throw new Error(`Expected mirror clear status 204, got ${response.status}`)
  }
}

async function getMirrorRequests() {
  const response = await fetch(mirrorUrl('/__mirror__/requests'))
  if (!response.ok) {
    throw new Error(`Cannot fetch mirror requests: ${response.status}`)
  }
  return response.json()
}

async function pollPayment(
  context,
  inkey,
  paymentHash,
  predicate,
  timeout = 10_000
) {
  let last
  await expect
    .poll(
      async () => {
        last = await getPayment(context, inkey, paymentHash)
        return predicate(last)
      },
      {timeout}
    )
    .toBeTruthy()
  return last
}

async function pollWalletBalance(
  context,
  inkey,
  expectedBalance,
  timeout = 10_000
) {
  await expect
    .poll(
      async () => {
        const wallet = await getWallet(context, inkey)
        return wallet.balance
      },
      {timeout}
    )
    .toBe(expectedBalance)
}

async function fetchManifest() {
  const manifestUrl =
    process.env.EXTENSIONS_MANIFEST_URL || DEFAULT_MANIFEST_URL
  const response = await fetch(manifestUrl)
  if (!response.ok) {
    throw new Error(
      `Cannot fetch extension manifest ${manifestUrl}: ${response.status}`
    )
  }
  return response.json()
}

async function latestRelease(context, extension) {
  const releases = await jsonRequest(
    context,
    'get',
    `/api/v1/extension/${extension}/releases`
  )
  expect(releases.length).toBeGreaterThan(0)
  return releases
    .slice()
    .sort((a, b) =>
      a.version.localeCompare(b.version, undefined, {numeric: true})
    )
    .at(-1)
}

async function installLatestExtension(context, extension) {
  const release = await latestRelease(context, extension)
  return jsonRequest(context, 'post', '/api/v1/extension', {
    data: {
      ext_id: extension,
      archive: release.archive,
      source_repo: release.source_repo,
      version: release.version
    }
  })
}

function mirrorUrl(path = '') {
  const port = process.env.MIRROR_PORT || '8500'
  return `http://localhost:${port}${path}`
}

module.exports = {
  apiKeyHeaders,
  activateExtension,
  clearMirror,
  createAccount,
  createInvoice,
  createWallet,
  deactivateExtension,
  decodePayment,
  disableExtension,
  enableExtension,
  expectStatus,
  fetchManifest,
  getMirrorRequests,
  getPayment,
  getPayments,
  getWallet,
  initServer,
  installLatestExtension,
  jsonRequest,
  latestRelease,
  lnurlScan,
  loginAdmin,
  logout,
  mirrorUrl,
  pageStatus,
  payInvoice,
  pollPayment,
  pollWalletBalance,
  responseJson,
  textRequest,
  topUpWallet,
  uninstallExtension
}
