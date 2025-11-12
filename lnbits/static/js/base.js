window.LNbits = {
  g: window.g,
  utils: window._lnbitsUtils,
  api: window._lnbitsApi,
  events: {
    onInvoicePaid(wallet, cb) {
      ws = new WebSocket(`${websocketUrl}/${wallet.inkey}`)
      ws.onmessage = ev => {
        const data = JSON.parse(ev.data)
        if (data.payment) {
          cb(data)
        }
      }
      return ws.onclose
    }
  },
  map: {
    user(data) {
      const obj = {
        id: data.id,
        admin: data.admin,
        email: data.email,
        extensions: data.extensions,
        wallets: data.wallets,
        fiat_providers: data.fiat_providers || [],
        super_user: data.super_user,
        extra: data.extra ?? {}
      }
      const mapWallet = this.wallet
      obj.wallets = obj.wallets
        .map(obj => {
          return mapWallet(obj)
        })
        .sort((a, b) => {
          if (a.extra.pinned !== b.extra.pinned) {
            return a.extra.pinned ? -1 : 1
          }
          return a.name.localeCompare(b.name)
        })
      obj.walletOptions = obj.wallets.map(obj => {
        return {
          label: [obj.name, ' - ', obj.id.substring(0, 5), '...'].join(''),
          value: obj.id
        }
      })
      obj.hiddenWalletsCount = Math.max(
        0,
        data.wallets.length - data.extra.visible_wallet_count
      )
      obj.walletInvitesCount = data.extra.wallet_invite_requests?.length || 0
      return obj
    },
    wallet(data) {
      newWallet = {
        id: data.id,
        name: data.name,
        walletType: data.wallet_type,
        sharePermissions: data.share_permissions,
        sharedWalletId: data.shared_wallet_id,
        adminkey: data.adminkey,
        inkey: data.inkey,
        currency: data.currency,
        extra: data.extra,
        canReceivePayments: true,
        canSendPayments: true
      }
      newWallet.msat = data.balance_msat
      newWallet.sat = Math.floor(data.balance_msat / 1000)
      newWallet.fsat = new Intl.NumberFormat(window.LOCALE).format(
        newWallet.sat
      )
      if (newWallet.walletType === 'lightning-shared') {
        const perms = newWallet.sharePermissions
        newWallet.canReceivePayments = perms.includes('receive-payments')
        newWallet.canSendPayments = perms.includes('send-payments')
      }
      newWallet.url = `/wallet?&wal=${data.id}`
      return newWallet
    },
    payment(data) {
      obj = {
        checking_id: data.checking_id,
        status: data.status,
        amount: data.amount,
        fee: data.fee,
        memo: data.memo,
        time: data.time,
        bolt11: data.bolt11,
        preimage: data.preimage,
        payment_hash: data.payment_hash,
        expiry: data.expiry,
        extra: data.extra ?? {},
        wallet_id: data.wallet_id,
        webhook: data.webhook,
        webhook_status: data.webhook_status,
        fiat_amount: data.fiat_amount,
        fiat_currency: data.fiat_currency
      }

      obj.date = moment.utc(data.created_at).local().format(window.dateFormat)
      obj.dateFrom = moment.utc(data.created_at).local().fromNow()

      obj.expirydate = moment.utc(obj.expiry).local().format(window.dateFormat)
      obj.expirydateFrom = moment.utc(obj.expiry).local().fromNow()
      obj.msat = obj.amount
      obj.sat = obj.msat / 1000
      obj.tag = obj.extra?.tag
      obj.fsat = new Intl.NumberFormat(window.LOCALE).format(obj.sat)
      obj.isIn = obj.amount > 0
      obj.isOut = obj.amount < 0
      obj.isPending = obj.status === 'pending'
      obj.isPaid = obj.status === 'success'
      obj.isFailed = obj.status === 'failed'
      obj._q = [obj.memo, obj.sat].join(' ').toLowerCase()
      try {
        obj.details = JSON.parse(data.extra?.details || '{}')
      } catch {
        obj.details = {extraDetails: data.extra?.details}
      }
      return obj
    }
  }
}
