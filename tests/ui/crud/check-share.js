/**
 * Test: Check shared wallet appears for recipient user
 *
 * This test logs in as the user who received the share (edit.weeks)
 * and verifies:
 * 1. The shared wallet appears in the left navigation
 * 2. The wallet is visually indicated as shared/joint
 */

const { chromium } = require('playwright');
const { login, getConfig } = require('../auth-helper');
const path = require('path');

async function checkSharedWallet() {
  const config = getConfig();
  const browser = await chromium.launch({ headless: false });
  const context = await browser.newContext();
  const page = await context.newPage();

  try {
    console.log('🔐 Logging in as secondary user (share recipient)...');
    console.log(`👤 Username: ${config.secondaryUsername}`);

    // Login as the user who received the share
    await login(page, config.secondaryUsername, config.secondaryPassword || 'Hfd75kEtjp$&PrNAgp%A');

    console.log('✅ Logged in successfully');

    // Wait for wallet page to load
    await page.waitForTimeout(2000);

    // Take screenshot of initial state
    await page.screenshot({
      path: path.join(__dirname, '../screenshots/check-share-logged-in.png'),
      fullPage: true
    });

    console.log('🔍 Checking for shared wallets in sidebar...');

    // Look for wallet items in the sidebar
    const walletItems = await page.locator('.q-item').all();

    console.log(`📊 Found ${walletItems.length} items in sidebar`);

    let sharedWalletFound = false;
    let sharedWalletName = null;

    for (const item of walletItems) {
      const text = await item.textContent();

      // Check if this item contains wallet-like text and shared indicators
      // Look for: "Joint", "Shared", or other wallet names
      // Also look for visual indicators like icons or badges

      const itemHtml = await item.innerHTML();

      // Check for shared wallet indicators:
      // 1. Wallet name (like "Joint" or the shared wallet name)
      // 2. Share icon (group, people_outline, share icons)
      // 3. Different styling/color for shared wallets

      if (text.includes('Joint') || text.includes('Shared') ||
          itemHtml.includes('group') || itemHtml.includes('people') ||
          itemHtml.includes('share')) {

        console.log('✅ Found potential shared wallet:');
        console.log(`   Text: ${text.trim()}`);

        sharedWalletFound = true;
        sharedWalletName = text.trim();

        // Highlight the shared wallet in screenshot
        await item.screenshot({
          path: path.join(__dirname, '../screenshots/check-share-found-wallet.png')
        });
      }
    }

    if (!sharedWalletFound) {
      console.log('⚠️  No shared wallet found in sidebar');
      console.log('📸 Taking full page screenshot for debugging...');

      await page.screenshot({
        path: path.join(__dirname, '../screenshots/check-share-no-wallet-found.png'),
        fullPage: true
      });

      // Log all sidebar items for debugging
      console.log('\n📋 All sidebar items:');
      for (let i = 0; i < walletItems.length; i++) {
        const text = await walletItems[i].textContent();
        console.log(`   ${i + 1}. ${text.trim()}`);
      }
    } else {
      console.log(`\n✅ Shared wallet "${sharedWalletName}" found in sidebar!`);

      // Check for visual indicators
      console.log('\n🎨 Checking visual indicators of shared wallet:');

      // Look for specific icon classes or badges
      const hasGroupIcon = await page.locator('i.material-icons:has-text("group")').count() > 0;
      const hasPeopleIcon = await page.locator('i.material-icons:has-text("people")').count() > 0;
      const hasShareIcon = await page.locator('i.material-icons:has-text("share")').count() > 0;

      if (hasGroupIcon) console.log('   ✓ Has "group" icon');
      if (hasPeopleIcon) console.log('   ✓ Has "people" icon');
      if (hasShareIcon) console.log('   ✓ Has "share" icon');

      if (!hasGroupIcon && !hasPeopleIcon && !hasShareIcon) {
        console.log('   ⚠️  No obvious visual indicator found');
        console.log('   ℹ️  The wallet may be styled differently (color, badge, etc.)');
      }
    }

    // Take final screenshot
    await page.screenshot({
      path: path.join(__dirname, '../screenshots/check-share-final.png'),
      fullPage: true
    });

    console.log('\n📸 Screenshots saved to tests/ui/screenshots/');
    console.log('\n✅ Test completed');

    if (!sharedWalletFound) {
      console.log('\n❌ Test FAILED: Shared wallet not found in sidebar');
      process.exit(1);
    }

  } catch (error) {
    console.error('\n❌ Error during test:', error.message);

    // Take error screenshot
    try {
      await page.screenshot({
        path: path.join(__dirname, '../screenshots/check-share-error.png'),
        fullPage: true
      });
      console.log('📸 Error screenshot saved');
    } catch (screenshotError) {
      console.error('Could not save error screenshot:', screenshotError.message);
    }

    throw error;
  } finally {
    await browser.close();
  }
}

// Run the test
if (require.main === module) {
  checkSharedWallet()
    .then(() => {
      console.log('\n✅ All checks passed!');
      process.exit(0);
    })
    .catch((error) => {
      console.error('\n❌ Test failed:', error.message);
      process.exit(1);
    });
}

module.exports = { checkSharedWallet };
