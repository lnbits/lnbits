const {chromium} = require('playwright')
const path = require('path')
const {
  login,
  getConfig,
  getWalletsFromStorage
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

    // Step 2: Check user has a wallet via UI
    console.log('📝 Step 2: Checking user has a wallet...')
    await page.goto(`${config.baseUrl}/wallet`)
    await page.waitForTimeout(2000)

    // Count wallet items in UI
    const walletCount = await page
      .locator('.q-drawer .q-list .q-item')
      .filter({hasNot: page.locator('text=Add a new wallet')})
      .count()

    if (walletCount === 0) {
      throw new Error(
        'No wallets found in UI. Please run create-wallet.js first.'
      )
    }

    console.log(`✅ User has ${walletCount} wallet(s)`)

    // Get wallet data from localStorage for API calls
    const wallets = await getWalletsFromStorage(page)
    const existingWallet = wallets[0]
    const walletId = existingWallet.id
    const adminKey = existingWallet.adminkey

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

    let shares = await response.json()

    // If no shares exist, create one first
    if (!Array.isArray(shares) || shares.length === 0) {
      console.log('⚠️ No shares found. Creating one first...')
      const shareWithUser = config.secondaryUsername
      if (!shareWithUser) {
        throw new Error('LNBITS_SECONDARY_USERNAME must be set in .env.local')
      }

      const createResponse = await page.request.post(
        `${config.baseUrl}/api/v1/wallet_shares/${walletId}`,
        {
          headers: {
            'X-Api-Key': adminKey,
            'Content-Type': 'application/json'
          },
          data: JSON.stringify({
            user_id: shareWithUser,
            permissions: 1
          })
        }
      )

      if (!createResponse.ok()) {
        throw new Error(`Failed to create share: ${createResponse.status()}`)
      }

      console.log('✅ Created test share')

      // Re-fetch shares
      const refetchResponse = await page.request.get(
        `${config.baseUrl}/api/v1/wallet_shares/${walletId}`,
        {
          headers: {'X-Api-Key': adminKey}
        }
      )
      shares = await refetchResponse.json()
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
