const {
  test,
  expect,
  setupIntegration,
  state,
  apiKeyHeaders,
  createWallet,
  decodePayment,
  getWallet,
  jsonRequest,
  textRequest,
  newContext,
  newUserWithUi,
  getAdminSession,
  payInvoiceViaUi,
  topUpWallet,
  ensureExtensionsInstalledViaUi,
  enableExtensionViaUi,
  createNip5Domain,
  createNip5Address,
  activateNip5Address,
  getNostrJson,
  buyNip5Address
} = require('./scenario-helpers')

setupIntegration()

test('010 nostrnip5 domain, search, pricing, and referral flow', async ({
  browser
}) => {
  test.setTimeout(10 * 60 * 1000)

  const admin = await getAdminSession(browser)
  await topUpWallet(state.adminContext, state.adminWallet.walletId, 1_000_000)
  await ensureExtensionsInstalledViaUi(admin, ['nostrnip5', 'lnurlp'])
  const anonymous = await newContext()
  await textRequest(anonymous, 'patch', '/nostrnip5/api/v1/domain/ranking/0', {
    data: 'reserved_a\r\nreserved_b',
    headers: {'content-type': 'text/plain'},
    expected: 401
  })
  await enableExtensionViaUi(admin, 'nostrnip5')
  await enableExtensionViaUi(admin, 'lnurlp')
  await textRequest(
    state.adminContext,
    'patch',
    '/nostrnip5/api/v1/domain/ranking/0',
    {
      data: 'reserved_a\r\nreserved_b',
      headers: {'content-type': 'text/plain'}
    }
  )
  await textRequest(
    state.adminContext,
    'patch',
    '/nostrnip5/api/v1/domain/ranking/200',
    {
      data: 'rank_200_a\r\nrank_200_b\r\nyyy',
      headers: {'content-type': 'text/plain'}
    }
  )
  await textRequest(
    state.adminContext,
    'patch',
    '/nostrnip5/api/v1/domain/ranking/1000',
    {
      data: 'rank_1000_a\r\nrank_1000_b\r\nrank_1000_c\r\nxxx',
      headers: {'content-type': 'text/plain'}
    }
  )
  await jsonRequest(state.adminContext, 'put', '/nostrnip5/api/v1/settings', {
    headers: apiKeyHeaders(state.adminWallet.adminkey),
    data: {
      lnaddress_api_endpoint: state.baseURL,
      lnaddress_api_admin_key: state.adminWallet.adminkey
    }
  })

  const owner = await newUserWithUi(browser, 'nostrnip5-owner')
  await enableExtensionViaUi(owner, 'nostrnip5')
  await enableExtensionViaUi(owner, 'lnurlp')
  await textRequest(
    owner.context,
    'patch',
    '/nostrnip5/api/v1/domain/ranking/0',
    {
      data: 'reserved_a\r\nreserved_b',
      headers: {'content-type': 'text/plain'},
      expected: 403
    }
  )

  const domain = await createNip5Domain(owner.context, owner)
  const domainId = domain.id
  await jsonRequest(
    owner.context,
    'get',
    `/nostrnip5/api/v1/domain/${domainId}`,
    {
      headers: apiKeyHeaders(owner.inkey)
    }
  )

  await jsonRequest(owner.context, 'put', '/nostrnip5/api/v1/domain', {
    headers: apiKeyHeaders(owner.adminkey),
    data: {
      cost: 100,
      cost_extra: {
        char_count_cost: [
          {bracket: '1', amount: '1001'},
          {bracket: '2', amount: '505'},
          {bracket: '3', amount: '202'}
        ],
        max_years: '5',
        promotions: [
          {
            code: 'code_10',
            buyer_discount_percent: '10',
            referer_bonus_percent: '0'
          },
          {
            code: 'code_20',
            buyer_discount_percent: '20',
            referer_bonus_percent: '5'
          },
          {
            code: 'code_alan',
            buyer_discount_percent: '25',
            referer_bonus_percent: '20',
            selected_referer: 'alan'
          }
        ],
        rank_cost: [
          {bracket: 200, amount: '10000'},
          {bracket: 1000, amount: '500'}
        ]
      },
      currency: 'USD',
      domain: domain.domain,
      id: domainId,
      wallet: owner.walletId
    }
  })

  const identifierOne = `one_${Date.now()}`
  const identifierTwo = `two_${Date.now()}`
  const identifierThree = `three_${Date.now()}`
  const address = await createNip5Address(
    owner.context,
    owner,
    domainId,
    identifierOne,
    '04c915daefee38317fa734444acee390a8269fe5810b2241e5e6dd343dfbecc9'
  )
  await getNostrJson(owner.context, domainId, identifierOne, 404)
  await activateNip5Address(owner.context, owner, domainId, address.id)
  let nostrJson = await getNostrJson(owner.context, domainId, identifierOne)
  expect(nostrJson.names[identifierOne]).toBeTruthy()

  await jsonRequest(
    owner.context,
    'put',
    `/nostrnip5/api/v1/domain/${domainId}/address/${address.id}`,
    {
      headers: apiKeyHeaders(owner.adminkey),
      data: {
        pubkey:
          '04c915daefee38317fa734444acee390a8269fe5810b2241e5e6dd343dfbeeee',
        relays: ['wss://relay.nostr.com', 'ws://relay.nostr.org']
      }
    }
  )
  nostrJson = await getNostrJson(owner.context, domainId, identifierOne)
  expect(nostrJson.relays).toBeTruthy()

  const second = await createNip5Address(
    owner.context,
    owner,
    domainId,
    identifierTwo,
    '04c915daefee38317fa734444acee390a8269fe5810b2241e5e6dd343dfaaaaa'
  )
  await activateNip5Address(owner.context, owner, domainId, second.id)
  let addresses = await jsonRequest(
    owner.context,
    'get',
    '/nostrnip5/api/v1/addresses/paginated',
    {
      headers: apiKeyHeaders(owner.inkey),
      params: {
        all_wallets: true,
        limit: 10,
        offset: 0,
        sortby: 'time',
        direction: 'asc'
      }
    }
  )
  expect(JSON.stringify(addresses)).toContain(identifierTwo)

  await jsonRequest(
    owner.context,
    'delete',
    `/nostrnip5/api/v1/domain/${domainId}/address/${address.id}`,
    {
      headers: apiKeyHeaders(owner.adminkey)
    }
  )
  await getNostrJson(owner.context, domainId, identifierOne, 404)

  const alan = await createNip5Address(
    owner.context,
    owner,
    domainId,
    'alan',
    '04c915daefee38317fa734444acee390a8269fe5810b2241e5e6dd343dfaaabb'
  )
  await activateNip5Address(owner.context, owner, domainId, alan.id)
  const alanWallet = await createWallet(owner.context, 'Alan Wallet')
  await jsonRequest(
    owner.context,
    'put',
    `/nostrnip5/api/v1/user/domain/${domainId}/address/${alan.id}/lnaddress`,
    {
      headers: apiKeyHeaders(owner.adminkey),
      data: {wallet: alanWallet.walletId, min: 5, max: '100005'}
    }
  )

  for (const [query, expectedAvailable] of [
    ['a', true],
    ['aa', true],
    ['aaa', true],
    ['aaaa', true],
    [identifierTwo, false],
    ['reserved_a', false],
    ['rank_200_b', true],
    ['rank_1000_b', true],
    ['yyy', true],
    ['xxx', true]
  ]) {
    const result = await jsonRequest(
      owner.context,
      'get',
      `/nostrnip5/api/v1/domain/${domainId}/search`,
      {
        headers: apiKeyHeaders(owner.inkey),
        params: {q: query}
      }
    )
    expect(Boolean(result.available)).toBe(expectedAvailable)
  }

  const client = await newUserWithUi(browser, 'nostrnip5-client')
  await enableExtensionViaUi(client, 'nostrnip5')
  await enableExtensionViaUi(client, 'lnurlp')

  await buyNip5Address(client.context, client, domainId, 'abc1', {
    pubkey: '04c915daefee38317fa734444acee390a8269fe5810b2241e5e6dd343dfaaaaa',
    years: 3
  })
  await buyNip5Address(client.context, client, domainId, 'a1', {
    pubkey: '04c915daefee38317fa734444acee390a8269fe5810b2241e5e6dd343dfaaaaa',
    years: 3
  })
  const cartItems = await jsonRequest(
    client.context,
    'get',
    '/nostrnip5/api/v1/user/addresses',
    {
      headers: apiKeyHeaders(client.inkey),
      params: {active: false}
    }
  )
  expect(JSON.stringify(cartItems)).toContain('abc1')
  expect(JSON.stringify(cartItems)).toContain('a1')

  const priceChecks = [
    ['abc1', 3, null, false, 300.0],
    ['abc1', 5, null, true, 500.0],
    ['abc1', 7, null, false, null, 400],
    ['abc1', 3, 'code_10', true, 270.0],
    ['abc1', 3, 'code_20', false, 240.0],
    ['abc1', 3, 'code_alan', true, 225.0],
    ['xyz', 3, null, false, 606.0],
    ['xyz', 5, null, true, 1010.0],
    ['xyz', 7, null, false, null, 400],
    ['xyz', 3, 'code_10', true, 545.4],
    ['xyz', 3, 'code_20', false, 484.8],
    ['xyz', 3, 'code_alan', true, 454.5]
  ]

  for (const [
    localPart,
    years,
    promoCode,
    createInvoiceFlag,
    expectedPrice,
    expectedStatus
  ] of priceChecks) {
    const result = await buyNip5Address(
      client.context,
      client,
      domainId,
      localPart,
      {
        pubkey:
          '04c915daefee38317fa734444acee390a8269fe5810b2241e5e6dd343dfaaaaa',
        years,
        promo_code: promoCode,
        create_invoice: createInvoiceFlag,
        expected: expectedStatus ?? 201
      }
    )
    if (expectedPrice !== null) {
      expect(result.extra.price).toBeCloseTo(expectedPrice)
    }
    if (createInvoiceFlag && result.payment_request) {
      const decoded = await decodePayment(
        client.context,
        result.payment_request
      )
      expect(Number(result.extra.price_in_sats) * 1000).toBe(
        decoded.amount_msat
      )
    }
  }

  const paidOne = await buyNip5Address(
    client.context,
    client,
    domainId,
    identifierOne,
    {
      pubkey:
        '04c915daefee38317fa734444acee390a8269fe5810b2241e5e6dd343dfaaaab',
      years: 3,
      create_invoice: true
    }
  )
  await payInvoiceViaUi(admin, paidOne.payment_request)
  await getNostrJson(client.context, domainId, identifierOne)

  const quoteThree = await buyNip5Address(
    client.context,
    client,
    domainId,
    identifierThree,
    {
      pubkey:
        '04c915daefee38317fa734444acee390a8269fe5810b2241e5e6dd343dfaaaac',
      years: 5
    }
  )
  expect(quoteThree.extra.price).toBeCloseTo(500.0)
  const paidThree = await buyNip5Address(
    client.context,
    client,
    domainId,
    identifierThree,
    {
      pubkey:
        '04c915daefee38317fa734444acee390a8269fe5810b2241e5e6dd343dfaaaac',
      years: 5,
      promo_code: 'code_alan',
      create_invoice: true
    }
  )
  await payInvoiceViaUi(admin, paidThree.payment_request)
  await getNostrJson(client.context, domainId, identifierThree)

  const refererBonus = Math.floor(quoteThree.extra.price_in_sats / 5)
  await expect
    .poll(
      async () => {
        const alanBalance = await getWallet(owner.context, alanWallet.inkey)
        return Math.abs(Math.floor(alanBalance.balance / 1000) - refererBonus)
      },
      {timeout: 15_000}
    )
    .toBeLessThanOrEqual(100)
})
