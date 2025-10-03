/**
 * Test: Check wallet icons for shared wallets
 *
 * This test logs in as edit.weeks and verifies that shared wallet icons appear
 */

const {chromium, firefox} = require('playwright')
const {login, getConfig} = require('../auth-helper')
const path = require('path')

async function checkWalletIcons() {
  const config = getConfig()

  // Support browser selection via env var: BROWSER=firefox node check-wallet-icons.js
  const browserType = process.env.BROWSER || 'chromium'
  const browserEngine = browserType === 'firefox' ? firefox : chromium

  console.log(`🌐 Launching ${browserType} browser...`)
  const browser = await browserEngine.launch({headless: false})
  const context = await browser.newContext()
  const page = await context.newPage()

  // Listen to console messages
  page.on('console', msg => {
    console.log(`Browser console: ${msg.text()}`)
  })

  try {
    console.log('🔐 Logging in as secondary user (has shared wallets)...')
    console.log(`👤 Username: ${config.secondaryUsername}`)

    // Login as the user who has shared wallets
    await login(
      page,
      config.secondaryUsername,
      config.secondaryPassword || 'Hfd75kEtjp$&PrNAgp%A'
    )

    console.log('✅ Logged in successfully')

    // Wait for page to load
    await page.waitForTimeout(3000)

    // Take screenshot of wallet list
    await page.screenshot({
      path: path.join(__dirname, '../screenshots/wallet-icons-full.png'),
      fullPage: true
    })

    console.log('📸 Full page screenshot saved')

    // Check wallet list in left sidebar
    const walletList = page.locator('.lnbits-drawer__q-list .q-item')
    const walletCount = await walletList.count()
    console.log(`📊 Found ${walletCount} wallet items`)

    // Check each wallet for shared icon
    for (let i = 0; i < walletCount; i++) {
      const wallet = walletList.nth(i)
      const nameEl = wallet.locator('.q-item__label span.ellipsis')
      const name = await nameEl.textContent()

      // Look for group icon
      const groupIcon = wallet.locator('i.material-icons:text("group")')
      const hasIcon = (await groupIcon.count()) > 0

      console.log(
        `Wallet "${name}": ${hasIcon ? '✅ HAS' : '❌ NO'} shared icon`
      )

      // Take screenshot of individual wallet item
      await wallet.screenshot({
        path: path.join(
          __dirname,
          `../screenshots/wallet-${i}-${name.replace(/[^a-zA-Z0-9]/g, '-')}.png`
        )
      })
    }

    // Execute JavaScript to check the data
    const walletData = await page.evaluate(() => {
      if (!window.g || !window.g.user || !window.g.user.wallets) {
        return {error: 'g.user.wallets not available'}
      }
      return window.g.user.wallets.map(w => ({
        name: w.name,
        is_shared: w.is_shared,
        hasOwnProperty: w.hasOwnProperty('is_shared')
      }))
    })

    console.log('\n📊 Wallet data from JavaScript:')
    console.log(JSON.stringify(walletData, null, 2))

    // Keep browser open for manual inspection
    console.log('\n⏸️  Browser will remain open for manual inspection...')
    console.log('Press Ctrl+C to close')
    await page.waitForTimeout(300000) // 5 minutes
  } catch (error) {
    console.error('❌ Error during test:', error.message)
    await page.screenshot({
      path: path.join(__dirname, '../screenshots/wallet-icons-error.png'),
      fullPage: true
    })
    console.log('📸 Error screenshot saved')
    throw error
  } finally {
    await browser.close()
  }
}

checkWalletIcons()
  .then(() => {
    console.log('\n✅ Test completed')
    process.exit(0)
  })
  .catch(error => {
    console.error('\n❌ Test failed:', error.message)
    process.exit(1)
  })
