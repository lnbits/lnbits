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
  const conflict = await setExtensionActiveViaUi(admin, 'lnurlp', true, 400)
  expect(JSON.stringify(conflict)).toContain('Already mapped')
  await setExtensionActiveViaUi(admin, 'lnaddress', false)
  await setExtensionActiveViaUi(admin, 'lnurlp', true)
})
