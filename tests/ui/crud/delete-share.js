const { chromium } = require('playwright');
const { login, getConfig, getAdminApiKey, getWalletId } = require('../auth-helper');

/**
 * Test: Delete wallet share (revoke access)
 * This test deletes/revokes an existing wallet share
 */

(async () => {
  const browser = await chromium.launch({ headless: true, slowMo: 500 });
  const page = await browser.newPage();
  const config = getConfig();

  let success = false;

  try {
    console.log('🚀 Starting delete wallet share test...');

    // Monitor DELETE requests
    let lastDeleteResponse = null;
    page.on('response', response => {
      if (response.url().includes('/api/v1/wallet_shares/') && response.request().method() === 'DELETE') {
        lastDeleteResponse = { status: response.status(), url: response.url() };
        console.log(`📥 DELETE response: ${response.status()} ${response.url()}`);
      }
    });

    // Step 1: Login as admin
    console.log('📝 Step 1: Logging in as admin...');
    await login(page);

    // Step 2: Navigate to wallet page
    console.log('📝 Step 2: Navigating to wallet page...');
    await page.goto(`${config.baseUrl}/wallet`);
    await page.waitForTimeout(3000);

    // Get wallet ID and API key
    const walletId = await getWalletId(page);
    const adminKey = await getAdminApiKey(page);

    if (!walletId || !adminKey) {
      throw new Error('Could not get wallet ID or admin key');
    }

    console.log(`✅ Using wallet ID: ${walletId}`);

    // Step 3: Get existing shares
    console.log('📝 Step 3: Getting existing shares...');
    const response = await page.request.get(`${config.baseUrl}/api/v1/wallet_shares/${walletId}`, {
      headers: { 'X-Api-Key': adminKey }
    });

    if (!response.ok()) {
      throw new Error(`Failed to get shares: ${response.status()}`);
    }

    const shares = await response.json();
    const initialCount = Array.isArray(shares) ? shares.length : 0;

    console.log(`📊 Initial share count: ${initialCount}`);

    if (initialCount === 0) {
      console.log('⚠️ No shares found to delete. Please create a share first.');
      process.exit(0);
    }

    const shareToDelete = shares[0];
    console.log(`📄 Found share to delete: ${shareToDelete.id}`);
    console.log(`   User: ${shareToDelete.username || shareToDelete.user_id}`);

    // Step 4: Delete share via API
    console.log('📝 Step 4: Deleting share...');

    const deleteResponse = await page.request.delete(
      `${config.baseUrl}/api/v1/wallet_shares/${shareToDelete.id}`,
      {
        headers: { 'X-Api-Key': adminKey }
      }
    );

    if (deleteResponse.ok()) {
      console.log(`✅ Share deleted successfully`);
      success = true;
    } else {
      console.log(`❌ Delete failed: ${deleteResponse.status()}`);
      const errorText = await deleteResponse.text();
      console.log(`   Error: ${errorText}`);
    }

    // Step 5: Verify deletion
    console.log('📝 Step 5: Verifying deletion...');
    await page.waitForTimeout(2000);

    const verifyResponse = await page.request.get(
      `${config.baseUrl}/api/v1/wallet_shares/${walletId}`,
      {
        headers: { 'X-Api-Key': adminKey }
      }
    );

    if (verifyResponse.ok()) {
      const updatedShares = await verifyResponse.json();
      const finalCount = Array.isArray(updatedShares) ? updatedShares.length : 0;

      console.log(`📊 Final share count: ${finalCount}`);
      console.log(`📉 Count change: ${finalCount - initialCount}`);

      // Verify the specific share is gone
      const stillExists = updatedShares.find(s => s.id === shareToDelete.id);

      if (!stillExists && finalCount === initialCount - 1) {
        console.log('✅ Deletion verified - share no longer exists!');
        success = true;
      } else {
        console.log('❌ Deletion verification failed');
        success = false;
      }
    }

    // Step 6: Test UI deletion (optional - if we have more shares)
    if (finalCount > 0) {
      console.log('\n📝 Step 6: Testing UI deletion...');

      // Open Share Wallet dialog
      const shareButton = page.locator('button:has-text("Share Wallet")');
      if (await shareButton.isVisible({ timeout: 5000 })) {
        await shareButton.click();
        await page.waitForTimeout(2000);

        // Take screenshot of shares before deletion
        await page.screenshot({
          path: 'tests/ui/screenshots/delete-share-before.png',
          fullPage: true
        });

        // Look for delete/revoke button (trash icon or similar)
        const deleteButtons = page.locator('button[aria-label="Delete"], button:has(i:has-text("delete")), .q-btn:has(.q-icon:has-text("delete"))');
        const deleteButtonCount = await deleteButtons.count();

        if (deleteButtonCount > 0) {
          console.log(`🗑️  Found ${deleteButtonCount} delete button(s)`);

          // Click the first delete button
          await deleteButtons.first().click();
          await page.waitForTimeout(1000);

          // Handle confirmation dialog if present
          const confirmButton = page.locator('button:has-text("OK"), button:has-text("Confirm"), button:has-text("Yes")');
          if (await confirmButton.isVisible({ timeout: 2000 })) {
            await confirmButton.click();
            console.log('✅ Confirmed deletion');
          }

          await page.waitForTimeout(2000);

          // Take screenshot after UI deletion
          await page.screenshot({
            path: 'tests/ui/screenshots/delete-share-after.png',
            fullPage: true
          });

          console.log('✅ UI deletion test complete');
        } else {
          console.log('⚠️ No delete buttons found in UI');
        }
      }
    }

    // Take final screenshot
    await page.screenshot({
      path: 'tests/ui/screenshots/delete-share-result.png',
      fullPage: true
    });

    if (success) {
      console.log('\n🎉 SUCCESS! Share deleted successfully!');
    }

  } catch (error) {
    console.error('💥 Error:', error.message);
    await page.screenshot({
      path: 'tests/ui/screenshots/delete-share-error.png',
      fullPage: true
    });
  } finally {
    await browser.close();
  }

  process.exit(success ? 0 : 1);
})();
