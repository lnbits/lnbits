import {defineConfig} from '@playwright/test'

const appBaseUrl = process.env.LNBITS_E2E_BASE_URL ?? 'http://127.0.0.1:5009'
const isCi = Boolean(process.env.CI)
const configuredWorkers = Number.parseInt(
  process.env.PLAYWRIGHT_WORKERS ?? '',
  10
)

export default defineConfig({
  testDir: './tests/e2e',
  testMatch: '**/*.spec.ts',
  timeout: 600_000,
  fullyParallel: false,
  forbidOnly: isCi,
  retries: isCi ? 1 : 0,
  workers:
    Number.isInteger(configuredWorkers) && configuredWorkers > 0
      ? configuredWorkers
      : 1,
  expect: {
    timeout: 15_000
  },
  reporter: isCi
    ? [['github'], ['html', {open: 'never'}]]
    : [['list'], ['html', {open: 'never'}]],
  use: {
    baseURL: appBaseUrl,
    browserName: 'chromium',
    headless: true,
    viewport: {
      width: 1280,
      height: 900
    },
    trace: isCi ? 'on-first-retry' : 'retain-on-failure',
    screenshot: 'on',
    video: 'retain-on-failure'
  },
  webServer: {
    command: 'node ./tests/e2e/start-lnbits-server.cjs',
    url: appBaseUrl,
    reuseExistingServer: false,
    timeout: 180_000
  }
})
