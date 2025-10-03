const {chromium} = require('playwright')
const path = require('path')
const {login, getConfig} = require('../auth-helper')

/**
 * Test: Create wallet via UI
 * This test creates a new wallet using the UI to ensure user has a wallet for other tests
 */

;(async () => {
  const browser = await chromium.launch({headless: true, slowMo: 500})
  const page = await browser.newPage()
  const config = getConfig()

  let success = false

  try {
    console.log('🚀 Starting create wallet UI test...')

    // Step 1: Login as admin
    console.log('📝 Step 1: Logging in as admin...')
    await login(page)

    // Step 2: Check if user already has a wallet (UI only)
    console.log('📝 Step 2: Checking for existing wallets in UI...')
    await page.goto(`${config.baseUrl}/wallet`)
    await page.waitForTimeout(2000)

    // Count wallet items in the UI sidebar (excluding "Add a new wallet" button)
    const walletItems = await page
      .locator('.q-drawer .q-list .q-item')
      .filter({hasNot: page.locator('text=Add a new wallet')})
      .count()
    console.log(`📊 Wallet items visible in UI: ${walletItems}`)

    if (walletItems > 0) {
      console.log(`✅ User already has ${walletItems} wallet(s)`)
      success = true
    } else {
      // Step 3: Create wallet via UI
      console.log('📝 Step 3: Creating wallet via UI...')

      // Click "Add a new wallet" button
      const addWalletButton = page.locator('text=Add a new wallet')
      if (await addWalletButton.isVisible({timeout: 5000})) {
        await addWalletButton.click()
        console.log('🖱️  Clicked "Add a new wallet"')
        await page.waitForTimeout(1000)

        // Fill in wallet name
        const walletNameInput = page
          .locator('input[type="text"]')
          .filter({hasText: /name/i})
          .or(page.locator('input[placeholder*="name" i]'))
          .or(page.locator('.q-dialog input[type="text"]'))
          .first()

        if (await walletNameInput.isVisible({timeout: 3000})) {
          const testWalletName = `Test Wallet ${Date.now()}`
          await walletNameInput.fill(testWalletName)
          console.log(`📝 Entered wallet name: ${testWalletName}`)
          await page.waitForTimeout(500)
        } else {
          console.log('⚠️  Wallet name input not found, trying without it')
        }

        // Click create/submit button
        const createButton = page
          .locator('.q-dialog button')
          .filter({hasText: /create|add|submit|ok/i})
          .first()

        if (await createButton.isVisible({timeout: 3000})) {
          await createButton.click()
          console.log('🖱️  Clicked create button')
          await page.waitForTimeout(2000)
        }

        // Verify wallet was created by checking UI
        await page.reload()
        await page.waitForTimeout(2000)

        const finalWalletItems = await page
          .locator('.q-drawer .q-list .q-item')
          .filter({hasNot: page.locator('text=Add a new wallet')})
          .count()

        console.log(`📊 Final wallet count: ${finalWalletItems}`)
        console.log(`📈 Count change: +${finalWalletItems - walletItems}`)

        if (finalWalletItems > walletItems) {
          console.log('✅ Wallet created successfully!')
          success = true
        } else {
          console.log('❌ Wallet creation verification failed')
        }
      } else {
        console.log('❌ "Add a new wallet" button not found')
      }
    }

    // Take screenshot
    await page.screenshot({
      path: path.join(__dirname, '../screenshots/create-wallet-result.png'),
      fullPage: true
    })

    if (success) {
      console.log('🎉 SUCCESS! User has a wallet!')
    }
  } catch (error) {
    console.error('💥 Error:', error.message)
    await page.screenshot({
      path: path.join(__dirname, '../screenshots/create-wallet-error.png'),
      fullPage: true
    })
  } finally {
    await browser.close()
  }

  process.exit(success ? 0 : 1)
})()
