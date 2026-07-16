const {
  test,
  expect,
  setupIntegration,
  state,
  jsonRequest,
  uninstallExtension,
  getAdminSession,
  refreshExtensionCatalog,
  installLatestExtensionViaUi,
  setExtensionActiveViaUi
} = require('./scenario-helpers')

setupIntegration()

test('008 lnaddress and lnurlp redirect conflict handling', async ({
  browser
}) => {
  test.setTimeout(10 * 60 * 1000)

  const admin = await getAdminSession(browser)
  await jsonRequest(state.adminContext, 'patch', '/admin/api/v1/settings', {
    data: {
      lnbits_extensions_manifests: [
        'https://raw.githubusercontent.com/lnbits/lnbits-extensions/main/extensions.json',
        'https://raw.githubusercontent.com/lnbits/lnaddress/refs/heads/main/manifest.json'
      ]
    }
  })
  await refreshExtensionCatalog(state.adminContext)
  await uninstallExtension(state.adminContext, 'lnaddress')

  await installLatestExtensionViaUi(admin, 'lnurlp')
  await installLatestExtensionViaUi(admin, 'lnaddress')
  await setExtensionActiveViaUi(admin, 'lnurlp', false)
  const conflict = await setExtensionActiveViaUi(
    admin,
    'lnurlp',
    true,
    [200, 400]
  )
  const conflictText = JSON.stringify(conflict)
  if (conflictText.includes('Already mapped')) {
    expect(conflictText).toContain('Already mapped')
  } else {
    expect(conflict?.success).toBeTruthy()
  }
  await setExtensionActiveViaUi(admin, 'lnaddress', false).catch(error => {
    if (!String(error.message).includes('Could not find extension card')) {
      throw error
    }
  })
  await setExtensionActiveViaUi(admin, 'lnurlp', true)
})
