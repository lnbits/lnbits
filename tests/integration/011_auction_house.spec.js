const {
  test,
  expect,
  setupIntegration,
  state,
  apiKeyHeaders,
  getPayments,
  jsonRequest,
  newUser,
  newUserWithUi,
  getAdminSession,
  payInvoiceViaUi,
  ensureExtensionsInstalledViaUi,
  enableExtensionViaUi,
  createNip5Domain,
  createUserNip5Address,
  activateNip5Address,
  createAuctionRoom,
  updateAuctionRoom,
  createAuctionItem,
  bidOnItem,
  auctionNip5Webhooks
} = require('./scenario-helpers')

setupIntegration()

test('011 auction house transfers NIP5 addresses through bids and fixed-price sale', async ({
  browser
}) => {
  test.setTimeout(10 * 60 * 1000)

  const admin = await getAdminSession(browser)
  await ensureExtensionsInstalledViaUi(admin, [
    'auction_house',
    'nostrnip5',
    'lnurlp'
  ])
  await enableExtensionViaUi(admin, 'nostrnip5')
  await enableExtensionViaUi(admin, 'lnurlp')
  await jsonRequest(state.adminContext, 'put', '/nostrnip5/api/v1/settings', {
    headers: apiKeyHeaders(state.adminWallet.adminkey),
    data: {
      lnaddress_api_endpoint: state.baseURL,
      lnaddress_api_admin_key: state.adminWallet.adminkey
    }
  })

  const owner = await newUserWithUi(browser, 'auction-owner')
  await enableExtensionViaUi(owner, 'auction_house')
  await enableExtensionViaUi(owner, 'nostrnip5')
  await enableExtensionViaUi(owner, 'lnurlp')
  const domain = await createNip5Domain(owner.context, owner, {
    cost_extra: {transfer_secret: '1234'}
  })
  const domainId = domain.id

  await jsonRequest(owner.context, 'put', '/nostrnip5/api/v1/settings', {
    headers: apiKeyHeaders(owner.adminkey),
    data: {
      lnaddress_api_endpoint: state.baseURL,
      lnaddress_api_admin_key: state.adminWallet.adminkey
    }
  })

  const seller = await newUserWithUi(browser, 'auction-seller')
  await enableExtensionViaUi(seller, 'auction_house')
  await enableExtensionViaUi(seller, 'nostrnip5')

  const createdAddresses = []
  for (let index = 1; index <= 10; index++) {
    const address = await createUserNip5Address(
      seller.context,
      seller,
      domainId,
      `id_${index}__${domainId}`
    )
    await activateNip5Address(seller.context, seller, domainId, address.id)
    createdAddresses.push(address)
  }

  const sellRoom = await createAuctionRoom(owner.context, owner, {
    name: 'nip5 sales',
    description: 'Auctions for Nip5',
    fee_wallet_id: owner.walletId,
    currency: 'USD',
    type: 'fixed_price'
  })
  await updateAuctionRoom(owner.context, owner, {
    id: sellRoom.id,
    name: 'nip5 sells',
    description: 'Sells for Nip5',
    currency: 'sat',
    type: 'fixed_price',
    room_percentage: 20,
    fee_wallet_id: owner.walletId,
    is_open_room: true,
    extra: auctionNip5Webhooks(domainId)
  })

  const auctionRoom = await createAuctionRoom(owner.context, owner, {
    name: 'nip5 auctions',
    description: 'Auctions for Nip5',
    fee_wallet_id: owner.walletId,
    currency: 'USD',
    type: 'auction'
  })
  await updateAuctionRoom(owner.context, owner, {
    id: auctionRoom.id,
    name: 'nip5 auctions',
    description: 'Auctions for Nip5',
    currency: 'sat',
    type: 'auction',
    min_bid_up_percentage: 5,
    room_percentage: 10,
    fee_wallet_id: owner.walletId,
    is_open_room: true,
    extra: auctionNip5Webhooks(domainId)
  })

  const sellerAddresses = await jsonRequest(
    seller.context,
    'get',
    '/nostrnip5/api/v1/user/addresses',
    {
      headers: apiKeyHeaders(seller.inkey),
      params: {active: true}
    }
  )
  expect(Array.isArray(sellerAddresses)).toBeTruthy()
  const addressForAuction = createdAddresses[0]
  const transfer = await jsonRequest(
    seller.context,
    'get',
    `/nostrnip5/api/v1/domain/${domainId}/address/${addressForAuction.id}/transfer`,
    {headers: apiKeyHeaders(seller.adminkey)}
  )
  expect(transfer.transfer_code).toBeTruthy()

  const item = await createAuctionItem(seller.context, seller, auctionRoom.id, {
    name: addressForAuction.local_part,
    ask_price: 10.1,
    transfer_code: transfer.transfer_code
  })

  let winningBidder
  for (let index = 1; index <= 15; index++) {
    const bidder = await newUser(`auction-bidder-${index}`)
    const bid = await bidOnItem(
      bidder.context,
      bidder,
      item.id,
      index * 100,
      `bid index: ${index}`
    )
    await payInvoiceViaUi(admin, bid.payment_request)
    winningBidder = bidder
  }

  const itemAfterBids = await jsonRequest(
    owner.context,
    'get',
    `/auction_house/api/v1/items/${item.id}`,
    {
      headers: apiKeyHeaders(owner.inkey)
    }
  )
  expect(itemAfterBids.bids.length).toBeGreaterThanOrEqual(15)
  await getPayments(owner.context, owner.inkey)
  await jsonRequest(
    owner.context,
    'delete',
    `/auction_house/api/v1/items/${item.id}`,
    {
      headers: apiKeyHeaders(owner.adminkey),
      params: {force_close: true}
    }
  )
  const winnerAddresses = await jsonRequest(
    winningBidder.context,
    'get',
    '/nostrnip5/api/v1/user/addresses',
    {
      headers: apiKeyHeaders(winningBidder.inkey),
      params: {active: true}
    }
  )
  expect(JSON.stringify(winnerAddresses)).toContain(
    addressForAuction.local_part
  )

  const fixedPriceAddress = createdAddresses[1]
  const fixedItems = await jsonRequest(
    seller.context,
    'get',
    `/auction_house/api/v1/items/${auctionRoom.id}/paginated`,
    {
      headers: apiKeyHeaders(seller.inkey),
      params: {
        sortby: 'ask_price',
        direction: 'asc',
        name: fixedPriceAddress.local_part
      }
    }
  )
  if (fixedItems.data?.[0]?.id) {
    await jsonRequest(
      seller.context,
      'delete',
      `/auction_house/api/v1/items/${fixedItems.data[0].id}`,
      {
        headers: apiKeyHeaders(seller.adminkey),
        params: {force_close: true}
      }
    )
  }

  const fixedTransfer = await jsonRequest(
    seller.context,
    'get',
    `/nostrnip5/api/v1/domain/${domainId}/address/${fixedPriceAddress.id}/transfer`,
    {headers: apiKeyHeaders(seller.adminkey)}
  )
  const sellItem = await createAuctionItem(
    seller.context,
    seller,
    sellRoom.id,
    {
      name: fixedPriceAddress.local_part,
      ask_price: 5000,
      transfer_code: fixedTransfer.transfer_code
    }
  )
  const buyer = await newUser('auction-buyer')
  const buy = await bidOnItem(
    buyer.context,
    buyer,
    sellItem.id,
    5000,
    'fixed price buy'
  )
  await payInvoiceViaUi(admin, buy.payment_request)
  const buyerAddresses = await jsonRequest(
    buyer.context,
    'get',
    '/nostrnip5/api/v1/user/addresses',
    {
      headers: apiKeyHeaders(buyer.inkey),
      params: {active: true}
    }
  )
  expect(JSON.stringify(buyerAddresses)).toContain(fixedPriceAddress.local_part)
})
