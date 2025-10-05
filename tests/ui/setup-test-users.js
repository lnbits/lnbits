/**
 * Setup script to create test users for wallet sharing tests
 * Creates both admin and secondary user accounts
 */

const {chromium} = require('playwright')
const {getConfig} = require('./auth-helper')
const path = require('path')

async function setupTestUsers() {
  const config = getConfig()
  const browser = await chromium.launch({headless: false})
  const context = await browser.newContext()
  const page = await context.newPage()

  try {
    console.log('🚀 Setting up test users...\n')

    // Create admin user
    console.log('👤 Creating admin user...')
    await createUser(page, config.baseUrl, config.username, config.password)
    console.log('✅ Admin user created\n')

    // Create secondary user
    console.log('👤 Creating secondary user...')
    await createUser(
      page,
      config.baseUrl,
      config.secondaryUsername,
      config.secondaryPassword
    )
    console.log('✅ Secondary user created\n')

    console.log('✅ Test users setup complete!')
  } catch (error) {
    console.error('❌ Error during setup:', error.message)
    throw error
  } finally {
    await browser.close()
  }
}

async function createUser(page, baseUrl, username, password) {
  await page.goto(baseUrl)
  await page.waitForLoadState('networkidle')

  // Check if we're on login page - if so, click "Create Account"
  const loginVisible = await page
    .locator('text=Login to your account')
    .isVisible({timeout: 2000})
    .catch(() => false)

  if (loginVisible) {
    // We're on login page, need to switch to create account
    const createAccountLink = page.locator('text=Create an Account').first()
    if (await createAccountLink.isVisible({timeout: 2000}).catch(() => false)) {
      await createAccountLink.click()
      await page.waitForTimeout(1000)
    }
  }

  // Look for create account form
  const createAccountVisible = await page
    .locator('text=Create Account')
    .isVisible({timeout: 2000})
    .catch(() => false)

  if (createAccountVisible) {
    // Fill in the create account form
    const usernameInput = page.locator('input[type="text"]').first()
    const passwordInput = page.locator('input[type="password"]').first()

    await usernameInput.fill(username)
    await passwordInput.fill(password)

    // Click create account button
    await page.click('button:has-text("CREATE ACCOUNT")')
    await page.waitForTimeout(3000)

    console.log(`   ✓ Account created for ${username}`)
  } else {
    // Already logged in or on a different page
    console.log(
      `   ℹ️  User ${username} may already exist or browser already logged in`
    )
  }
}

// Run the setup
if (require.main === module) {
  setupTestUsers()
    .then(() => {
      console.log('\n✅ Setup complete!')
      process.exit(0)
    })
    .catch(error => {
      console.error('\n❌ Setup failed:', error.message)
      process.exit(1)
    })
}

module.exports = {setupTestUsers}
