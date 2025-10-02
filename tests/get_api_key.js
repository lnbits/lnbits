/**
 * Helper script to get admin API key and wallet ID
 * Run this after logging in to extract credentials for testing
 */

const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

async function getAdminApiKey(page) {
  try {
    const apiKey = await page.evaluate(() => {
      if (window.app && window.app.g && window.app.g.wallet && window.app.g.wallet.adminkey) {
        return window.app.g.wallet.adminkey;
      }
      const user = localStorage.getItem('lnbits.user');
      if (user) {
        const userData = JSON.parse(user);
        if (userData.wallets && userData.wallets.length > 0) {
          return userData.wallets[0].adminkey;
        }
      }
      return null;
    });
    return apiKey;
  } catch (error) {
    return null;
  }
}

async function getWalletId(page) {
  try {
    const walletId = await page.evaluate(() => {
      if (window.app && window.app.g && window.app.g.wallet && window.app.g.wallet.id) {
        return window.app.g.wallet.id;
      }
      const user = localStorage.getItem('lnbits.user');
      if (user) {
        const userData = JSON.parse(user);
        if (userData.wallets && userData.wallets.length > 0) {
          return userData.wallets[0].id;
        }
      }
      return null;
    });
    return walletId;
  } catch (error) {
    return null;
  }
}

module.exports = { getAdminApiKey, getWalletId };

// If run directly
if (require.main === module) {
  (async () => {
    // Load config
    const envPath = path.join(__dirname, '../.env.local');
    let config = { baseUrl: 'http://localhost:5001', username: 'admin', password: '' };

    if (fs.existsSync(envPath)) {
      const content = fs.readFileSync(envPath, 'utf-8');
      content.split('\n').forEach(line => {
        if (line && !line.startsWith('#') && line.includes('=')) {
          const [key, value] = line.split('=');
          if (key.trim() === 'TEST_LNBITS_URL') config.baseUrl = value.trim();
          if (key.trim() === 'LNBITS_ADMIN_USERNAME') config.username = value.trim();
          if (key.trim() === 'LNBITS_ADMIN_PASSWORD') config.password = value.trim();
        }
      });
    }

    const browser = await chromium.launch({ headless: false });
    const page = await browser.newPage();

    console.log('🔐 Getting API credentials...');
    console.log(`📍 URL: ${config.baseUrl}`);
    console.log(`👤 User: ${config.username}`);

    // Navigate and login
    await page.goto(config.baseUrl);
    await page.waitForTimeout(2000);

    // Check if need to switch to login
    const createAccountVisible = await page.locator('text=Create Account').first().isVisible();
    if (createAccountVisible) {
      await page.click('text=Login');
      await page.waitForTimeout(2000);
    }

    // Login
    await page.fill('input[type="text"], input[type="email"]', config.username);
    await page.fill('input[type="password"]', config.password);
    await page.click('button:has-text("LOGIN")');
    await page.waitForTimeout(3000);

    // Navigate to wallet
    await page.goto(`${config.baseUrl}/wallet`);
    await page.waitForTimeout(2000);

    // Get credentials
    const adminKey = await getAdminApiKey(page);
    const walletId = await getWalletId(page);

    console.log('\n📋 Credentials:');
    console.log(`Admin API Key: ${adminKey || 'NOT FOUND'}`);
    console.log(`Wallet ID: ${walletId || 'NOT FOUND'}`);

    if (adminKey && walletId) {
      console.log('\n✅ Add these to .env.local:');
      console.log(`TEST_ADMIN_API_KEY=${adminKey}`);
      console.log(`TEST_WALLET_ID=${walletId}`);
    } else {
      console.log('\n❌ Could not extract credentials');
    }

    await browser.close();
  })();
}
