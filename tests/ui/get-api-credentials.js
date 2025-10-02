/**
 * Helper script to extract API credentials from logged-in admin
 * This populates TEST_ADMIN_API_KEY and TEST_WALLET_ID in .env.local
 */

const {chromium} = require('playwright')
const {login, getConfig, getAdminApiKey, getWalletId} = require('./auth-helper')
const fs = require('fs')
const path = require('path')

async function getApiCredentials() {
  const config = getConfig()
  const browser = await chromium.launch({headless: false})
  const context = await browser.newContext()
  const page = await context.newPage()

  try {
    console.log('🔐 Logging in as admin to extract API credentials...\n')

    // Login as admin
    await login(page, config.username, config.password)

    // Get API key and wallet ID
    const apiKey = await getAdminApiKey(page)
    const walletId = await getWalletId(page)

    if (apiKey && walletId) {
      console.log('✅ Successfully extracted credentials:')
      console.log(`   Admin API Key: ${apiKey.substring(0, 20)}...`)
      console.log(`   Wallet ID: ${walletId}\n`)

      // Update .env.local
      const envPath = path.join(__dirname, '../../.env.local')
      let envContent = ''

      if (fs.existsSync(envPath)) {
        envContent = fs.readFileSync(envPath, 'utf-8')
      }

      // Update or add TEST_ADMIN_API_KEY
      if (envContent.includes('TEST_ADMIN_API_KEY=')) {
        envContent = envContent.replace(
          /TEST_ADMIN_API_KEY=.*/,
          `TEST_ADMIN_API_KEY=${apiKey}`
        )
      } else {
        envContent += `\nTEST_ADMIN_API_KEY=${apiKey}`
      }

      // Update or add TEST_WALLET_ID
      if (envContent.includes('TEST_WALLET_ID=')) {
        envContent = envContent.replace(
          /TEST_WALLET_ID=.*/,
          `TEST_WALLET_ID=${walletId}`
        )
      } else {
        envContent += `\nTEST_WALLET_ID=${walletId}`
      }

      fs.writeFileSync(envPath, envContent)

      console.log('✅ Updated .env.local with API credentials')
      console.log(
        '📝 You can now run the API tests with: cd tests && ./run_api_tests.sh\n'
      )
    } else {
      console.log('❌ Could not extract credentials')
      console.log('   Make sure the admin user has a wallet created')
      process.exit(1)
    }
  } catch (error) {
    console.error('❌ Error:', error.message)
    throw error
  } finally {
    await browser.close()
  }
}

// Run the script
if (require.main === module) {
  getApiCredentials()
    .then(() => {
      console.log('✅ Done!')
      process.exit(0)
    })
    .catch(error => {
      console.error('❌ Failed:', error.message)
      process.exit(1)
    })
}

module.exports = {getApiCredentials}
