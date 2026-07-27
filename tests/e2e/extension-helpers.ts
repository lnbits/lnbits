import {expect, type Frame, type Locator, type Page} from '@playwright/test'

import {
  browserJson,
  delay,
  isRecord,
  type LNbitsE2EServer,
  waitForResult
} from './fixtures'

const INSTALLABLE_EXTENSION_REFRESH_TASK =
  'refresh_installable_extensions_cache'

export type ExtensionUnderTest = {
  configUrl?: string
  extId: string
  name: string
  permissionTexts?: string[]
}

export type E2EWallet = {
  adminkey: string
  id: string
  inkey: string
  name: string
}

export async function login(
  page: Page,
  server: LNbitsE2EServer
): Promise<void> {
  await page.goto('/')
  await page.locator('input[name="username"]').fill(server.username)
  await page.locator('input[name="password"]').fill(server.password)
  await page.getByRole('button', {name: /^login$/i}).click()
  await expect(page).toHaveURL(/\/wallet\/[^/]+$/)
  await dismissDisclaimer(page)
}

export async function dismissDisclaimer(page: Page): Promise<void> {
  try {
    await page
      .getByRole('button', {name: 'I understand'})
      .click({timeout: 5_000})
  } catch (_error) {}
}

export async function superuserWallet(page: Page): Promise<E2EWallet> {
  const wallet = await page.evaluate(() => {
    const global = window as typeof window & {
      g: {
        user: {
          wallets: Array<{
            adminkey: string
            id: string
            inkey: string
            name: string
          }>
        }
      }
    }
    return {
      adminkey: global.g.user.wallets[0].adminkey,
      id: global.g.user.wallets[0].id,
      inkey: global.g.user.wallets[0].inkey,
      name: global.g.user.wallets[0].name
    }
  })
  return walletFromResponse(wallet)
}

export async function createWallet(
  page: Page,
  name: string
): Promise<E2EWallet> {
  const wallet = await browserJson(page, 'POST', '/api/v1/wallet', {name})
  return walletFromResponse(wallet)
}

export async function fundWalletWithFakeBalance(
  page: Page,
  walletId: string,
  {amountSats}: {amountSats: number}
): Promise<void> {
  const response = await browserJson(page, 'PUT', '/users/api/v1/balance', {
    id: walletId,
    amount: amountSats
  })
  if (!isRecord(response) || response.success !== true) {
    throw new Error(`Fake balance update failed: ${JSON.stringify(response)}`)
  }
}

export async function walletBalanceSat(
  page: Page,
  wallet: E2EWallet
): Promise<number> {
  const response = await browserJson(
    page,
    'GET',
    '/api/v1/wallet',
    undefined,
    wallet.inkey
  )
  if (!isRecord(response) || typeof response.balance !== 'number') {
    throw new Error(
      `Wallet response missing balance: ${JSON.stringify(response)}`
    )
  }
  return Math.trunc(response.balance / 1000)
}

export async function waitForWalletBalance(
  page: Page,
  wallet: E2EWallet,
  {expectedSats, timeout = 30_000}: {expectedSats: number; timeout?: number}
): Promise<number> {
  return waitForResult(
    `wallet ${wallet.id} balance to reach ${expectedSats} sats`,
    async () => {
      const balance = await walletBalanceSat(page, wallet)
      return balance >= expectedSats ? balance : null
    },
    {timeout}
  )
}

export async function createInvoice(
  page: Page,
  wallet: E2EWallet,
  {
    amountSats,
    memo,
    extra = {}
  }: {amountSats: number; extra?: Record<string, unknown>; memo: string}
): Promise<Record<string, unknown>> {
  const invoice = await browserJson(
    page,
    'POST',
    '/api/v1/payments',
    {
      out: false,
      amount: amountSats,
      unit: 'sat',
      memo,
      extra
    },
    wallet.inkey
  )
  if (!isRecord(invoice)) {
    throw new Error(
      `Invoice response is not an object: ${JSON.stringify(invoice)}`
    )
  }
  expect(invoicePaymentRequest(invoice).toLowerCase()).toMatch(/^lnbc/)
  return invoice
}

export async function payInvoiceWithWallet(
  page: Page,
  wallet: E2EWallet,
  paymentRequest: string
): Promise<Record<string, unknown>> {
  const payment = await browserJson(
    page,
    'POST',
    '/api/v1/payments',
    {out: true, bolt11: paymentRequest},
    wallet.adminkey
  )
  if (!isRecord(payment)) {
    throw new Error(
      `Payment response is not an object: ${JSON.stringify(payment)}`
    )
  }
  return payment
}

export function invoicePaymentRequest(
  invoice: Record<string, unknown>
): string {
  const paymentRequest = invoice.payment_request ?? invoice.bolt11
  if (typeof paymentRequest !== 'string') {
    throw new Error(
      `Invoice response missing payment request: ${JSON.stringify(invoice)}`
    )
  }
  return paymentRequest
}

export async function installAndEnableExtension(
  page: Page,
  extension: ExtensionUnderTest
): Promise<void> {
  await installExtension(page, extension)
  await enableExtension(page, extension)
}

export async function installExtension(
  page: Page,
  extension: ExtensionUnderTest
): Promise<void> {
  const state = await extensionState(page, extension.extId)
  if (state?.isInstalled) {
    if (!state.isActive) {
      await activateInstalledExtension(page, extension)
      await waitForInstalledExtension(page, extension.extId)
    }
    return
  }

  const installable = await waitForInstallableExtension(page, extension)
  const release = latestReleaseFor(installable)

  await page.goto('/extensions')
  await dismissDisclaimer(page)
  await selectExtensionsTab(page, 'All')
  await filterExtensions(page, extension.name)
  const extensionCard = extensionCardFor(page, extension)
  await expect(extensionCard).toBeVisible({timeout: 120_000})
  await extensionCard.getByRole('button', {name: /^manage$/i}).click()

  const manageDialog = manageExtensionDialog(page)
  await expect(manageDialog).toBeVisible({timeout: 60_000})
  await expect(
    manageDialog.getByRole('tab', {name: /^releases$/i})
  ).toBeVisible({
    timeout: 60_000
  })

  const version = String(release.version)
  const sourceRepo = String(release.source_repo)
  const repositoryLabel = manageDialog.getByText(sourceRepo).first()
  await expect(repositoryLabel).toBeVisible({timeout: 120_000})
  await repositoryLabel.click()

  const releaseLabel = manageDialog.getByText(version).first()
  await expect(releaseLabel).toBeVisible({timeout: 120_000})
  await releaseLabel.click()

  const installButton = manageDialog
    .getByRole('button', {name: /^install$/i})
    .first()
  await expect(installButton).toBeVisible({timeout: 120_000})
  await installButton.click()

  const permissionsDialog = page
    .locator('.q-dialog')
    .filter({hasText: 'Grant extension permissions'})
    .last()
  let hasPermissionsDialog = false
  try {
    await expect(permissionsDialog).toBeVisible({
      timeout: 10_000
    })
    hasPermissionsDialog = true
  } catch (_error) {}

  if (hasPermissionsDialog) {
    for (const permissionText of extension.permissionTexts ?? []) {
      await expect(
        permissionsDialog.getByText(permissionText).first()
      ).toBeVisible({
        timeout: 60_000
      })
    }
    const grantButton = permissionsDialog.getByRole('button', {
      name: /^grant and install$/i
    })
    await expect(grantButton).toBeEnabled({timeout: 60_000})
    await grantButton.click()
  }

  await waitForInstalledExtension(page, extension.extId)
  const latestConfig = await latestReleaseConfig(release)
  const permissions = Array.isArray(latestConfig.permissions)
    ? latestConfig.permissions.filter(isRecord)
    : []
  let installed = await extensionState(page, extension.extId)
  let grantedPermissionIds = installedPermissionIds(installed)
  const missingPermissionIds = permissions
    .map(permission => permission.id)
    .filter(permissionId => !grantedPermissionIds.has(permissionId))

  if (extension.configUrl && missingPermissionIds.length) {
    const response = await page
      .context()
      .request.put(
        `/api/v1/extension/${encodeURIComponent(extension.extId)}/permissions`,
        {data: {permissions}}
      )
    expect(
      response.ok(),
      `Could not grant local fixture permissions: ${await response.text()}`
    ).toBe(true)
    installed = await extensionState(page, extension.extId)
    grantedPermissionIds = installedPermissionIds(installed)
  }

  for (const permission of permissions) {
    expect(
      grantedPermissionIds.has(permission.id),
      `Missing extension permission: ${String(permission.id)}`
    ).toBe(true)
  }
}

export async function enableExtension(
  page: Page,
  extension: ExtensionUnderTest
): Promise<void> {
  if (await userExtensionEnabled(page, extension.extId)) return

  await page.goto(`/extensions#${encodeURIComponent(extension.extId)}`)
  await dismissDisclaimer(page)
  const extensionCard = extensionCardFor(page, extension)
  await expect(extensionCard).toBeVisible({timeout: 120_000})
  const enableButton = extensionCard.getByRole('button', {name: /^enable$/i})
  await expect(enableButton).toBeVisible({timeout: 60_000})
  await enableButton.click()
  await expect(page.getByText('Extension enabled!')).toBeVisible({
    timeout: 60_000
  })
  await waitForResult(
    `${extension.extId} extension to be enabled for the user`,
    async () =>
      (await userExtensionEnabled(page, extension.extId)) ? true : null,
    {timeout: 60_000, interval: 1_000}
  )
  await expect(extensionCard.getByRole('link', {name: /^open$/i})).toBeVisible({
    timeout: 60_000
  })
}

export async function activateInstalledExtension(
  page: Page,
  extension: ExtensionUnderTest
): Promise<void> {
  await page.goto('/extensions')
  await selectExtensionsTab(page, 'Installed')
  await filterExtensions(page, extension.name)
  const extensionCard = extensionCardFor(page, extension)
  await expect(extensionCard).toBeVisible({timeout: 120_000})
  const inactiveToggle = extensionCard.getByText(/^deactivated$/i)
  try {
    await inactiveToggle.click({timeout: 5_000})
  } catch (_error) {
    return
  }
  await expect(
    page.getByText(
      new RegExp(`Extension '${escapeRegExp(extension.extId)}' activated!`)
    )
  ).toBeVisible({timeout: 60_000})
}

export async function waitForInstallableExtension(
  page: Page,
  extension: ExtensionUnderTest,
  {timeout = 360_000}: {timeout?: number} = {}
): Promise<Record<string, unknown>> {
  let lastResponse: unknown
  let lastError: unknown
  const deadline = Date.now() + timeout

  while (Date.now() < deadline) {
    try {
      lastError = undefined
      await waitForInstallableExtensionRefresh(page, deadline)
      const extensions = await browserJson(page, 'GET', '/api/v1/extension/all')
      lastResponse = extensions
      const extensionList = Array.isArray(extensions) ? extensions : []
      const installable = extensionList
        .filter(isRecord)
        .find(item => item.id === extension.extId)
      if (installable) return installable
      await waitForInstallableExtensionRefresh(page, deadline)
    } catch (error) {
      lastError = error
    }
    await delay(2_000)
  }

  throw new Error(
    `${extension.name} extension did not become installable: ${JSON.stringify(lastResponse)}. Last error: ${String(lastError)}`
  )
}

export async function waitForInstalledExtension(
  page: Page,
  extensionId: string,
  {timeout = 120_000}: {timeout?: number} = {}
): Promise<void> {
  await waitForResult(
    `${extensionId} extension to be installed and active`,
    async () => {
      const state = await extensionState(page, extensionId)
      return state?.isInstalled && state.isActive ? true : null
    },
    {timeout, interval: 2_000}
  )
}

export async function extensionState(
  page: Page,
  extensionId: string
): Promise<Record<string, unknown> | null> {
  const extensions = await browserJson(page, 'GET', '/api/v1/extension/all')
  if (!Array.isArray(extensions)) {
    throw new Error(
      `Extensions response is not a list: ${JSON.stringify(extensions)}`
    )
  }
  return (
    extensions
      .filter(isRecord)
      .find(extension => extension.id === extensionId) ?? null
  )
}

async function userExtensionEnabled(
  page: Page,
  extensionId: string
): Promise<boolean> {
  const extensions = await browserJson(page, 'GET', '/api/v1/extension')
  if (!Array.isArray(extensions)) {
    throw new Error(
      `User extensions response is not a list: ${JSON.stringify(extensions)}`
    )
  }
  return extensions
    .filter(isRecord)
    .some(extension => extension.code === extensionId)
}

export async function grantBackgroundPaymentPermission(
  page: Page,
  extensionId: string,
  walletId: string,
  {
    maxAmountSats,
    destinationPolicy = 'external_allowed'
  }: {destinationPolicy?: string; maxAmountSats: number}
): Promise<Record<string, unknown>> {
  const response = await browserJson(
    page,
    'POST',
    `/api/v1/extension/${extensionId}/permissions/background-payment`,
    {
      wallet_id: walletId,
      max_amount: maxAmountSats,
      destination_policy: destinationPolicy
    }
  )
  if (!isRecord(response)) {
    throw new Error(
      `Permission response is not an object: ${JSON.stringify(response)}`
    )
  }
  return response
}

export async function grantWalletPaymentsWatchPermission(
  page: Page,
  extensionId: string,
  walletId: string
): Promise<Record<string, unknown>> {
  const response = await browserJson(
    page,
    'POST',
    `/api/v1/extension/${extensionId}/permissions/wallet-payments-watch`,
    {wallet_id: walletId}
  )
  if (!isRecord(response)) {
    throw new Error(
      `Permission response is not an object: ${JSON.stringify(response)}`
    )
  }
  return response
}

export async function extensionApi(
  page: Page,
  extensionId: string,
  method: string,
  path: string,
  data?: Record<string, unknown>
): Promise<Record<string, unknown>> {
  const body = await browserJson(
    page,
    method,
    `/api/v1/ext/${extensionId}${path}`,
    data
  )
  if (isRecord(body) && body.ok === false) {
    throw new Error(`${method} ${path} failed: ${JSON.stringify(body)}`)
  }
  const responseData = isRecord(body) && isRecord(body.data) ? body.data : body
  if (!isRecord(responseData)) {
    throw new Error(
      `${method} ${path} returned non-object data: ${JSON.stringify(body)}`
    )
  }
  return responseData
}

export async function extensionFrame(
  page: Page,
  title: string
): Promise<Frame> {
  const iframe = page.locator(`iframe[title="${title}"]`)
  await expect(iframe).toBeVisible({timeout: 60_000})
  const handle = await iframe.elementHandle()
  const frame = await handle?.contentFrame()
  if (!frame) throw new Error(`Extension iframe not found: ${title}`)
  return frame
}

function extensionCardFor(page: Page, extension: ExtensionUnderTest): Locator {
  return page.locator('.q-card').filter({hasText: extension.name}).first()
}

async function filterExtensions(page: Page, searchTerm: string): Promise<void> {
  await page
    .locator('.q-field')
    .filter({hasText: 'Search extensions'})
    .locator('input')
    .fill(searchTerm)
}

async function selectExtensionsTab(page: Page, tabName: string): Promise<void> {
  const tab = page.getByRole('tab', {
    name: new RegExp(`^${escapeRegExp(tabName)}$`, 'i')
  })
  await expect(tab).toBeVisible({timeout: 60_000})
  for (let attempt = 0; attempt < 3; attempt += 1) {
    await tab.click()
    try {
      await expect(tab).toHaveAttribute('aria-selected', 'true', {
        timeout: 5_000
      })
      return
    } catch (_error) {
      await page.waitForTimeout(500)
    }
  }
  await expect(tab).toHaveAttribute('aria-selected', 'true', {timeout: 60_000})
}

function manageExtensionDialog(page: Page): Locator {
  return page.locator('.q-dialog').filter({hasText: 'Releases'}).last()
}

async function waitForInstallableExtensionRefresh(
  page: Page,
  deadline: number
): Promise<void> {
  while (Date.now() < deadline) {
    const tasks = await browserJson(page, 'GET', '/admin/api/v1/monitor')
    if (!Array.isArray(tasks)) return
    if (
      !tasks
        .filter(isRecord)
        .some(task => task.name === INSTALLABLE_EXTENSION_REFRESH_TASK)
    ) {
      return
    }
    await delay(2_000)
  }
}

function latestReleaseFor(
  installable: Record<string, unknown>
): Record<string, unknown> {
  const release = installable.latestRelease
  if (
    !isRecord(release) ||
    typeof release.version !== 'string' ||
    typeof release.source_repo !== 'string' ||
    typeof release.details_link !== 'string'
  ) {
    throw new Error(
      `Installable extension is missing release metadata: ${JSON.stringify(installable)}`
    )
  }
  return release
}

function installedPermissionIds(
  extension: Record<string, unknown> | null
): Set<unknown> {
  return new Set(
    Array.isArray(extension?.permissions)
      ? extension.permissions.filter(isRecord).map(permission => permission.id)
      : []
  )
}

async function latestReleaseConfig(
  release: Record<string, unknown>
): Promise<Record<string, unknown>> {
  const config = await fetchJson(String(release.details_link))
  if (!isRecord(config)) {
    throw new Error(
      `Invalid extension config response: ${JSON.stringify(config)}`
    )
  }
  return config
}

async function fetchJson(url: string): Promise<unknown> {
  const response = await fetch(url, {
    headers: {
      Accept: 'application/json',
      'User-Agent': 'LNbits Playwright e2e'
    }
  })
  const text = await response.text()
  if (!response.ok) {
    throw new Error(`${url} failed with ${response.status}: ${text}`)
  }
  return text ? JSON.parse(text) : {}
}

function walletFromResponse(wallet: unknown): E2EWallet {
  if (!isRecord(wallet)) {
    throw new Error(
      `Wallet response is not an object: ${JSON.stringify(wallet)}`
    )
  }
  return {
    adminkey: String(wallet.adminkey),
    id: String(wallet.id),
    inkey: String(wallet.inkey),
    name: String(wallet.name ?? wallet.id)
  }
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}
