/**
 * Authentication helper for UI tests
 * Centralizes configuration and login functionality for wallet sharing tests
 */

const fs = require('fs')
const path = require('path')

/**
 * Load environment variables from .env.local
 */
function loadEnv() {
  const envPath = path.join(__dirname, '../../.env.local')
  const config = {}

  if (fs.existsSync(envPath)) {
    const content = fs.readFileSync(envPath, 'utf-8')
    const lines = content.split('\n')

    for (const line of lines) {
      if (line && !line.startsWith('#')) {
        const [key, value] = line.split('=')
        if (key && value) {
          config[key.trim()] = value.trim()
        }
      }
    }
  }

  return config
}

/**
 * Get configuration for tests
 * @returns {Object} Configuration object with baseUrl, username, password, etc.
 */
function getConfig() {
  const config = loadEnv()

  return {
    baseUrl:
      config.TEST_LNBITS_URL ||
      process.env.TEST_LNBITS_URL ||
      'http://localhost:5001',
    username: config.LNBITS_ADMIN_USERNAME || process.env.LNBITS_ADMIN_USERNAME,
    password: config.LNBITS_ADMIN_PASSWORD || process.env.LNBITS_ADMIN_PASSWORD,
    secondaryUsername:
      config.LNBITS_SECONDARY_USERNAME || process.env.LNBITS_SECONDARY_USERNAME,
    secondaryPassword:
      config.LNBITS_SECONDARY_PASSWORD || process.env.LNBITS_SECONDARY_PASSWORD,
    walletName:
      config.TEST_WALLET_NAME || process.env.TEST_WALLET_NAME || 'Test Wallet'
  }
}

/**
 * Login to LNBits as a specific user
 * @param {Page} page - Playwright page object
 * @param {string} username - Optional username (defaults to primary admin)
 * @param {string} password - Optional password (defaults to primary admin)
 */
async function login(page, username = null, password = null) {
  const config = getConfig()
  const user = username || config.username
  const pass = password || config.password

  console.log(`📝 Logging in as ${user}...`)

  await page.goto(config.baseUrl)
  await page.waitForLoadState('networkidle')

  // Check if we need to switch to login screen
  const createAccountVisible = await page
    .locator('text=Create Account')
    .first()
    .isVisible()
  if (createAccountVisible) {
    await page.click('text=Login')
    await page.waitForTimeout(2000)
  }

  // Fill login credentials - wait for each field to be ready
  const usernameInput = page
    .locator('input[type="text"], input[type="email"]')
    .first()
  const passwordInput = page.locator('input[type="password"]').first()

  await usernameInput.waitFor({state: 'visible'})
  await usernameInput.fill(user)

  await passwordInput.waitFor({state: 'visible'})
  await passwordInput.fill(pass)

  // Wait a moment for Vue reactivity
  await page.waitForTimeout(500)

  // Find and click the login button - try multiple strategies
  const loginButton = page.locator('button:has-text("LOGIN")').first()
  await loginButton.waitFor({state: 'visible'})
  await loginButton.click()

  // Wait for navigation or error
  await page.waitForTimeout(3000)

  const indicators = [
    'text=Extensions',
    'text=Add a new wallet',
    '.q-btn:has-text("Add a new wallet")',
    'text=sats'
  ]

  let isLoggedIn = false
  for (const indicator of indicators) {
    try {
      if (await page.locator(indicator).isVisible({timeout: 5000})) {
        isLoggedIn = true
        console.log(`✅ Login verified using indicator: ${indicator}`)
        break
      }
    } catch (error) {
      // Continue to next indicator
    }
  }

  if (!isLoggedIn) {
    await page.screenshot({
      path: 'tests/ui/screenshots/login-verification-failed.png',
      fullPage: true
    })
    throw new Error('Login failed - could not verify successful login')
  }

  console.log(`✅ Successfully logged in as ${user}`)
}

/**
 * Get admin API key from the page
 * @param {Page} page - Playwright page object
 * @returns {string} Admin API key
 */
async function getAdminApiKey(page) {
  try {
    // Navigate to wallet if not already there
    const currentUrl = page.url()
    if (!currentUrl.includes('/wallet')) {
      await page.goto(`${getConfig().baseUrl}/wallet`)
      await page.waitForTimeout(2000)
    }

    // Try to extract API key from page context
    const apiKey = await page.evaluate(() => {
      // Try to get from Vue app
      if (
        window.app &&
        window.app.g &&
        window.app.g.wallet &&
        window.app.g.wallet.adminkey
      ) {
        return window.app.g.wallet.adminkey
      }
      // Try to get from localStorage
      const user = localStorage.getItem('lnbits.user')
      if (user) {
        const userData = JSON.parse(user)
        if (userData.wallets && userData.wallets.length > 0) {
          return userData.wallets[0].adminkey
        }
      }
      return null
    })

    if (apiKey) {
      console.log('✅ Admin API key retrieved')
      return apiKey
    }

    console.log('⚠️ Could not retrieve admin API key')
    return null
  } catch (error) {
    console.log('⚠️ Error getting admin API key:', error.message)
    return null
  }
}

/**
 * Get wallet ID from the page
 * @param {Page} page - Playwright page object
 * @returns {string} Wallet ID
 */
async function getWalletId(page) {
  try {
    const walletId = await page.evaluate(() => {
      if (
        window.app &&
        window.app.g &&
        window.app.g.wallet &&
        window.app.g.wallet.id
      ) {
        return window.app.g.wallet.id
      }
      const user = localStorage.getItem('lnbits.user')
      if (user) {
        const userData = JSON.parse(user)
        if (userData.wallets && userData.wallets.length > 0) {
          return userData.wallets[0].id
        }
      }
      return null
    })

    if (walletId) {
      console.log(`✅ Wallet ID retrieved: ${walletId}`)
      return walletId
    }

    console.log('⚠️ Could not retrieve wallet ID')
    return null
  } catch (error) {
    console.log('⚠️ Error getting wallet ID:', error.message)
    return null
  }
}

module.exports = {
  login,
  getConfig,
  getAdminApiKey,
  getWalletId
}
