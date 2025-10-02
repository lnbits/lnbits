const {chromium} = require('playwright')
const path = require('path')
const {
  login,
  getConfig,
  getAdminApiKey,
  getWalletId
} = require('../auth-helper')

/**
 * Test: Update wallet share permissions
 * This test updates permissions on an existing wallet share
 */

;(async () => {
  const browser = await chromium.launch({headless: true, slowMo: 500})
  const page = await browser.newPage()
  const config = getConfig()

  let success = false

  try {
    console.log('🚀 Starting update wallet share test...')

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

    if (!walletId || !adminKey) {
      throw new Error('Could not get wallet ID or admin key')
    }

    console.log(`✅ Using wallet ID: ${walletId}`)

    // Step 3: Get existing shares
    console.log('📝 Step 3: Getting existing shares...')
    const response = await page.request.get(
      `${config.baseUrl}/api/v1/wallet_shares/${walletId}`,
      {
        headers: {'X-Api-Key': adminKey}
      }
    )

    if (!response.ok()) {
      throw new Error(`Failed to get shares: ${response.status()}`)
    }

    const shares = await response.json()
    if (!Array.isArray(shares) || shares.length === 0) {
      console.log('⚠️ No shares found to update. Please create a share first.')
      process.exit(0)
    }

    const shareToUpdate = shares[0]
    console.log(`📄 Found share to update: ${shareToUpdate.id}`)
    console.log(`   Current permissions: ${shareToUpdate.permissions}`)

    // Step 4: Update permissions via API
    console.log('📝 Step 4: Updating share permissions...')

    // Change permissions (if VIEW=1, change to VIEW+CREATE_INVOICE=3)
    const newPermissions = shareToUpdate.permissions === 1 ? 3 : 1

    const updateResponse = await page.request.put(
      `${config.baseUrl}/api/v1/wallet_shares/${shareToUpdate.id}`,
      {
        headers: {
          'X-Api-Key': adminKey,
          'Content-Type': 'application/json'
        },
        data: JSON.stringify({permissions: newPermissions})
      }
    )

    if (updateResponse.ok()) {
      const updatedShare = await updateResponse.json()
      console.log(`✅ Share updated successfully`)
      console.log(`   New permissions: ${updatedShare.permissions}`)
      success = true
    } else {
      console.log(`❌ Update failed: ${updateResponse.status()}`)
      const errorText = await updateResponse.text()
      console.log(`   Error: ${errorText}`)
    }

    // Step 5: Verify update
    console.log('📝 Step 5: Verifying update...')
    const verifyResponse = await page.request.get(
      `${config.baseUrl}/api/v1/wallet_shares/${walletId}`,
      {
        headers: {'X-Api-Key': adminKey}
      }
    )

    if (verifyResponse.ok()) {
      const updatedShares = await verifyResponse.json()
      const verifiedShare = updatedShares.find(s => s.id === shareToUpdate.id)

      if (verifiedShare && verifiedShare.permissions === newPermissions) {
        console.log('✅ Update verified - permissions match!')
        success = true
      } else {
        console.log('❌ Update verification failed - permissions do not match')
        success = false
      }
    }

    // Take screenshot
    await page.screenshot({
      path: path.join(__dirname, '../screenshots/update-share-result.png'),
      fullPage: true
    })

    if (success) {
      console.log('🎉 SUCCESS! Share updated successfully!')
    }
  } catch (error) {
    console.error('💥 Error:', error.message)
    await page.screenshot({
      path: path.join(__dirname, '../screenshots/update-share-error.png'),
      fullPage: true
    })
  } finally {
    await browser.close()
  }

  process.exit(success ? 0 : 1)
})()
