import {defineConfig} from '@playwright/test'
import {resolve} from 'node:path'

const appBaseUrl = process.env.LNBITS_E2E_BASE_URL ?? 'http://127.0.0.1:5009'
const e2eDir = __dirname
const isCi = Boolean(process.env.CI)
const projectRoot = resolve(e2eDir, '../..')
const reportRoot = resolve(projectRoot, 'test-reports')
const configuredWorkers = Number.parseInt(
  process.env.PLAYWRIGHT_WORKERS ?? '',
  10
)

export default defineConfig({
  testDir: e2eDir,
  testMatch: '**/*.spec.ts',
  outputDir: resolve(reportRoot, 'test-results'),
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
    ? [
        ['github'],
        [
          'html',
          {
            open: 'never',
            outputFolder: resolve(reportRoot, 'playwright-report')
          }
        ]
      ]
    : [
        ['list'],
        [
          'html',
          {
            open: 'never',
            outputFolder: resolve(reportRoot, 'playwright-report')
          }
        ]
      ],
  use: {
    baseURL: appBaseUrl,
    browserName: 'chromium',
    headless: true,
    viewport: {
      width: 1280,
      height: 900
    },
    trace: 'off',
    screenshot: 'only-on-failure',
    video: 'off'
  },
  webServer: {
    command: 'node ./tests/e2e/start-lnbits-server.cjs',
    cwd: projectRoot,
    url: appBaseUrl,
    reuseExistingServer: false,
    timeout: 180_000
  }
})
