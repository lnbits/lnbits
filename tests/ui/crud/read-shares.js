const {chromium} = require('playwright')
const path = require('path')
const {
  login,
  getConfig,
  getAdminApiKey,
  getWalletId
} = require('../auth-helper')

/**
 * Test: Read wallet shares
 * This test retrieves and displays existing wallet shares
 */

;(async () => {
  const browser = await chromium.launch({headless: true, slowMo: 500})
  const page = await browser.newPage()
  const config = getConfig()

  let success = false

  try {
    console.log('🚀 Starting read wallet shares test...')

    // Step 1: Login as admin
    console.log('📝 Step 1: Logging in as admin...')
    await login(page)

    // Step 2: Navigate to wallet page
    console.log('📝 Step 2: Navigating to wallet page...')
    await page.goto(`${config.baseUrl}/wallet`)
    await page.waitForTimeout(3000)

    // Get wallet ID and API key
    const walletId = await getWalletId(page)
    const adminKey = await getAdminApiKey(page)

    if (!walletId) {
      throw new Error('Could not get wallet ID')
    }

    console.log(`✅ Using wallet ID: ${walletId}`)

    // Step 3: Read shares via API
    console.log('📝 Step 3: Reading shares via API...')
    if (adminKey) {
      try {
        const response = await page.request.get(
          `${config.baseUrl}/api/v1/wallet_shares/${walletId}`,
          {
            headers: {'X-Api-Key': adminKey}
          }
        )

        if (response.ok()) {
          const shares = await response.json()
          const count = Array.isArray(shares) ? shares.length : 0

          console.log(`📊 Found ${count} share(s)`)

          if (Array.isArray(shares) && shares.length > 0) {
            shares.forEach((share, index) => {
              console.log(`\n📄 Share ${index + 1}:`)
              console.log(`   ID: ${share.id}`)
              console.log(`   User: ${share.username || share.user_id}`)
              console.log(`   Permissions: ${share.permissions}`)
              console.log(`   Shared by: ${share.shared_by}`)
              console.log(`   Shared at: ${share.shared_at}`)
              console.log(`   Accepted: ${share.accepted}`)
            })
          }

          success = true
          console.log('\n✅ SUCCESS! Shares read successfully')
        } else {
          console.log(`❌ API returned ${response.status()}`)
        }
      } catch (error) {
        console.log('❌ Error reading shares:', error.message)
      }
    } else {
      console.log('❌ No admin API key available')
    }

    // Step 4: Verify UI shows shares
    console.log('\n📝 Step 4: Checking UI for Share Wallet button...')
    const shareButton = page.locator('button:has-text("Share Wallet")')

    if (await shareButton.isVisible({timeout: 5000})) {
      await shareButton.click()
      await page.waitForTimeout(2000)

      // Take screenshot of shares dialog
      await page.screenshot({
        path: path.join(__dirname, '../screenshots/read-shares-dialog.png'),
        fullPage: true
      })
      console.log('📸 Screenshot saved: read-shares-dialog.png')

      // Check for "Current Shares" section
      const currentSharesSection = page.locator(
        'text=Current Shares, text=Shared Users'
      )
      if (await currentSharesSection.isVisible()) {
        console.log('✅ Current Shares section visible in UI')
      }

      console.log('✅ UI verification complete')
    }
  } catch (error) {
    console.error('💥 Error:', error.message)
    await page.screenshot({
      path: path.join(__dirname, '../screenshots/read-shares-error.png'),
      fullPage: true
    })
  } finally {
    await browser.close()
  }

  process.exit(success ? 0 : 1)
})()
