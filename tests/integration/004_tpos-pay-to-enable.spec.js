const {
  test,
  expect,
  setupIntegration,
  state,
  jsonRequest,
  latestRelease,
  pageStatus,
  topUpWallet,
  newUserWithUi,
  getAdminSession,
  ensureExtensionsInstalledViaUi,
  enableExtensionViaUi,
  disableExtensionViaUi,
  payToEnableExtensionViaUi
} = require('./scenario-helpers')

setupIntegration()

test('004 tpos pay-to-enable flow', async ({browser}) => {
  test.setTimeout(5 * 60 * 1000)

  const admin = await getAdminSession(browser)
  await ensureExtensionsInstalledViaUi(admin, ['tpos'])
  const user = await newUserWithUi(browser, 'pay-to-enable')
  await topUpWallet(state.adminContext, user.walletId, 1000)

  const release = await latestRelease(state.adminContext, 'tpos')
  expect(release.version).toBeTruthy()
  await enableExtensionViaUi(admin, 'tpos')
  await jsonRequest(state.adminContext, 'put', '/api/v1/extension/tpos/sell', {
    data: {required: true, amount: 21, wallet: state.adminWallet.walletId}
  })

  await pageStatus(state.adminContext, '/tpos')

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

  await jsonRequest(state.adminContext, 'put', '/api/v1/extension/tpos/sell', {
    data: {required: false, amount: 0, wallet: state.adminWallet.walletId}
  })
})
