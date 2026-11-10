// Standalone component smoke test: node tests/e2e/admin-onchain.cjs
const assert = require('node:assert/strict')
const {readFileSync} = require('node:fs')
const {resolve} = require('node:path')
const {chromium} = require('@playwright/test')
const root = resolve(__dirname, '../..')

async function main() {
  const browser = await chromium.launch({
    headless: true,
    ...(process.env.CHROME_PATH
      ? {executablePath: process.env.CHROME_PATH}
      : {})
  })
  try {
    const page = await browser.newPage({viewport: {width: 1100, height: 1000}})
    const errors = []
    page.on('pageerror', error => errors.push(error.message))
    await page.route('https://admin.test/**', route =>
      route.fulfill({
        body: '<html><body></body></html>',
        contentType: 'text/html'
      })
    )
    await page.goto('https://admin.test/')
    await page.setContent(
      readFileSync(
        root + '/lnbits/templates/components/admin/server.vue',
        'utf8'
      ) +
        '<div id="app" class="q-pa-md"><q-card flat bordered class="q-pa-md"><lnbits-admin-server ref="payments" :form-data="formData" :is-super-user="superUser"></lnbits-admin-server></q-card></div>'
    )
    await page.addScriptTag({
      path: root + '/node_modules/vue/dist/vue.global.js'
    })
    await page.addScriptTag({
      path: root + '/node_modules/quasar/dist/quasar.umd.prod.js'
    })
    await page.addStyleTag({
      path: root + '/node_modules/quasar/dist/quasar.prod.css'
    })
    await page.addStyleTag({
      content:
        "@font-face {font-family: 'Material Icons'; src: url(data:font/woff2;base64," +
        readFileSync(
          root + '/lnbits/static/fonts/material-icons-v50.woff2'
        ).toString('base64') +
        ") format('woff2')} .material-icons {font-family: 'Material Icons'; font-weight: normal; font-style: normal; letter-spacing: normal; text-transform: none; white-space: nowrap; word-wrap: normal; direction: ltr; -webkit-font-feature-settings: 'liga'; -webkit-font-smoothing: antialiased;}"
    })
    await page.evaluate(() => {
      window.localisation = {}
    })
    await page.addScriptTag({path: root + '/lnbits/static/i18n/en.js'})
    await page.evaluate(() => {
      window.statusFixture = {configured: false, backup_confirmed: false}
      window.calls = []
      window.LNbits = {
        api: {
          async request(method, path, apiKey, body, options) {
            if (options.headers['X-Api-Key'] !== 'test-admin-key')
              throw new Error('Missing authorization')
            calls.push({method, path})
            if (method === 'GET') return {data: {...statusFixture}}
            if (path.endsWith('/backup'))
              return {
                data: {
                  version: 1,
                  key: 'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=',
                  fingerprint: 'test-fingerprint'
                }
              }
            if (path.endsWith('/confirm')) {
              if (
                options.headers['X-Onchain-Key-Fingerprint'] !==
                'test-fingerprint'
              )
                throw new Error('Wrong fingerprint')
              statusFixture.backup_confirmed = true
            } else {
              statusFixture = {
                configured: true,
                backup_confirmed: false,
                fingerprint: 'test-fingerprint',
                source: 'file'
              }
            }
            return {data: {...statusFixture}}
          }
        },
        utils: {
          notifyApiError(error) {
            throw error
          }
        }
      }
      window.app = Vue.createApp({
        data: () => ({
          formData: {lnbits_allow_onchain_payments: false},
          superUser: false
        })
      })
      app.use(Quasar)
      app.mixin({
        computed: {
          g() {
            return {
              user: {wallets: [{adminkey: 'test-admin-key'}]},
              currencies: [],
              allowedCurrencies: []
            }
          }
        },
        methods: {
          $t(key) {
            return window.localisation.en[key] || key
          }
        }
      })
    })
    await page.addScriptTag({
      path: root + '/lnbits/static/js/components/admin/lnbits-admin-server.js'
    })
    await page.evaluate(() => {
      window.vm = app.mount('#app')
    })
    // The admin page loads the user's role asynchronously, after mounting.
    await page.evaluate(() => {
      vm.superUser = true
    })
    const toggle = page.getByRole('switch', {name: 'Allow onchain payments'})
    await page.getByRole('button', {name: 'Generate encryption key'}).waitFor()
    assert.equal(await toggle.getAttribute('aria-disabled'), 'true')
    await page.getByRole('button', {name: 'Generate encryption key'}).click()
    const downloadEvent = page.waitForEvent('download')
    await page.getByRole('button', {name: 'Download key backup'}).click()
    const download = await downloadEvent
    assert.equal(download.suggestedFilename(), 'lnbits-onchain-key.json')
    await page
      .getByRole('checkbox', {
        name: 'I have stored this key backup somewhere safe'
      })
      .click()
    await page.getByRole('button', {name: 'Confirm backup'}).click()
    await page
      .getByRole('button', {name: 'Confirm backup'})
      .waitFor({state: 'hidden'})
    await toggle.click()
    assert.equal(
      await page.evaluate(() => vm.formData.lnbits_allow_onchain_payments),
      true
    )
    await page.evaluate(async () => {
      statusFixture = {
        configured: false,
        backup_confirmed: false,
        fingerprint: 'test-fingerprint',
        error: 'Restore the original key'
      }
      await vm.$refs.payments.loadOnchainStatus()
    })
    await page.getByText('Restore an encryption key', {exact: true}).click()
    await page.locator('input[type=file]').setInputFiles({
      name: 'lnbits-onchain-key.json',
      mimeType: 'application/json',
      buffer: Buffer.from(
        JSON.stringify({
          version: 1,
          key: 'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA='
        })
      )
    })
    await page.getByRole('button', {name: 'Restore key', exact: true}).click()
    await page
      .getByRole('button', {name: 'Back up encryption key', exact: true})
      .waitFor()
    for (const width of [390, 1100]) {
      await page.setViewportSize({width, height: 1000})
      for (const dark of [true, false]) {
        await page.evaluate(value => Quasar.Dark.set(value), dark)
        await page.screenshot({
          path: `/tmp/onchain-settings-${width}-${dark ? 'dark' : 'light'}.png`,
          fullPage: true
        })
        assert.equal(
          await page.evaluate(
            () => document.documentElement.scrollWidth <= innerWidth
          ),
          true
        )
      }
    }
    await page.evaluate(() => {
      vm.superUser = false
    })
    await page
      .getByText(
        'The super user manages onchain payments and encryption key backups.'
      )
      .waitFor()
    assert.equal(await toggle.getAttribute('aria-disabled'), 'true')
    assert.deepEqual(errors, [])
    console.log(
      'Payments settings: generation, download, confirmation, toggle, restore, permissions and responsive layouts passed.'
    )
  } finally {
    await browser.close()
  }
}
main().catch(error => {
  console.error(error)
  process.exitCode = 1
})
