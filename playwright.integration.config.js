const {defineConfig} = require('@playwright/test')

const port = process.env.PORT || '5000'
const baseURL = process.env.LNBITS_BASE_URL || `http://127.0.0.1:${port}`

module.exports = defineConfig({
  testDir: './tests/integration',
  testMatch: '**/*.spec.js',
  timeout: 120_000,
  globalTimeout: 60 * 60 * 1000,
  fullyParallel: false,
  workers: 1,
  reporter: [
    ['list'],
    ['html', {outputFolder: 'playwright-report/integration', open: 'never'}]
  ],
  use: {
    baseURL,
    extraHTTPHeaders: {
      Accept: 'application/json, text/plain, */*'
    }
  },
  webServer: process.env.LNBITS_SKIP_WEB_SERVER
    ? undefined
    : {
        command: 'node tests/integration/server.cjs',
        url: baseURL,
        timeout: 180_000,
        reuseExistingServer: !process.env.CI
      }
})
