window.LNbits = {
  g: window.g,
  utils: window._lnbitsUtils,
  api: window._lnbitsApi,
  map: {
    user(data) {
      const obj = {
        id: data.id,
        username: data.username,
        admin: data.admin,
        email: data.email,
        extensions: data.extensions,
        wallets: data.wallets,
        fiat_providers: data.fiat_providers || [],
        super_user: data.super_user,
        extra: data.extra ?? {}
      }
      const mapWallet = this.wallet
      obj.wallets = obj.wallets.map(mapWallet).sort((a, b) => {
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
      if (newWallet.walletType === 'lightning-shared') {
        const perms = newWallet.sharePermissions
        newWallet.canReceivePayments = perms.includes('receive-payments')
        newWallet.canSendPayments = perms.includes('send-payments')
      }
      newWallet.url = `/wallet?&wal=${data.id}`
      newWallet.storedPaylinks = data.stored_paylinks.links
      return newWallet
    }
  }
}
