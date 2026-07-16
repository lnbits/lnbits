const {
  test,
  expect,
  setupIntegration,
  apiKeyHeaders,
  clearMirror,
  getPayments,
  jsonRequest,
  mirrorUrl,
  pageStatus,
  pollWalletBalance,
  newUserWithUi,
  getAdminSession,
  payInvoiceViaUi,
  ensureExtensionsInstalledViaUi,
  enableExtensionViaUi
} = require('./scenario-helpers')

setupIntegration()

test('006 watchonly, satspay, and tipjar scenario', async ({browser}) => {
  test.setTimeout(7 * 60 * 1000)
  await clearMirror()

  const admin = await getAdminSession(browser)
  await ensureExtensionsInstalledViaUi(admin, [
    'watchonly',
    'satspay',
    'tipjar'
  ])
  const user = await newUserWithUi(browser, 'watchonly-satspay-tipjar')
  await enableExtensionViaUi(user, 'watchonly')
  await pageStatus(user.context, `/watchonly/?usr=${user.userId}`)
  await jsonRequest(user.context, 'get', '/watchonly/api/v1/config', {
    headers: apiKeyHeaders(user.inkey)
  })
  await jsonRequest(user.context, 'get', '/watchonly/api/v1/wallet', {
    headers: apiKeyHeaders(user.inkey),
    params: {network: 'Mainnet'}
  })
  const onchain = await jsonRequest(
    user.context,
    'post',
    '/watchonly/api/v1/wallet',
    {
      headers: apiKeyHeaders(user.adminkey),
      data: {
        title: 'segwit',
        masterpub:
          'zpub6rsRjqj6BTbD9DjqrY4p14tUx5kdA8ZGCTJD99wZTxD5wfvCkyXKrK3s7M3B1eFN6NbRhmbDDRDC8LF3Bn5gmxxN9rF8mDpZsGC6isGrK1g',
        network: 'Mainnet',
        meta: '{"accountPath":"m/84\'/0\'/0\'"}'
      },
      expected: [200, 201]
    }
  )
  expect(onchain.id).toBeTruthy()
  await jsonRequest(
    user.context,
    'get',
    `/watchonly/api/v1/addresses/${onchain.id}`,
    {
      headers: apiKeyHeaders(user.inkey)
    }
  )
  await jsonRequest(
    user.context,
    'get',
    `/watchonly/api/v1/address/${onchain.id}`,
    {
      headers: apiKeyHeaders(user.inkey)
    }
  )

  await enableExtensionViaUi(user, 'satspay')
  await pageStatus(user.context, '/satspay/')
  await jsonRequest(user.context, 'get', '/satspay/api/v1/charges', {
    headers: apiKeyHeaders(user.adminkey)
  })
  const onchainCharge = await jsonRequest(
    user.context,
    'post',
    '/satspay/api/v1/charge',
    {
      headers: apiKeyHeaders(user.adminkey),
      data: {
        onchain: true,
        onchainwallet: onchain.id,
        lnbits: false,
        description: 'Onchain Charge',
        time: 1111,
        amount: 1111,
        lnbitswallet: null
      },
      expected: [200, 201]
    }
  )
  expect(onchainCharge.id).toBeTruthy()

  await jsonRequest(user.context, 'post', '/satspay/api/v1/charge', {
    headers: apiKeyHeaders(user.adminkey),
    data: {
      onchain: false,
      onchainwallet: null,
      lnbits: true,
      description: 'lightning charge - to expire',
      time: 1,
      amount: 10,
      lnbitswallet: user.walletId,
      webhook: 'https://google.com',
      completelink: 'https://twitter.com',
      completelinktext: 'Have Fun'
    },
    expected: [200, 201]
  })

  let expectedBalanceSats = 0
  for (let index = 1; index <= 5; index++) {
    const amount = 9 + index
    const charge = await jsonRequest(
      user.context,
      'post',
      '/satspay/api/v1/charge',
      {
        headers: apiKeyHeaders(user.adminkey),
        data: {
          onchain: false,
          onchainwallet: null,
          lnbits: true,
          description: `lightning charge [${index}]`,
          time: 1220,
          amount,
          lnbitswallet: user.walletId,
          webhook: mirrorUrl(),
          completelink: 'https://twitter.com',
          completelinktext: 'Have Fun'
        },
        expected: [200, 201]
      }
    )
    expect(charge.payment_request).toBeTruthy()
    await pageStatus(user.context, `/satspay/${charge.id}`)
    await jsonRequest(
      user.context,
      'get',
      `/satspay/api/v1/charge/balance/${charge.id}`,
      {
        headers: apiKeyHeaders(user.inkey)
      }
    )
    await payInvoiceViaUi(admin, charge.payment_request)
    await expect
      .poll(async () => {
        const updatedCharge = await jsonRequest(
          user.context,
          'get',
          `/satspay/api/v1/charge/${charge.id}`,
          {
            headers: apiKeyHeaders(user.inkey)
          }
        )
        return Boolean(updatedCharge.paid || updatedCharge.lnbitswallet)
      })
      .toBeTruthy()
    expectedBalanceSats += amount
  }

  await pollWalletBalance(user.context, user.inkey, expectedBalanceSats * 1000)
  const charges = await jsonRequest(
    user.context,
    'get',
    '/satspay/api/v1/charges',
    {
      headers: apiKeyHeaders(user.adminkey)
    }
  )
  expect(charges.length).toBeGreaterThanOrEqual(7)
  const payments = await getPayments(user.context, user.inkey)
  expect(payments.length).toBeGreaterThanOrEqual(6)

  await enableExtensionViaUi(user, 'tipjar')
  await pageStatus(user.context, `/tipjar/?usr=${user.userId}`)
  await jsonRequest(user.context, 'get', '/tipjar/api/v1/tipjars', {
    headers: apiKeyHeaders(user.inkey)
  })
  const tipjar = await jsonRequest(
    user.context,
    'post',
    '/tipjar/api/v1/tipjars',
    {
      headers: apiKeyHeaders(user.adminkey),
      data: {wallet: user.walletId, name: 'Nakamoto', webhook: mirrorUrl()},
      expected: [200, 201]
    }
  )
  expect(tipjar.id).toBeTruthy()
  await pageStatus(user.context, `/tipjar/${tipjar.id}`)

  for (let index = 1; index <= 5; index++) {
    const tip = await jsonRequest(user.context, 'post', '/tipjar/api/v1/tips', {
      headers: apiKeyHeaders(user.adminkey),
      data: {
        tipjar: tipjar.id,
        name: 'Hal',
        sats: 21,
        message: `Let's go ...${index}!`
      },
      expected: [200, 201]
    })
    expect(tip.redirect_url).toBeTruthy()
    const tipChargeId = tip.redirect_url.split('/').filter(Boolean).at(-1)
    const charge = await jsonRequest(
      user.context,
      'get',
      `/satspay/api/v1/charge/${tipChargeId}`,
      {
        headers: apiKeyHeaders(user.inkey)
      }
    )
    expect(charge.description).toBe(`Let's go ...${index}!`)
    const tips = await jsonRequest(user.context, 'get', '/tipjar/api/v1/tips', {
      headers: apiKeyHeaders(user.inkey)
    })
    expect(tips.length).toBe(index)
    await payInvoiceViaUi(admin, tip.payment_request || charge.payment_request)
    expectedBalanceSats += 21
    await pollWalletBalance(
      user.context,
      user.inkey,
      expectedBalanceSats * 1000
    )
  }
})
