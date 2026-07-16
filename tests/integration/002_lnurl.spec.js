const {
  test,
  expect,
  setupIntegration,
  apiKeyHeaders,
  clearMirror,
  createWallet,
  getPayment,
  jsonRequest,
  lnurlScan,
  pageStatus,
  pollPayment,
  pollWalletBalance,
  newUserWithUi,
  getAdminSession,
  payLnurlViaUi,
  withdrawLnurlViaUi,
  ensureExtensionsInstalledViaUi,
  enableExtensionViaUi,
  createPayLink,
  createWithdrawLink
} = require('./scenario-helpers')

setupIntegration()

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
    await user.page.waitForTimeout(2100)

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
      if (withdrawIndex === 0) {
        await user.page.waitForTimeout(1100)
      }
    }
  }

  await pollWalletBalance(user.context, receiveWallet.inkey, 60_000)
})
