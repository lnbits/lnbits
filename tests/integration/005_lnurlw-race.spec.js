const {
  test,
  expect,
  setupIntegration,
  createWallet,
  getPayments,
  jsonRequest,
  newUserWithUi,
  getAdminSession,
  payLnurlViaUi,
  ensureExtensionsInstalledViaUi,
  enableExtensionViaUi,
  createPayLink,
  createWithdrawLink,
  withdrawLnurl
} = require('./scenario-helpers')

setupIntegration()

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

  const payments = await getPayments(user.context, receiveWallet.inkey, {
    limit: 100
  })
  expect(payments).toHaveLength(100)
  const successCount = payments.filter(
    payment => payment.status === 'success'
  ).length
  expect(successCount).toBeGreaterThan(0)
  expect(successCount).toBeLessThanOrEqual(2)
})
