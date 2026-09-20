const assert = require('node:assert/strict')
const {readFileSync} = require('node:fs')
const {resolve} = require('node:path')
const {chromium} = require('@playwright/test')
const root = resolve(__dirname, '../..')
const assets = resolve(root, 'lnbits/onchain/static')

async function main() {
  const browser = await chromium.launch({
    headless: true,
    ...(process.env.CHROME_PATH
      ? {executablePath: process.env.CHROME_PATH}
      : {})
  })
  try {
    const page = await browser.newPage({viewport: {width: 1280, height: 1000}})
    await page.clock.install()
    const sockets = new Map()
    await page.routeWebSocket(
      'wss://wallet.test/blockexplorer/api/v1/**',
      ws => {
        const path = new URL(ws.url()).pathname
        sockets.set(path, ws)
        ws.onClose(() => {
          if (sockets.get(path) === ws) sockets.delete(path)
        })
      }
    )
    const errors = []
    page.on('pageerror', e => {
      errors.push(e.message)
      console.error(e.message)
    })
    page.on('console', msg => {
      if (msg.type() === 'warning') console.error(msg.text())
    })
    page.setDefaultTimeout(10000)
    await page.route('https://wallet.test/**', async route => {
      const url = new URL(route.request().url())
      if (url.pathname.startsWith('/onchain/static/')) {
        return route.fulfill({
          body: readFileSync(
            assets + url.pathname.slice('/onchain/static'.length)
          ),
          contentType: 'application/javascript'
        })
      }
      return route.fulfill({
        body: '<html><body></body></html>',
        contentType: 'text/html'
      })
    })
    await page.goto('https://wallet.test/')
    await page.setContent(
      '<!doctype html>' +
        readFileSync(assets + '/wallet.vue', 'utf8') +
        [
          'lnbits-wallet-extra',
          'lnbits-wallet-charts',
          'lnbits-wallet-api-docs'
        ]
          .map(name =>
            readFileSync(
              root + '/lnbits/templates/components/' + name + '.vue',
              'utf8'
            )
          )
          .join('') +
        '<div id="app" class="q-pa-md"><page-onchain ref="page" @synced="onSynced"><template #wallet-tools><lnbits-wallet-extra :chart-config="chartConfig"></lnbits-wallet-extra><lnbits-wallet-charts ref="charts" :chart-config="chartConfig" :payment-filter="onchainPaymentFilter" api-url="/onchain/api/v1/stats/daily" api-key="read-test"></lnbits-wallet-charts></template></page-onchain></div>'
    )
    for (const script of [
      'vue/dist/vue.global.js',
      'quasar/dist/quasar.umd.prod.js',
      'underscore/underscore.js',
      'moment/moment.js'
    ]) {
      await page.addScriptTag({path: root + '/node_modules/' + script})
    }
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
      window.fixtureWallets = []
      window.fixtureAddresses = []
      window.calls = []
      window.notifications = []
      window.fixtureState = null
      const config = {
        isLoaded: true,
        network: 'Testnet4',
        explorer_provider: 'lnbits',
        lnbits_explorer_network: 'Testnet4',
        explorer_url: '/blockexplorer',
        mempool_endpoint: 'https://mempool.space',
        sats_denominated: true
      }
      window.LNbits = {
        api: {
          async request(method, path, key, payload, options) {
            calls.push({method, path, payload, options})
            if (path.endsWith('/stats/daily'))
              return {
                data: [
                  {
                    date: '2026-09-19',
                    balance: 100000,
                    balance_in: 100000,
                    balance_out: 0,
                    count_in: 1,
                    count_out: 0,
                    fee: 0
                  }
                ]
              }
            if (path.startsWith('/api/v1/rate/')) return {data: {price: 80000}}
            if (path.endsWith('/fees'))
              return {data: {halfHourFee: 2, fastestFee: 5, hourFee: 1}}
            if (path.endsWith('/hex')) return {data: 'previous-tx'}
            if (path.endsWith('/sync')) return {data: {scheduled: true}}
            if (path.endsWith('/state'))
              return {
                data: fixtureState || {
                  addresses: fixtureAddresses,
                  snapshots: [],
                  scanning: false,
                  checked_at: 0,
                  balance_sat: 0
                }
              }
            if (path.endsWith('/hot-wallet/status'))
              return {data: {available: true}}
            if (path.endsWith('/config')) {
              if (method === 'PUT') {
                Object.assign(config, payload)
                config.explorer_url =
                  config.explorer_provider === 'lnbits'
                    ? '/blockexplorer'
                    : config.mempool_endpoint
              }
              return {data: {...config}}
            }
            if (path === '/onchain/api/v1/hot-wallet') {
              const wallet = {
                id: 'hot' + (fixtureWallets.length + 1),
                title: payload.title,
                wallet_kind: 'hot',
                type: 'p2wpkh',
                network: 'Testnet4',
                meta: '{"accountPath":"m/84\'/1\'/0\'"}',
                masterpub: 'test-public-descriptor',
                fingerprint: '00000001',
                address_no: -1,
                backup_confirmed: false
              }
              fixtureWallets.push(wallet)
              fixtureAddresses.push(
                {
                  id: wallet.id + '-receive',
                  wallet: wallet.id,
                  address:
                    wallet.id === 'hot1'
                      ? 'tb1qtestreceive'
                      : 'tb1qreceive' + wallet.id,
                  amount: 0,
                  branch_index: 0,
                  address_index: 0,
                  has_activity: false
                },
                {
                  id: wallet.id + '-change',
                  wallet: wallet.id,
                  address:
                    wallet.id === 'hot1'
                      ? 'tb1qtestchange'
                      : 'tb1qchange' + wallet.id,
                  amount: 0,
                  branch_index: 1,
                  address_index: 0,
                  has_activity: false
                }
              )
              return {data: {...wallet}}
            }
            if (path.includes('/backup/confirm')) {
              fixtureWallets[0].backup_confirmed = true
              return {data: fixtureWallets[0]}
            }
            if (path.endsWith('/backup'))
              return {
                data: {mnemonic: Array(23).fill('abandon').join(' ') + ' art'}
              }
            if (path.includes('/wallet?'))
              return {data: fixtureWallets.map(w => ({...w}))}
            if (path.includes('/addresses/'))
              return {
                data: fixtureAddresses
                  .filter(a => path.endsWith('/' + a.wallet))
                  .map(a => ({...a}))
              }
            if (path.includes('/address/') && method === 'GET')
              return {data: fixtureAddresses[0]}
            if (path.includes('/address/') && method === 'PUT') {
              const a = fixtureAddresses.find(a => path.endsWith(a.id))
              Object.assign(a, payload)
              return {data: a}
            }
            if (path.endsWith('/psbt')) return {data: 'test-unsigned-psbt'}
            if (path.endsWith('/sign'))
              return {
                data: {
                  tx_hex: 'test-signed-hex',
                  tx_json: JSON.stringify({
                    outputs: payload.transaction.outputs,
                    fee: payload.max_fee_sat
                  })
                }
              }
            if (path.endsWith('/tx')) return {data: 'broadcast-id'}
            throw new Error('Unexpected request: ' + path)
          }
        },
        utils: {
          loadScript: path =>
            new Promise((resolve, reject) => {
              const s = document.createElement('script')
              s.src = path
              s.onload = resolve
              s.onerror = reject
              document.head.append(s)
            }),
          formatCurrency: (value, currency) =>
            new Intl.NumberFormat('en-US', {
              style: 'currency',
              currency: currency || 'USD'
            }).format(value),
          formatSat: value => Number(value).toLocaleString('en-US'),
          notifyApiError: error => notifications.push(error.message),
          confirmDialog: message =>
            Quasar.Dialog.create({message, cancel: true}),
          exportCSV() {}
        }
      }
      LNbits.g = {wallet: {inkey: 'read-test'}}
      window.app = Vue.createApp({
        data: () => ({
          onchainPaymentFilter: {},
          chartConfig: {
            showBalanceChart: true,
            showBalanceInOutChart: true,
            showPaymentInOutChart: true
          },
          syncEvents: 0
        }),
        methods: {
          onSynced() {
            this.syncEvents++
            this.$refs.charts?.changeCharts()
          }
        }
      })
      app.use(Quasar)
      app.mixin({
        computed: {
          utils() {
            return LNbits.utils
          },
          baseUrl() {
            return window.location.origin + '/'
          },
          g() {
            return {
              user: {wallets: [{adminkey: 'admin-test', inkey: 'read-test'}]},
              wallet: {
                id: 'core-wallet',
                adminkey: 'admin-test',
                inkey: 'read-test',
                currency: 'USD',
                walletType: 'onchain',
                name: 'Bitcoin wallet',
                extra: {
                  icon: 'currency_bitcoin',
                  color: 'primary',
                  pinned: false
                },
                sat: 100000
              },
              exchangeRate: 80000,
              fiatTracking: true,
              isFiatPriority: false,
              allowedCurrencies: [],
              currencies: ['USD', 'EUR'],
              isSatsDenomination: true,
              settings: {enableWalletLightningAddresses: false}
            }
          }
        },
        methods: {
          copyText(text) {
            window.lastCopied = text
          }
        }
      })
      app.config.globalProperties.$t = key =>
        key.split('.').pop().replaceAll('_', ' ')
      for (const name of [
        'lnbits-wallet-icon',
        'lnbits-wallet-paylinks',
        'lnbits-wallet-share'
      ])
        app.component(name, {template: '<span></span>'})
      app.component('lnbits-qrcode', {
        props: ['value'],
        template: '<div data-testid="qr">{{ value }}</div>'
      })
    })
    await page.addScriptTag({path: root + '/lnbits/static/vendor/chart.umd.js'})
    for (const name of [
      'lnbits-wallet-extra',
      'lnbits-wallet-charts',
      'lnbits-wallet-api-docs'
    ]) {
      await page.addScriptTag({
        path: root + '/lnbits/static/js/components/' + name + '.js'
      })
    }
    await page.route('https://mempool.space/**', route => {
      const path = new URL(route.request().url()).pathname
      return route.fulfill({
        body: path.endsWith('/hex')
          ? 'previous-tx'
          : JSON.stringify({halfHourFee: 2, fastestFee: 5, hourFee: 1}),
        contentType: 'application/json'
      })
    })
    await page.evaluate(async () => {
      const definition = (await import('/onchain/static/wallet.js')).default
      app.component('page-onchain', definition)
      window.vm = app.mount('#app')
    })
    await page
      .getByRole('button', {name: 'Serial device', exact: true})
      .first()
      .waitFor()
    // Settings must remain usable throughout a background scan.
    await page.evaluate(() => {
      vm.$refs.page.liveUpdates.stop()
      vm.$refs.page.scan.scanning = true
    })
    await page.getByRole('button', {name: 'Onchain settings'}).click()
    assert.equal(await page.getByLabel('mempool endpoint').count(), 0)
    await page.getByLabel('Block explorer', {exact: true}).click()
    await page.getByRole('option', {name: 'Mempool', exact: true}).click()
    const endpoint = page.getByLabel('mempool endpoint', {exact: true})
    await endpoint.fill('https://example.com/testnet4')
    await page.getByRole('button', {name: 'update', exact: true}).click()
    await page.getByRole('button', {name: 'Onchain settings'}).click()
    assert.equal(await endpoint.inputValue(), 'https://example.com/testnet4')
    await page.getByLabel('Block explorer', {exact: true}).click()
    await page
      .getByRole('option', {name: 'LNbits block explorer', exact: true})
      .click()
    await page.getByRole('button', {name: 'update', exact: true}).click()
    await page.getByRole('button', {name: 'Set up wallet', exact: true}).click()
    await page.getByText('Server wallet', {exact: true}).click()
    await page.getByLabel('Wallet name', {exact: true}).fill('Everyday bitcoin')
    await page
      .getByRole('button', {name: 'Create wallet', exact: true})
      .last()
      .click()
    await page
      .getByRole('heading', {name: 'Back up Everyday bitcoin'})
      .waitFor()
    assert.equal(await page.locator('.onchain-word').count(), 24)
    assert.equal(
      await page.locator('.onchain-word').first().textContent(),
      '••••••'
    )
    await page.getByRole('button', {name: 'Show words', exact: true}).click()
    await page.getByRole('button', {name: 'Hide words', exact: true}).waitFor()
    assert.equal(
      await page.locator('.onchain-word').last().textContent(),
      'art'
    )
    await page.getByRole('button', {name: 'Hide words', exact: true}).click()
    assert.equal(
      await page.locator('.onchain-word').last().textContent(),
      '••••••'
    )
    for (const width of [1280, 390]) {
      await page.setViewportSize({width, height: 1000})
      await page.clock.runFor(500)
      for (const dark of [false, true]) {
        await page.evaluate(value => Quasar.Dark.set(value), dark)
        await page.screenshot({
          path: `/tmp/onchain-backup-${width}-${dark ? 'dark' : 'light'}.png`
        })
        assert.equal(
          await page.evaluate(
            () => document.documentElement.scrollWidth <= innerWidth
          ),
          true
        )
      }
    }
    await page.getByRole('button', {name: 'I have written it down'}).click()
    assert.equal(await page.locator('.onchain-word').count(), 0)
    await page
      .getByRole('button', {name: 'Confirm backup', exact: true})
      .click()
    await page
      .getByRole('alert')
      .getByText('One or more words are incorrect.', {exact: false})
      .waitFor()
    assert.equal(
      await page.evaluate(
        () => calls.filter(c => c.path.endsWith('/backup/confirm')).length
      ),
      0
    )
    const wordInputs = page.getByLabel(/^Word \d+$/)
    assert.equal(await wordInputs.count(), 4)
    for (const input of await wordInputs.all()) {
      const label = await input.getAttribute('aria-label')
      await input.fill(label === 'Word 24' ? 'art' : 'abandon')
    }
    await page.screenshot({path: '/tmp/onchain-backup-verify.png'})
    await page
      .getByRole('button', {name: 'Confirm backup', exact: true})
      .click()
    await page
      .getByRole('heading', {name: 'Back up Everyday bitcoin'})
      .waitFor({state: 'hidden'})
    await page.setViewportSize({width: 1280, height: 1000})
    assert.equal(
      await page.getByRole('button', {name: 'Send', exact: true}).isDisabled(),
      true
    )
    await page.evaluate(() => {
      vm.$refs.page.scan.scanning = true
    })
    await page.getByRole('button', {name: 'Receive', exact: true}).click()
    await page.getByLabel('Amount in sats (optional)').fill('12345')
    await page.getByRole('button', {name: 'Copy payment link'}).click()
    assert.equal(
      await page.evaluate(() => lastCopied),
      'bitcoin:tb1qtestreceive?amount=0.00012345'
    )
    await page.getByRole('button', {name: 'close', exact: true}).last().click()
    await page.evaluate(() => {
      const p = vm.$refs.page
      p.addresses[0].amount = 100000
      p.utxos.data = [
        {
          wallet: 'hot1',
          address: 'tb1qtestreceive',
          amount: 100000,
          txId: 'a'.repeat(64),
          vout: 0,
          addressIndex: 0,
          accountType: 'p2wpkh',
          accountPath: "m/84'/1'/0'",
          selected: false,
          confirmed: true
        }
      ]
      p.lastSynced = '12:00'
      fixtureState = {
        addresses: fixtureAddresses.map(a => ({
          ...a,
          amount: a.branch_index === 0 ? 100000 : 0
        })),
        snapshots: [],
        scanning: true,
        checked_at: 100,
        balance_sat: 100000
      }
      p.scan.scanning = true
      p.syncError = true
      p.liveUpdates.stop()
    })
    assert.equal(await page.evaluate(() => vm.$refs.page.scan.scanning), true)
    // A failed earlier scan must not lock operations using the cached coins.
    await page.getByText('Advanced', {exact: true}).click()
    await page.getByRole('button', {name: 'Import signed PSBT'}).click()
    await page.getByLabel('signed psbt', {exact: true}).waitFor()
    await page.keyboard.press('Escape')
    await page
      .getByLabel('signed psbt', {exact: true})
      .waitFor({state: 'hidden'})
    await page.getByRole('button', {name: 'Cancel', exact: true}).click()
    await page.getByText('Advanced', {exact: true}).click()
    await page.getByRole('button', {name: 'Send', exact: true}).click()
    await page
      .getByLabel('Bitcoin address or payment link', {exact: true})
      .fill('tb1qrecipient')
    await page.getByLabel('amount sats', {exact: true}).fill('25000')
    await page.evaluate(async () => {
      await vm.$refs.page.hydrateState()
    })
    const draft = await page.evaluate(() => {
      const payment = vm.$refs.page.$refs.paymentRef
      return {
        address: payment.sendToList[0].address,
        amount: payment.sendToList[0].amount,
        selected: payment.selectedAmount,
        change: payment.changeAddress.address
      }
    })
    assert.deepEqual(draft, {
      address: 'tb1qrecipient',
      amount: 25000,
      selected: 100000,
      change: 'tb1qtestchange'
    })

    await page
      .getByRole('button', {name: 'Review payment', exact: true})
      .click()
    await page
      .getByRole('heading', {name: 'Review payment', exact: true})
      .waitFor()
    await page.getByText('Change back to your wallet', {exact: true}).waitFor()
    assert.ok(
      await page.getByRole('button', {name: 'Confirm and send'}).isEnabled()
    )
    assert.equal(
      await page.evaluate(
        () => calls.filter(c => c.path.endsWith('/tx')).length
      ),
      0
    )
    await page.getByRole('button', {name: 'Confirm and send'}).click()
    await page
      .getByText('Payment broadcast successfully.', {exact: false})
      .waitFor()
    assert.equal(
      await page.evaluate(
        () => calls.filter(c => c.path.endsWith('/tx')).length
      ),
      1
    )
    assert.equal(
      await page.evaluate(
        () => calls.find(c => c.path.endsWith('/tx')).payload.network
      ),
      'Testnet4'
    )
    await page.evaluate(() => {
      const p = vm.$refs.page
      p.scan.scanning = true
      p.history = [
        {
          address: 'tb1qtestreceive',
          txId: 'existing-payment',
          received: true,
          amount: 100000,
          confirmed: false
        }
      ]
    })
    await page
      .getByRole('link', {name: 'View transaction existing-payment'})
      .waitFor()
    assert.equal(
      await page
        .getByRole('button', {name: 'Set up wallet', exact: true})
        .count(),
      0
    )
    assert.equal(
      await page.getByRole('button', {name: 'Add wallet', exact: true}).count(),
      0
    )
    await page.evaluate(() => vm.$refs.page.$refs.walletList.openSetup())
    assert.equal(
      await page
        .getByRole('heading', {name: 'Set up your onchain wallet'})
        .count(),
      0
    )
    assert.equal(await page.evaluate(() => fixtureWallets.length), 1)
    await page.evaluate(() => {
      const p = vm.$refs.page
      // Live updates are paused so the synthetic activity stays stable.
      p.activityNow = Date.now()
      p.history = [
        {
          address: 'tb1qtestreceive',
          txId: 'existing-payment',
          received: true,
          amount: 100000,
          confirmed: true,
          timestamp: undefined,
          date: moment().subtract(8, 'days').format('LLL')
        },
        {
          address: 'tb1qtestreceive',
          txId: 'b'.repeat(64),
          outputAddresses: ['tb1qrecipient' + 'a'.repeat(30), 'tb1qtestchange'],
          sent: true,
          amount: 25000,
          confirmed: true,
          height: 101,
          timestamp: Math.floor(Date.now() / 1000) - 3600
        },
        {
          address: 'tb1qtestreceive',
          txId: 'c'.repeat(64),
          received: true,
          amount: 1200,
          confirmed: false,
          firstSeen: Math.floor(Date.now() / 1000) - 5
        }
      ]
    })
    await page
      .getByRole('link', {name: 'View transaction ' + 'b'.repeat(64)})
      .waitFor()
    await page.getByLabel('Search transactions', {exact: true}).fill('-25000')
    assert.equal(
      await page.locator('.onchain-activity-table tbody tr').count(),
      1
    )
    await page.getByLabel('Search transactions', {exact: true}).fill('')
    await page.getByText('a few seconds ago', {exact: true}).waitFor()
    await page.getByText('8 days ago', {exact: true}).waitFor()
    const recipient = page.getByRole('link', {
      name: 'View address tb1qrecipient' + 'a'.repeat(30)
    })
    await recipient.waitFor()
    assert.ok(
      (await recipient.getAttribute('href')).endsWith(
        '/address/tb1qrecipient' + 'a'.repeat(30)
      )
    )
    assert.equal(
      await page
        .getByRole('link', {name: 'View address tb1qtestchange', exact: true})
        .count(),
      0
    )

    for (const width of [1280, 390]) {
      await page.setViewportSize({width, height: 1000})
      await page.clock.runFor(500)
      for (const dark of [false, true]) {
        await page.evaluate(dark => Quasar.Dark.set(dark), dark)
        const overflow = await page.evaluate(
          () => document.documentElement.scrollWidth > innerWidth
        )
        if (overflow)
          console.log(
            await page.evaluate(() =>
              [...document.querySelectorAll('body *')]
                .filter(e => e.getBoundingClientRect().right > innerWidth + 1)
                .slice(0, 12)
                .map(e => ({
                  tag: e.tagName,
                  cls: e.className,
                  text: e.textContent.slice(0, 80),
                  width: e.getBoundingClientRect().width
                }))
            )
          )
        await page.screenshot({
          path: `/tmp/onchain-wallet-${width}-${dark ? 'dark' : 'light'}.png`,
          fullPage: true
        })
        assert.equal(overflow, false, `Page overflow at ${width}px`)
      }
    }
    await page.evaluate(async () => {
      const p = vm.$refs.page
      const address = {...fixtureAddresses[0], amount: 100000}
      const duplicate = {...address, id: 'duplicate', branch_index: 1}
      const tx = {
        txid: 'd'.repeat(64),
        vin: [{prevout: null}],
        vout: [{value: 100000, scriptpubkey_address: address.address}],
        status: {confirmed: true, block_time: 1700000000},
        first_seen: 1700000000
      }
      const coin = {txid: tx.txid, vout: 0, value: 100000, status: tx.status}
      fixtureState = {
        addresses: [address, duplicate],
        snapshots: [address, duplicate].map(a => ({
          address_id: a.id,
          transactions: [tx],
          utxos: [coin],
          checked_at: 1
        })),
        balance_sat: 100000,
        scanning: false
      }
      await p.hydrateState()
    })
    assert.deepEqual(
      await page.evaluate(() => ({
        balance: vm.$refs.page.selectedBalance,
        coins: vm.$refs.page.selectedUtxos.length,
        amount: vm.$refs.page.activity[0].amount
      })),
      {balance: 100000, coins: 1, amount: 100000}
    )
    await page.clock.runFor(2000)
    const chartCount = () =>
      page.evaluate(
        () => calls.filter(c => c.path.endsWith('/stats/daily')).length
      )
    const stateCount = () =>
      page.evaluate(() => calls.filter(c => c.path.endsWith('/state')).length)
    const chartBefore = await chartCount()
    const eventsBefore = await page.evaluate(() => vm.syncEvents)
    await page.evaluate(async () => {
      for (let i = 0; i < 3; i++) {
        fixtureState.snapshots.forEach(s => s.checked_at++)
        vm.$refs.page.activityNow += 15000
        await vm.$refs.page.hydrateState()
      }
    })
    await page.clock.runFor(5000)
    assert.equal(
      await chartCount(),
      chartBefore,
      'unchanged scans and relative-date renders must not refetch charts'
    )
    assert.equal(await page.evaluate(() => vm.syncEvents), eventsBefore)
    await page.evaluate(() => {
      const p = vm.$refs.page
      p.liveUpdates = Vue.markRaw(
        new p.liveUpdates.constructor(p.liveUpdates.options)
      )
      p.liveUpdates.start()
    })
    const stateBefore = await stateCount()
    await page.clock.runFor(59000)
    assert.equal(await stateCount(), stateBefore, 'no fast idle polling')
    await page.clock.runFor(1000)
    assert.equal(
      await stateCount(),
      stateBefore + 1,
      'one-minute fallback refresh'
    )
    await page.clock.runFor(2000)
    assert.equal(await chartCount(), chartBefore)
    assert.ok(sockets.has('/blockexplorer/api/v1/ws/blocks'))
    assert.ok([...sockets.keys()].some(path => path.includes('/ws/address/')))
    const scansBefore = await page.evaluate(
      () => calls.filter(c => c.path.endsWith('/sync')).length
    )
    const blocks = sockets.get('/blockexplorer/api/v1/ws/blocks')
    blocks.send(JSON.stringify({height: 100}))
    blocks.send(JSON.stringify({height: 101}))
    await page.waitForFunction(
      () => vm.$refs.page.liveUpdates.eventTimer !== null
    )
    await page.clock.runFor(1000)
    assert.equal(
      await page.evaluate(
        () => calls.filter(c => c.path.endsWith('/sync')).length
      ),
      scansBefore + 1
    )
    blocks.send(JSON.stringify({height: 101}))
    await page.clock.runFor(1000)
    assert.equal(
      await page.evaluate(
        () => calls.filter(c => c.path.endsWith('/sync')).length
      ),
      scansBefore + 1
    )
    assert.deepEqual(errors, [])
    console.log(
      'PASS: browser onboarding, backup, receive URI, fee-aware send review, single-wallet setup, background scanning and retained history, and mobile/light/dark layout'
    )
  } finally {
    await browser.close()
  }
}
main().catch(error => {
  console.error(error)
  process.exitCode = 1
})
