const {
  test,
  expect,
  setupIntegration,
  state,
  apiKeyHeaders,
  createWallet,
  getWallet,
  jsonRequest,
  pageStatus,
  pollWalletBalance,
  newUserWithUi,
  getAdminSession,
  payInvoiceViaUi,
  ensureExtensionsInstalledViaUi,
  enableExtensionViaUi,
  withdrawLnurl
} = require('./scenario-helpers')

setupIntegration()

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

  const beforeAdmin = await getWallet(
    state.adminContext,
    state.adminWallet.inkey
  )
  const beforeUser = await getWallet(user.context, user.inkey)
  const atmPin = await jsonRequest(
    user.context,
    'get',
    `/tpos/api/v1/atm/${atm.id}/2222`,
    {
      headers: apiKeyHeaders(state.adminWallet.adminkey)
    }
  )
  expect(atmPin.id).toBeTruthy()
  const withdraw = await jsonRequest(
    user.context,
    'get',
    `/tpos/api/v1/atm/withdraw/${atmPin.id}/100`,
    {
      headers: apiKeyHeaders(state.adminWallet.adminkey)
    }
  )
  const withdrawResponse = await jsonRequest(
    user.context,
    'get',
    `/tpos/api/v1/lnurl/${withdraw.id}/100`,
    {headers: apiKeyHeaders(state.adminWallet.adminkey)}
  )
  const payment = await withdrawLnurl(
    user.context,
    state.adminWallet,
    withdrawResponse,
    100,
    'TPoS withdraw'
  )
  expect(payment.payment_hash).toBeTruthy()
  await pollWalletBalance(
    state.adminContext,
    state.adminWallet.inkey,
    beforeAdmin.balance + 100_000
  )
  await pollWalletBalance(
    user.context,
    user.inkey,
    beforeUser.balance - 100_000
  )
})
