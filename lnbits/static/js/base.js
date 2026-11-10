window.LNbits = {
  g: window.g,
  utils: window._lnbitsUtils,
  api: window._lnbitsApi,
  map: {
    walletTypes: {
      all: null,
      lightning: ['lightning', 'lightning-shared']
    },
    wallets(wallets, walletType = 'lightning') {
      if (walletType === 'all') return wallets
      const walletTypes = this.walletTypes[walletType]
      return wallets.filter(wallet =>
        walletTypes
          ? walletTypes.includes(wallet.walletType)
          : wallet.walletType === walletType
      )
    },
    walletOptions(wallets) {
      return wallets.map(wallet => {
        return {
          label: [wallet.name, ' - ', wallet.id.substring(0, 5), '...'].join(
            ''
          ),
          value: wallet.id
        }
      })
    },
    user(data) {
      const obj = {
        id: data.id,
        username: data.username,
        admin: data.admin,
        email: data.email,
        extensions: data.extensions,
        fiat_providers: data.fiat_providers || [],
        canCreateFiatWallet: data.can_create_fiat_wallet ?? false,
        super_user: data.super_user,
        extra: data.extra ?? {},
        hasPassword: data.has_password ?? false,
        uiCustomization: data.ui_customization || {}
      }
      const mapWallet = this.wallet
      const sortWallets = (a, b) => {
        if (a.extra.pinned !== b.extra.pinned) {
          return a.extra.pinned ? -1 : 1
        }
        return a.name.localeCompare(b.name)
      }
      obj.wallets = data.wallets.map(mapWallet).sort(sortWallets)
      obj.walletOptions = this.walletOptions(this.wallets(obj.wallets))
      obj.allWalletOptions = this.walletOptions(obj.wallets)
      obj.hiddenWalletsCount = Math.max(
        0,
        obj.wallets.length - data.extra.visible_wallet_count
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
        lightningAddress: data.lightning_address,
        extra: data.extra,
        canReceivePayments: true,
        canSendPayments: data.wallet_type !== 'fiat'
      }
      newWallet.msat = data.balance_msat
      newWallet.sat = Math.floor(data.balance_msat / 1000)
      if (newWallet.walletType === 'lightning-shared') {
        const perms = newWallet.sharePermissions
        newWallet.canReceivePayments = perms.includes('receive-payments')
        newWallet.canSendPayments = perms.includes('send-payments')
      }
      newWallet.url = `/wallet?&wal=${data.id}`
      newWallet.lightningAddressFull = newWallet.lightningAddress
        ? `${newWallet.lightningAddress}@${window.location.host}`
        : null
      newWallet.storedPaylinks = data.stored_paylinks.links
      return newWallet
    }
  }
}
