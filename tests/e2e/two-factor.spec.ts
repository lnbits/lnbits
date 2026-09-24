import {createHmac} from 'node:crypto'
import {test, expect} from './fixtures'
import {login} from './extension-helpers'

test.use({serviceWorkers: 'block'})

function authenticatorCode(base32: string): string {
  const alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567'
  const bits = [...base32.replace(/=+$/, '')]
    .map(char => alphabet.indexOf(char).toString(2).padStart(5, '0'))
    .join('')
  const key = Buffer.from(bits.match(/.{8}/g)!.map(byte => parseInt(byte, 2)))
  const counter = Buffer.alloc(8)
  counter.writeBigUInt64BE(BigInt(Math.floor(Date.now() / 30000)))
  const hash = createHmac('sha1', key).update(counter).digest()
  const offset = hash[hash.length - 1] & 15
  return ((hash.readUInt32BE(offset) & 0x7fffffff) % 1000000)
    .toString()
    .padStart(6, '0')
}

test('TOTP enrollment, recovery login, account dialogs, and global disable', async ({
  page,
  lnbitsServer
}) => {
  await login(page, lnbitsServer)
  await page.goto('/admin#two_factor')
  await page
    .getByLabel('Enable two factor authentication', {exact: true})
    .check()
  await page.getByRole('button', {name: 'Save', exact: true}).click()
  await expect(page.getByText(/Success! Settings changed!/)).toBeVisible()

  await page.goto('/account#two_factor')
  const setupResponse = page.waitForResponse(response =>
    response.url().endsWith('/auth/2fa/setup')
  )
  await page
    .getByRole('button', {name: 'Set up authenticator', exact: true})
    .click()
  const setup = await (await setupResponse).json()
  await expect(
    page.locator('code').filter({hasText: setup.secret})
  ).toBeVisible()
  await page
    .getByLabel('Authenticator code', {exact: true})
    .fill(authenticatorCode(setup.secret))
  await page.getByRole('button', {name: 'Enable 2FA', exact: true}).click()
  const codes = (await page.locator('pre').innerText()).trim().split('\n')
  expect(codes).toHaveLength(10)
  await page.getByLabel('I have saved my recovery codes').check()
  await page.getByRole('button', {name: 'Done', exact: true}).click()
  await expect(page.getByText(/Authenticator enrolled/)).toBeVisible()

  await page.request.post('/api/v1/auth/logout')
  await page.goto('/')
  await page.locator('input[name="username"]').fill(lnbitsServer.username)
  await page.locator('input[name="password"]').fill(lnbitsServer.password)
  await page.getByRole('button', {name: /^login$/i}).click()
  await expect(page).toHaveURL(/\/two-factor$/)
  expect((await page.request.get('/api/v1/auth')).status()).toBe(401)
  await page
    .getByLabel('Authenticator or recovery code', {exact: true})
    .fill(codes[0])
  await page.getByRole('button', {name: 'Verify', exact: true}).click()
  await expect(page).toHaveURL(/\/wallet/)

  await page.goto('/account#two_factor')
  await expect(page.getByText(/Authenticator enrolled/)).toBeVisible()
  await expect(
    page.getByLabel('Authenticator or recovery code', {exact: true})
  ).toHaveCount(0)
  await expect(
    page.getByRole('button', {name: 'Verify', exact: true})
  ).toHaveCount(0)

  const dialog = page.getByRole('dialog')
  const replace = page.getByRole('button', {
    name: 'Replace recovery codes',
    exact: true
  })
  await replace.click()
  await expect(dialog).toBeVisible()
  await expect(dialog.getByRole('textbox')).toHaveCount(0)
  await dialog.getByRole('button', {name: 'Cancel', exact: true}).click()
  await expect(dialog).toBeHidden()
  expect(
    (await (await page.request.get('/api/v1/auth/2fa/status')).json())
      .recovery_remaining
  ).toBe(9)

  await replace.click()
  await dialog
    .getByRole('button', {name: 'Replace recovery codes', exact: true})
    .click()
  await expect(dialog).toBeHidden()
  const replacementCodes = (await page.locator('pre').innerText())
    .trim()
    .split('\n')
  expect(replacementCodes).toHaveLength(10)
  expect(replacementCodes).not.toEqual(codes)
  await page.getByLabel('I have saved my recovery codes').check()
  await page.getByRole('button', {name: 'Done', exact: true}).click()

  // Expiry after opening the dialog must request a code and retain the action.
  await page.getByRole('button', {name: 'Disable my 2FA', exact: true}).click()
  await expect(dialog.getByRole('textbox')).toHaveCount(0)
  await page.route(
    '**/api/v1/auth/2fa',
    route =>
      route.fulfill({
        status: 401,
        headers: {'two-factor-required': 'true'},
        json: {detail: 'Fresh two factor verification required.'}
      }),
    {times: 1}
  )
  await dialog
    .getByRole('button', {name: 'Disable my 2FA', exact: true})
    .click()
  const codeInput = dialog.getByLabel('Authenticator or recovery code', {
    exact: true
  })
  await expect(codeInput).toBeVisible()
  await codeInput.fill('invalid-code')
  await dialog
    .getByRole('button', {name: 'Disable my 2FA', exact: true})
    .click()
  await expect(dialog.getByRole('alert')).toBeVisible()
  expect(
    (await (await page.request.get('/api/v1/auth/2fa/status')).json()).enrolled
  ).toBe(true)
  await dialog.getByRole('button', {name: 'Cancel', exact: true}).click()
  await expect(dialog).toBeHidden()
  await expect(page.getByRole('alert')).toHaveCount(0)

  // A stale session detected before opening should prompt immediately.
  await page.route('**/api/v1/auth/2fa/status', async route => {
    const response = await route.fetch()
    await route.fulfill({
      response,
      json: {...(await response.json()), verification_required: true}
    })
  })
  await page.getByRole('button', {name: 'Disable my 2FA', exact: true}).click()
  await expect(dialog.getByRole('alert')).toHaveCount(0)
  await codeInput.fill(replacementCodes[0])
  await dialog
    .getByRole('button', {name: 'Disable my 2FA', exact: true})
    .click()
  await expect(dialog).toBeHidden()
  await expect(
    page.getByRole('button', {name: 'Set up authenticator', exact: true})
  ).toBeVisible()
  await expect(page).toHaveURL(/\/account#two_factor$/)
  await page.unroute('**/api/v1/auth/2fa/status')

  // Keep an enrolled account when checking the global-off behavior below.
  const reenrollmentSetup = await page.request.post('/api/v1/auth/2fa/setup')
  expect(reenrollmentSetup.ok()).toBe(true)
  const reenrollment = await page.request.post('/api/v1/auth/2fa/confirm', {
    data: {code: authenticatorCode((await reenrollmentSetup.json()).secret)}
  })
  expect(reenrollment.ok()).toBe(true)
  expect(
    (await page.request.post('/api/v1/auth/2fa/recovery/acknowledge')).ok()
  ).toBe(true)

  await page.goto('/admin#two_factor')
  await page
    .getByLabel('Enable two factor authentication', {exact: true})
    .uncheck()
  await page.getByRole('button', {name: 'Save', exact: true}).click()
  await expect(page.getByText(/Success! Settings changed!/)).toBeVisible()
  await page.request.post('/api/v1/auth/logout')
  await login(page, lnbitsServer)
  await page.goto('/account#two_factor')
  await expect(
    page.getByText(/2FA is disabled for this instance/)
  ).toBeVisible()
})
