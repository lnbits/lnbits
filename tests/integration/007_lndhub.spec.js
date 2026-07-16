const {
  test,
  expect,
  setupIntegration,
  jsonRequest,
  pageStatus,
  newUserWithUi,
  getAdminSession,
  createInvoiceViaUi,
  payInvoiceViaUi,
  ensureExtensionsInstalledViaUi,
  enableExtensionViaUi,
  lndhubHeaders
} = require('./scenario-helpers')

setupIntegration()

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
