const {chromium} = require('playwright')
const path = require('path')
const {
  login,
  getConfig,
  createTestWallet,
  getWalletsFromStorage
} = require('../auth-helper')

/**
 * Test: Create wallet share
 * This test creates a new wallet share with another user
 */

;(async () => {
  const browser = await chromium.launch({headless: true, slowMo: 500})
  const page = await browser.newPage()
  const config = getConfig()

  let success = false

  try {
    console.log('🚀 Starting create wallet share test...')

    // Listen for console errors
    page.on('console', msg => {
      if (msg.type() === 'error') {
        console.log('❌ Browser console error:', msg.text())
      }
    })

    page.on('pageerror', error => {
      console.log('💥 Page error:', error.message)
    })

    // Monitor network requests for share creation
    let lastCreateResponse = null
    page.on('response', response => {
      if (
        response.url().includes('/api/v1/wallet_shares/') &&
        response.request().method() === 'POST'
      ) {
        lastCreateResponse = {status: response.status(), url: response.url()}
        console.log(`📥 POST response: ${response.status()} ${response.url()}`)
      }
    })

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
    const existingAdminKey = existingWallet.adminkey
    console.log(`✅ Using wallet: ${existingWallet.id}`)

    // Step 3: Create a fresh test wallet via API
    console.log('📝 Step 3: Creating fresh test wallet via API...')
    const testWallet = await createTestWallet(page, existingAdminKey)
    if (!testWallet) {
      throw new Error('Failed to create test wallet')
    }

    const walletId = testWallet.id
    const adminKey = testWallet.adminkey ||  testWallet.inkey

    console.log(`✅ Using test wallet ID: ${walletId}`)

    // Navigate to the test wallet
    await page.goto(`${config.baseUrl}/wallet?wal=${walletId}`)
    await page.waitForTimeout(3000)

    // Step 4: Get initial share count
    console.log('📝 Step 4: Getting initial share count...')
    let initialCount = 0
    if (adminKey) {
      try {
        const initialResponse = await page.request.get(
          `${config.baseUrl}/api/v1/wallet_shares/${walletId}`,
          {
            headers: {'X-Api-Key': adminKey}
          }
        )
        if (initialResponse.ok()) {
          const initialData = await initialResponse.json()
          initialCount = Array.isArray(initialData) ? initialData.length : 0
        }
      } catch (error) {
        console.log('⚠️ Could not get initial count:', error.message)
      }
    }
    console.log(`📊 Initial share count: ${initialCount}`)

    // Step 5: Open Share Wallet dialog
    console.log('📝 Step 5: Opening Share Wallet dialog...')
    // The Share Wallet button is a round button with group icon in top right
    const shareButton = page.locator('button.text-deep-purple i.material-icons:has-text("group")').locator('..')

    if (await shareButton.isVisible({timeout: 5000})) {
      await shareButton.click()
      await page.waitForTimeout(2000)

      // Take screenshot of dialog
      await page.screenshot({
        path: path.join(__dirname, '../screenshots/create-share-dialog.png'),
        fullPage: true
      })
      console.log('📸 Screenshot saved: create-share-dialog.png')

      // Step 5: Fill the form
      console.log('📝 Step 5: Filling share form...')

      // Get secondary username from config
      const shareWithUser = config.secondaryUsername
      if (!shareWithUser) {
        throw new Error('LNBITS_SECONDARY_USERNAME must be set in .env.local')
      }

      console.log(`📧 Sharing with user: ${shareWithUser}`)

      // Fill user ID field - find the input within the Share Wallet dialog
      const userIdInput = page.locator('.q-dialog input[type="text"]').first()
      await userIdInput.waitFor({state: 'visible'})
      await userIdInput.click()
      await userIdInput.fill(shareWithUser)
      console.log(`✅ Filled user ID field: ${shareWithUser}`)

      await page.waitForTimeout(1000)

      // Select permissions (default to VIEW for test)
      const permissionSelect = page.locator('.q-select').first()
      if (await permissionSelect.isVisible()) {
        await permissionSelect.click()
        await page.waitForTimeout(500)

        // Select "View Only" option
        const viewOnlyOption = page
          .locator('.q-item')
          .filter({hasText: /view.*only/i})
        if (await viewOnlyOption.isVisible()) {
          await viewOnlyOption.click()
          console.log('✅ Selected permission: View Only')
        }
      }

      await page.waitForTimeout(1000)

      // Take screenshot of filled form
      await page.screenshot({
        path: path.join(__dirname, '../screenshots/create-share-filled.png'),
        fullPage: true
      })
      console.log('📸 Screenshot saved: create-share-filled.png')

      // Step 6: Submit the form
      console.log('📝 Step 6: Submitting form...')
      // Look for "Share Wallet" button specifically (not "Create Invoice")
      const createButton = page
        .locator('button')
        .filter({hasText: /^share wallet$/i})
      if (await createButton.isVisible()) {
        await createButton.click()
        console.log('🖱️ Clicked create button')
      }

      // Wait for response
      await page.waitForTimeout(3000)

      // Check if dialog closed (success indicator)
      const dialogStillOpen = await page.locator('.q-dialog').isVisible()
      if (!dialogStillOpen) {
        console.log('🎉 Dialog closed - likely successful!')
      }

      // Step 7: Verify share was created
      console.log('📝 Step 7: Verifying share creation...')

      // Wait for UI to update
      await page.waitForTimeout(2000)

      // Check final count via API
      let finalCount = 0
      if (adminKey) {
        try {
          const finalResponse = await page.request.get(
            `${config.baseUrl}/api/v1/wallet_shares/${walletId}`,
            {
              headers: {'X-Api-Key': adminKey}
            }
          )
          if (finalResponse.ok()) {
            const finalData = await finalResponse.json()
            finalCount = Array.isArray(finalData) ? finalData.length : 0

            // Check if our share is in the list
            if (Array.isArray(finalData)) {
              const ourShare = finalData.find(
                share =>
                  share.user_id === shareWithUser ||
                  share.username === shareWithUser
              )
              if (ourShare) {
                console.log(`✅ Share found in API response!`)
                console.log(`   User: ${ourShare.username || ourShare.user_id}`)
                console.log(`   Permissions: ${ourShare.permissions}`)
                console.log(`   Accepted: ${ourShare.accepted}`)
                success = true
              }
            }
          }
        } catch (error) {
          console.log('⚠️ Could not verify via API:', error.message)
        }
      }

      console.log(`📊 Final share count: ${finalCount}`)
      console.log(`📈 Count change: +${finalCount - initialCount}`)

      // Take final screenshot
      await page.screenshot({
        path: path.join(__dirname, '../screenshots/create-share-result.png'),
        fullPage: true
      })
      console.log('📸 Screenshot saved: create-share-result.png')

      // Check HTTP response status
      if (lastCreateResponse) {
        if (
          lastCreateResponse.status >= 200 &&
          lastCreateResponse.status < 300
        ) {
          console.log(
            `✅ HTTP ${lastCreateResponse.status} - Share created successfully`
          )
          success = true
        } else {
          console.log(
            `❌ HTTP ${lastCreateResponse.status} - Share creation failed`
          )
        }
      }

      if (success) {
        console.log('🎉 SUCCESS! Wallet share created successfully!')
      } else {
        console.log('❌ FAILED: Could not verify share creation')
      }
    } else {
      console.log('❌ Share Wallet button not found')
      await page.screenshot({
        path: path.join(__dirname, '../screenshots/create-share-no-button.png'),
        fullPage: true
      })
    }
  } catch (error) {
    console.error('💥 Error:', error.message)
    await page.screenshot({
      path: path.join(__dirname, '../screenshots/create-share-error.png'),
      fullPage: true
    })
  } finally {
    await browser.close()
  }

  process.exit(success ? 0 : 1)
})()
