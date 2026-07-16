const {
  test,
  expect,
  setupIntegration,
  state,
  pageStatus,
  uninstallExtension,
  getAdminSession,
  installLatestExtensionViaUi,
  enableExtensionViaUi,
  disableExtensionViaUi
} = require('./scenario-helpers')

setupIntegration()

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
  const extensionIds = [...new Set([...state.extensionById.keys()])]
    .filter(extension => !excluded.has(extension))
    .sort()

  expect(extensionIds.length).toBeGreaterThan(0)

  for (const extension of extensionIds) {
    await uninstallExtension(state.adminContext, extension)
    await pageStatus(state.adminContext, `/${extension}`, [200, 403, 404])
  }

  for (const extension of extensionIds) {
    await installLatestExtensionViaUi(admin, extension)
    await pageStatus(state.adminContext, `/${extension}`, [200, 403, 404])
    await enableExtensionViaUi(admin, extension)
    await pageStatus(
      state.adminContext,
      `/${extension}`,
      adminExtensions.has(extension) ? [200, 403] : 200
    )
    await disableExtensionViaUi(admin, extension)
    await pageStatus(state.adminContext, `/${extension}`, [200, 403, 404])
    await enableExtensionViaUi(admin, extension)
    await pageStatus(
      state.adminContext,
      `/${extension}`,
      adminExtensions.has(extension) ? [200, 403] : 200
    )
  }
})
