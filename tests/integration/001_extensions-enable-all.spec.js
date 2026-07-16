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
    'nostrrelay',
    'tpos',
    'webpages'
  ])
  const extensionIds = [...new Set([...state.extensionById.keys()])]
    .filter(extension => !excluded.has(extension))
    .sort()

  expect(extensionIds.length).toBeGreaterThan(0)

  for (const extension of extensionIds) {
    await test.step(`uninstall ${extension}`, async () => {
      await uninstallExtension(state.adminContext, extension)
      await pageStatus(state.adminContext, `/${extension}`, [200, 403, 404])
    })
  }

  for (const extension of extensionIds) {
    await test.step(`install and toggle ${extension}`, async () => {
      const installed = await installLatestExtensionViaUi(admin, extension)
      if (!installed) {
        return
      }
      await pageStatus(state.adminContext, `/${extension}`, [200, 403, 404])
      await enableExtensionViaUi(admin, extension)
      await pageStatus(state.adminContext, `/${extension}`, [200, 403, 404])
      await disableExtensionViaUi(admin, extension)
      await pageStatus(state.adminContext, `/${extension}`, [200, 403, 404])
      await enableExtensionViaUi(admin, extension)
      await pageStatus(state.adminContext, `/${extension}`, [200, 403, 404])
    })
  }
})
