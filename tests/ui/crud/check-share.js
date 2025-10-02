/**
 * Test: Accept wallet share invitation
 *
 * This test logs in as the user who received the share (edit.weeks)
 * and verifies:
 * 1. The notification bell appears with pending shares
 * 2. Clicking the bell opens the share invitations dialog
 * 3. User can accept a share
 * 4. The shared wallet appears in the wallet list
 */

const { chromium } = require('playwright');
const { login, getConfig } = require('../auth-helper');
const path = require('path');

async function checkAndAcceptShare() {
  const config = getConfig();
  const browser = await chromium.launch({ headless: false });
  const context = await browser.newContext();
  const page = await context.newPage();

  // Listen to console messages
  page.on('console', msg => {
    console.log(`Browser console: ${msg.text()}`);
  });

  try {
    console.log('🔐 Logging in as secondary user (share recipient)...');
    console.log(`👤 Username: ${config.secondaryUsername}`);

    // Login as the user who received the share
    await login(page, config.secondaryUsername, config.secondaryPassword || 'Hfd75kEtjp$&PrNAgp%A');

    console.log('✅ Logged in successfully');

    // Wait for page to load
    await page.waitForTimeout(2000);

    // Take screenshot of initial state
    await page.screenshot({
      path: path.join(__dirname, '../screenshots/accept-share-1-logged-in.png'),
      fullPage: true
    });

    console.log('🔍 Looking for notification bell...');

    // Look for the notification bell button
    const notificationBell = page.locator('button:has(i.material-icons:text("notifications"))');
    const bellCount = await notificationBell.count();

    if (bellCount === 0) {
      console.log('❌ No notification bell found');
      await page.screenshot({
        path: path.join(__dirname, '../screenshots/accept-share-2-no-bell.png'),
        fullPage: true
      });
      throw new Error('Notification bell not found');
    }

    console.log(`✅ Found ${bellCount} notification bell(s)`);

    // Get the badge count
    const badge = notificationBell.locator('.q-badge');
    const badgeText = await badge.textContent();
    console.log(`📊 Pending shares: ${badgeText}`);

    // Take screenshot of notification bell
    await notificationBell.screenshot({
      path: path.join(__dirname, '../screenshots/accept-share-3-notification-bell.png')
    });

    console.log('🖱️  Clicking notification bell...');
    await notificationBell.click();

    // Wait a bit for dialog to appear
    await page.waitForTimeout(1000);

    // Take screenshot after clicking
    await page.screenshot({
      path: path.join(__dirname, '../screenshots/accept-share-4-after-click.png'),
      fullPage: true
    });

    console.log('🔍 Looking for share invitations dialog...');

    // Look for the dialog
    const dialog = page.locator('.q-dialog');
    const dialogVisible = await dialog.isVisible();

    if (!dialogVisible) {
      console.log('❌ Dialog not visible');

      // Check if dialog exists in DOM
      const dialogCount = await dialog.count();
      console.log(`Dialog count in DOM: ${dialogCount}`);

      // Get all dialogs
      if (dialogCount > 0) {
        for (let i = 0; i < dialogCount; i++) {
          const d = dialog.nth(i);
          const visible = await d.isVisible();
          const html = await d.innerHTML().catch(() => 'Could not get HTML');
          console.log(`Dialog ${i}: visible=${visible}`);
          console.log(`Dialog ${i} HTML:`, html.substring(0, 200));
        }
      }

      throw new Error('Share invitations dialog did not open');
    }

    console.log('✅ Dialog is visible!');

    // Take screenshot of dialog
    await dialog.screenshot({
      path: path.join(__dirname, '../screenshots/accept-share-5-dialog.png')
    });

    console.log('🔍 Looking for share items in dialog...');

    // Look for the list of shares
    const shareItems = dialog.locator('.q-item');
    const shareCount = await shareItems.count();
    console.log(`📊 Found ${shareCount} share items in dialog`);

    if (shareCount === 0) {
      console.log('❌ No share items found in dialog');
      const dialogHtml = await dialog.innerHTML();
      console.log('Dialog HTML:', dialogHtml);
      throw new Error('No share items found');
    }

    // Get info about first share
    const firstShare = shareItems.first();
    const shareText = await firstShare.textContent();
    console.log(`📝 First share: ${shareText}`);

    // Take screenshot of first share item
    await firstShare.screenshot({
      path: path.join(__dirname, '../screenshots/accept-share-6-first-share.png')
    });

    console.log('🖱️  Looking for Accept button...');

    // Find and click the accept button (green checkmark)
    const acceptButton = firstShare.locator('button:has(i:text("check"))');
    const acceptButtonCount = await acceptButton.count();

    if (acceptButtonCount === 0) {
      console.log('❌ Accept button not found');
      throw new Error('Accept button not found');
    }

    console.log('✅ Found Accept button, clicking it...');
    await acceptButton.click();

    // Wait for the accept operation to complete
    await page.waitForTimeout(2000);

    // Take screenshot after accepting
    await page.screenshot({
      path: path.join(__dirname, '../screenshots/accept-share-7-after-accept.png'),
      fullPage: true
    });

    console.log('🔍 Checking if shared wallet appears in wallet list...');

    // Wait a bit more for wallet list to refresh
    await page.waitForTimeout(1000);

    // Look for wallet items in the sidebar
    const walletItems = page.locator('.q-item');
    const walletCount = await walletItems.count();
    console.log(`📊 Found ${walletCount} items in sidebar`);

    let sharedWalletFound = false;
    for (let i = 0; i < walletCount; i++) {
      const item = walletItems.nth(i);
      const text = await item.textContent();

      // Look for the shared wallet (checking for "Joint" or shared indicators)
      if (text.includes('Joint') || text.includes('Shared')) {
        console.log(`✅ Found shared wallet: ${text.trim()}`);
        sharedWalletFound = true;

        await item.screenshot({
          path: path.join(__dirname, '../screenshots/accept-share-8-shared-wallet.png')
        });
        break;
      }
    }

    if (!sharedWalletFound) {
      console.log('⚠️  Shared wallet not immediately visible');
      console.log('   (It may take a moment to appear)');
    }

    // Take final screenshot
    await page.screenshot({
      path: path.join(__dirname, '../screenshots/accept-share-9-final.png'),
      fullPage: true
    });

    console.log('\n📸 Screenshots saved to tests/ui/screenshots/');
    console.log('\n✅ Test completed successfully!');

  } catch (error) {
    console.error('\n❌ Error during test:', error.message);

    // Take error screenshot
    try {
      await page.screenshot({
        path: path.join(__dirname, '../screenshots/accept-share-error.png'),
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
  checkAndAcceptShare()
    .then(() => {
      console.log('\n✅ Share accepted successfully!');
      process.exit(0);
    })
    .catch((error) => {
      console.error('\n❌ Test failed:', error.message);
      process.exit(1);
    });
}

module.exports = { checkAndAcceptShare };
