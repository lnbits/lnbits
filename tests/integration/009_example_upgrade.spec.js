const {
  test,
  expect,
  setupIntegration,
  state,
  jsonRequest,
  textRequest,
  getAdminSession,
  installExtensionVersionViaUi,
  enableExtensionViaUi
} = require('./scenario-helpers')

setupIntegration()

test('009 example extension can downgrade and upgrade data shape', async ({
  browser
}) => {
  test.setTimeout(10 * 60 * 1000)

  const admin = await getAdminSession(browser)
  async function installAndCheck(testVersion, extensionVersion) {
    const releases = await jsonRequest(
      state.adminContext,
      'get',
      '/api/v1/extension/example/releases'
    )
    const release = releases.find(item => item.version === extensionVersion)
    expect(release).toBeTruthy()
    await installExtensionVersionViaUi(admin, 'example', release.version)
    await enableExtensionViaUi(admin, 'example')
    const page = await textRequest(state.adminContext, 'get', '/example')
    expect(page).toContain(
      `Do not remove. Test install extension version: ${testVersion}`
    )
    const response = await jsonRequest(
      state.adminContext,
      'get',
      '/example/api/v1/test/00000000'
    )
    expect(response.version).toBe(String(testVersion))
    expect(response.test_id).toBe('00000000')
  }

  await installAndCheck(1, '1.0.1')
  await installAndCheck(2, '1.0.6')
  await installAndCheck(1, '1.0.1')
  await installAndCheck(2, '1.0.6')
  await installAndCheck(1, '1.0.1')
})
