Vue.component(VueQrcode.name, VueQrcode)

Vue.filter('reverse', function (value) {
  // slice to make a copy of array, then reverse the copy
  return value.slice().reverse()
})

new Vue({
  el: '#vue',
  mixins: [windowMixin],
  data: function () {
    return {
      DUST_LIMIT: 546,
      filter: '',

      scan: {
        scanning: false,
        scanCount: 0,
        scanIndex: 0
      },

      currentAddress: null,

      tab: 'addresses',

      config: {
        data: {
          mempool_endpoint: 'https://mempool.space',
          receive_gap_limit: 20,
          change_gap_limit: 5
        },
        DEFAULT_RECEIVE_GAP_LIMIT: 20,
        show: false
      },

      formDialog: {
        show: false,
        data: {}
      },

      qrCodeDialog: {
        show: false,
        data: null
      },
      ...tables,
      ...tableData
    }
  },

  methods: {
    //################### CONFIG ###################
    getConfig: async function () {
      try {
        const {data} = await LNbits.api.request(
          'GET',
          '/watchonly/api/v1/config',
          this.g.user.wallets[0].adminkey
        )
        this.config.data = data
      } catch (error) {
        LNbits.utils.notifyApiError(error)
      }
    },
    updateConfig: async function () {
      const wallet = this.g.user.wallets[0]
      try {
        await LNbits.api.request(
          'PUT',
          '/watchonly/api/v1/config',
          wallet.adminkey,
          this.config.data
        )
        this.config.show = false
      } catch (error) {
        LNbits.utils.notifyApiError(error)
      }
    },

    //################### WALLETS ###################
    getWalletName: function (walletId) {
      const wallet = this.walletAccounts.find(wl => wl.id === walletId)
      return wallet ? wallet.title : 'unknown'
    },
    addWalletAccount: async function () {
      const wallet = this.g.user.wallets[0]
      const data = _.omit(this.formDialog.data, 'wallet')
      await this.createWalletAccount(wallet, data)
    },
    createWalletAccount: async function (wallet, data) {
      try {
        const response = await LNbits.api.request(
          'POST',
          '/watchonly/api/v1/wallet',
          wallet.adminkey,
          data
        )
        this.walletAccounts.push(mapWalletAccount(response.data))
        this.formDialog.show = false

        await this.refreshWalletAccounts()
        await this.refreshAddresses()

        if (!this.payment.changeWallett) {
          this.payment.changeWallet = this.walletAccounts[0]
          this.selectChangeAddress(this.payment.changeWallet)
        }
      } catch (error) {
        LNbits.utils.notifyApiError(error)
      }
    },
    deleteWalletAccount: function (walletAccountId) {
      LNbits.utils
        .confirmDialog(
          'Are you sure you want to delete this watch only wallet?'
        )
        .onOk(async () => {
          try {
            await LNbits.api.request(
              'DELETE',
              '/watchonly/api/v1/wallet/' + walletAccountId,
              this.g.user.wallets[0].adminkey
            )
            this.walletAccounts = _.reject(this.walletAccounts, function (obj) {
              return obj.id === walletAccountId
            })
            await this.refreshWalletAccounts()
            await this.refreshAddresses()
            if (
              this.payment.changeWallet &&
              this.payment.changeWallet.id === walletAccountId
            ) {
              this.payment.changeWallet = this.walletAccounts[0]
              this.selectChangeAddress(this.payment.changeWallet)
            }
            await this.scanAddressWithAmount()
          } catch (error) {
            this.$q.notify({
              type: 'warning',
              message: 'Error while deleting wallet account. Please try again.',
              timeout: 10000
            })
          }
        })
    },
    getAddressesForWallet: async function (walletId) {
      try {
        const {data} = await LNbits.api.request(
          'GET',
          '/watchonly/api/v1/addresses/' + walletId,
          this.g.user.wallets[0].inkey
        )
        return data.map(mapAddressesData)
      } catch (err) {
        this.$q.notify({
          type: 'warning',
          message: `Failed to fetch addresses for wallet with id ${walletId}.`,
          timeout: 10000
        })
        LNbits.utils.notifyApiError(err)
      }
      return []
    },
    getWatchOnlyWallets: async function () {
      try {
        const {data} = await LNbits.api.request(
          'GET',
          '/watchonly/api/v1/wallet',
          this.g.user.wallets[0].inkey
        )
        return data
      } catch (error) {
        this.$q.notify({
          type: 'warning',
          message: 'Failed to fetch wallets.',
          timeout: 10000
        })
        LNbits.utils.notifyApiError(error)
      }
      return []
    },
    refreshWalletAccounts: async function () {
      const wallets = await this.getWatchOnlyWallets()
      this.walletAccounts = wallets.map(w => mapWalletAccount(w))
    },
    getAmmountForWallet: function (walletId) {
      const amount = this.addresses.data
        .filter(a => a.wallet === walletId)
        .reduce((t, a) => t + a.amount || 0, 0)
      return this.satBtc(amount)
    },

    //################### ADDRESSES ###################

    refreshAddresses: async function () {
      const wallets = await this.getWatchOnlyWallets()
      this.addresses.data = []
      for (const {id, type} of wallets) {
        const newAddresses = await this.getAddressesForWallet(id)
        const uniqueAddresses = newAddresses.filter(
          newAddr =>
            !this.addresses.data.find(a => a.address === newAddr.address)
        )

        const lastAcctiveAddress =
          uniqueAddresses.filter(a => !a.isChange && a.hasActivity).pop() || {}

        uniqueAddresses.forEach(a => {
          a.expanded = false
          a.accountType = type
          a.gapLimitExceeded =
            !a.isChange &&
            a.addressIndex >
              lastAcctiveAddress.addressIndex +
                this.config.DEFAULT_RECEIVE_GAP_LIMIT
        })
        this.addresses.data.push(...uniqueAddresses)
      }
    },
    updateAmountForAddress: async function (addressData, amount = 0) {
      try {
        const wallet = this.g.user.wallets[0]
        addressData.amount = amount
        if (!addressData.isChange) {
          const addressWallet = this.walletAccounts.find(
            w => w.id === addressData.wallet
          )
          if (
            addressWallet &&
            addressWallet.address_no < addressData.addressIndex
          ) {
            addressWallet.address_no = addressData.addressIndex
          }
        }

        await LNbits.api.request(
          'PUT',
          `/watchonly/api/v1/address/${addressData.id}`,
          wallet.adminkey,
          {amount}
        )
      } catch (err) {
        addressData.error = 'Failed to refresh amount for address'
        this.$q.notify({
          type: 'warning',
          message: `Failed to refresh amount for address ${addressData.address}`,
          timeout: 10000
        })
        LNbits.utils.notifyApiError(err)
      }
    },
    updateNoteForAddress: async function (addressData, note) {
      try {
        const wallet = this.g.user.wallets[0]
        await LNbits.api.request(
          'PUT',
          `/watchonly/api/v1/address/${addressData.id}`,
          wallet.adminkey,
          {note: addressData.note}
        )
        const updatedAddress =
          this.addresses.data.find(a => a.id === addressData.id) || {}
        updatedAddress.note = note
      } catch (err) {
        LNbits.utils.notifyApiError(err)
      }
    },
    getFilteredAddresses: function () {
      const selectedWalletId = this.addresses.selectedWallet?.id
      const filter = this.addresses.filterValues || []
      const includeChangeAddrs = filter.includes('Show Change Addresses')
      const includeGapAddrs = filter.includes('Show Gap Addresses')
      const excludeNoAmount = filter.includes('Only With Amount')

      const walletsLimit = this.walletAccounts.reduce((r, w) => {
        r[`_${w.id}`] = w.address_no
        return r
      }, {})

      const addresses = this.addresses.data.filter(
        a =>
          (includeChangeAddrs || !a.isChange) &&
          (includeGapAddrs ||
            a.isChange ||
            a.addressIndex <= walletsLimit[`_${a.wallet}`]) &&
          !(excludeNoAmount && a.amount === 0) &&
          (!selectedWalletId || a.wallet === selectedWalletId)
      )
      return addresses
    },
    openGetFreshAddressDialog: async function (walletId) {
      const {data} = await LNbits.api.request(
        'GET',
        `/watchonly/api/v1/address/${walletId}`,
        this.g.user.wallets[0].inkey
      )
      const addressData = mapAddressesData(data)

      addressData.note = `Shared on ${currentDateTime()}`
      const lastAcctiveAddress =
        this.addresses.data
          .filter(
            a => a.wallet === addressData.wallet && !a.isChange && a.hasActivity
          )
          .pop() || {}
      addressData.gapLimitExceeded =
        !addressData.isChange &&
        addressData.addressIndex >
          lastAcctiveAddress.addressIndex +
            this.config.DEFAULT_RECEIVE_GAP_LIMIT

      this.openQrCodeDialog(addressData)
      const wallet = this.walletAccounts.find(w => w.id === walletId) || {}
      wallet.address_no = addressData.addressIndex
      await this.refreshAddresses()
    },

    //################### ADDRESS HISTORY ###################
    addressHistoryFromTxs: function (addressData, txs) {
      const addressHistory = []
      txs.forEach(tx => {
        const sent = tx.vin
          .filter(
            vin => vin.prevout.scriptpubkey_address === addressData.address
          )
          .map(vin => mapInputToSentHistory(tx, addressData, vin))

        const received = tx.vout
          .filter(vout => vout.scriptpubkey_address === addressData.address)
          .map(vout => mapOutputToReceiveHistory(tx, addressData, vout))
        addressHistory.push(...sent, ...received)
      })
      return addressHistory
    },
    getFilteredAddressesHistory: function () {
      return this.addresses.history.filter(
        a => (!a.isChange || a.sent) && !a.isSubItem
      )
    },
    exportHistoryToCSV: function () {
      const history = this.getFilteredAddressesHistory().map(a => ({
        ...a,
        action: a.sent ? 'Sent' : 'Received'
      }))
      LNbits.utils.exportCSV(
        this.historyTable.exportColums,
        history,
        'address-history'
      )
    },
    markSameTxAddressHistory: function () {
      this.addresses.history
        .filter(s => s.sent)
        .forEach((el, i, arr) => {
          if (el.isSubItem) return

          const sameTxItems = arr.slice(i + 1).filter(e => e.txId === el.txId)
          if (!sameTxItems.length) return
          sameTxItems.forEach(e => {
            e.isSubItem = true
          })

          el.totalAmount =
            el.amount + sameTxItems.reduce((t, e) => (t += e.amount || 0), 0)
          el.sameTxItems = sameTxItems
        })
    },
    showAddressHistoryDetails: function (addressHistory) {
      addressHistory.expanded = true
    },

    //################### PAYMENT ###################
    createTx: function (excludeChange = false) {
      const tx = {
        fee_rate: this.payment.feeRate,
        tx_size: this.payment.txSize,
        masterpubs: this.walletAccounts.map(w => ({
          public_key: w.masterpub,
          fingerprint: w.fingerprint
        }))
      }
      tx.inputs = this.utxos.data
        .filter(utxo => utxo.selected)
        .map(mapUtxoToPsbtInput)
        .sort((a, b) =>
          a.tx_id < b.tx_id ? -1 : a.tx_id > b.tx_id ? 1 : a.vout - b.vout
        )

      tx.outputs = this.payment.data.map(out => ({
        address: out.address,
        amount: out.amount
      }))

      if (excludeChange) {
        this.payment.changeAmount = 0
      } else {
        const change = this.createChangeOutput()
        this.payment.changeAmount = change.amount
        if (change.amount >= this.DUST_LIMIT) {
          tx.outputs.push(change)
        }
      }
      // Only sort by amount on UI level (no lib for address decode)
      // Should sort by scriptPubKey (as byte array) on the backend
      tx.outputs.sort((a, b) => a.amount - b.amount)

      return tx
    },
    createChangeOutput: function () {
      const change = this.payment.changeAddress
      const fee = this.payment.feeRate * this.payment.txSize
      const inputAmount = this.getTotalSelectedUtxoAmount()
      const payedAmount = this.getTotalPaymentAmount()
      const walletAcount =
        this.walletAccounts.find(w => w.id === change.wallet) || {}

      return {
        address: change.address,
        amount: inputAmount - payedAmount - fee,
        addressIndex: change.addressIndex,
        addressIndex: change.addressIndex,
        masterpub_fingerprint: walletAcount.fingerprint
      }
    },
    computeFee: function () {
      const tx = this.createTx()
      this.payment.txSize = Math.round(txSize(tx))
      return this.payment.feeRate * this.payment.txSize
    },
    createPsbt: async function () {
      const wallet = this.g.user.wallets[0]
      try {
        this.computeFee()
        const tx = this.createTx()
        txSize(tx)
        for (const input of tx.inputs) {
          input.tx_hex = await this.fetchTxHex(input.tx_id)
        }

        const {data} = await LNbits.api.request(
          'POST',
          '/watchonly/api/v1/psbt',
          wallet.adminkey,
          tx
        )

        this.payment.psbtBase64 = data
      } catch (err) {
        LNbits.utils.notifyApiError(err)
      }
    },
    deletePaymentAddress: function (v) {
      const index = this.payment.data.indexOf(v)
      if (index !== -1) {
        this.payment.data.splice(index, 1)
      }
    },
    initPaymentData: async function () {
      if (!this.payment.show) return
      await this.refreshAddresses()

      this.payment.showAdvanced = false
      this.payment.changeWallet = this.walletAccounts[0]
      this.selectChangeAddress(this.payment.changeWallet)

      await this.refreshRecommendedFees()
      this.payment.feeRate = this.payment.recommededFees.halfHourFee
    },
    getFeeRateLabel: function (feeRate) {
      const fees = this.payment.recommededFees
      if (feeRate >= fees.fastestFee) return `High Priority (${feeRate} sat/vB)`
      if (feeRate >= fees.halfHourFee)
        return `Medium Priority (${feeRate} sat/vB)`
      if (feeRate >= fees.hourFee) return `Low Priority (${feeRate} sat/vB)`
      return `No Priority (${feeRate} sat/vB)`
    },
    addPaymentAddress: function () {
      this.payment.data.push({address: '', amount: undefined})
    },
    getTotalPaymentAmount: function () {
      return this.payment.data.reduce((t, a) => t + (a.amount || 0), 0)
    },
    selectChangeAddress: function (wallet = {}) {
      this.payment.changeAddress =
        this.addresses.data.find(
          a => a.wallet === wallet.id && a.isChange && !a.hasActivity
        ) || {}
    },
    goToPaymentView: async function () {
      this.payment.show = true
      this.tab = 'utxos'
      await this.initPaymentData()
    },
    sendMaxToAddress: function (paymentAddress = {}) {
      paymentAddress.amount = 0
      const tx = this.createTx(true)
      this.payment.txSize = Math.round(txSize(tx))
      const fee = this.payment.feeRate * this.payment.txSize
      const inputAmount = this.getTotalSelectedUtxoAmount()
      const payedAmount = this.getTotalPaymentAmount()
      paymentAddress.amount = Math.max(0, inputAmount - payedAmount - fee)
    },

    //################### UTXOs ###################
    scanAllAddresses: async function () {
      await this.refreshAddresses()
      this.addresses.history = []
      let addresses = this.addresses.data
      this.utxos.data = []
      this.utxos.total = 0
      // Loop while new funds are found on the gap adresses.
      // Use 1000 limit as a safety check (scan 20 000 addresses max)
      for (let i = 0; i < 1000 && addresses.length; i++) {
        await this.updateUtxosForAddresses(addresses)
        const oldAddresses = this.addresses.data.slice()
        await this.refreshAddresses()
        const newAddresses = this.addresses.data.slice()
        // check if gap addresses have been extended
        addresses = newAddresses.filter(
          newAddr => !oldAddresses.find(oldAddr => oldAddr.id === newAddr.id)
        )
        if (addresses.length) {
          this.$q.notify({
            type: 'positive',
            message: 'Funds found! Scanning for more...',
            timeout: 10000
          })
        }
      }
    },
    scanAddressWithAmount: async function () {
      this.utxos.data = []
      this.utxos.total = 0
      this.addresses.history = []
      const addresses = this.addresses.data.filter(a => a.hasActivity)
      await this.updateUtxosForAddresses(addresses)
    },
    scanAddress: async function (addressData) {
      this.updateUtxosForAddresses([addressData])
      this.$q.notify({
        type: 'positive',
        message: 'Address Rescanned',
        timeout: 10000
      })
    },
    updateUtxosForAddresses: async function (addresses = []) {
      this.scan = {scanning: true, scanCount: addresses.length, scanIndex: 0}

      try {
        for (addrData of addresses) {
          const addressHistory = await this.getAddressTxsDelayed(addrData)
          // remove old entries
          this.addresses.history = this.addresses.history.filter(
            h => h.address !== addrData.address
          )

          // add new entrie
          this.addresses.history.push(...addressHistory)
          this.addresses.history.sort((a, b) =>
            !a.height ? -1 : b.height - a.height
          )
          this.markSameTxAddressHistory()

          if (addressHistory.length) {
            // search only if it ever had any activity
            const utxos = await this.getAddressTxsUtxoDelayed(addrData.address)
            this.updateUtxosForAddress(addrData, utxos)
          }

          this.scan.scanIndex++
        }
      } catch (error) {
        console.error(error)
        this.$q.notify({
          type: 'warning',
          message: 'Failed to scan addresses',
          timeout: 10000
        })
      } finally {
        this.scan.scanning = false
      }
    },
    updateUtxosForAddress: function (addressData, utxos = []) {
      const wallet =
        this.walletAccounts.find(w => w.id === addressData.wallet) || {}

      const newUtxos = utxos.map(utxo =>
        mapAddressDataToUtxo(wallet, addressData, utxo)
      )
      // remove old utxos
      this.utxos.data = this.utxos.data.filter(
        u => u.address !== addressData.address
      )
      // add new utxos
      this.utxos.data.push(...newUtxos)
      if (utxos.length) {
        this.utxos.data.sort((a, b) => b.sort - a.sort)
        this.utxos.total = this.utxos.data.reduce(
          (total, y) => (total += y?.amount || 0),
          0
        )
      }
      const addressTotal = utxos.reduce(
        (total, y) => (total += y?.value || 0),
        0
      )
      this.updateAmountForAddress(addressData, addressTotal)
    },
    getTotalSelectedUtxoAmount: function () {
      const total = this.utxos.data
        .filter(u => u.selected)
        .reduce((t, a) => t + (a.amount || 0), 0)
      return total
    },
    applyUtxoSelectionMode: function () {
      const payedAmount = this.getTotalPaymentAmount()
      const mode = this.payment.utxoSelectionMode
      this.utxos.data.forEach(u => (u.selected = false))
      const isManual = mode === 'Manual'
      if (isManual || !payedAmount) return

      const isSelectAll = mode === 'Select All'
      if (isSelectAll || payedAmount >= this.utxos.total) {
        this.utxos.data.forEach(u => (u.selected = true))
        return
      }
      const isSmallerFirst = mode === 'Smaller Inputs First'
      const isLargerFirst = mode === 'Larger Inputs First'

      let selectedUtxos = this.utxos.data.slice()
      if (isSmallerFirst || isLargerFirst) {
        const sortFn = isSmallerFirst
          ? (a, b) => a.amount - b.amount
          : (a, b) => b.amount - a.amount
        selectedUtxos.sort(sortFn)
      } else {
        // default to random order
        selectedUtxos = _.shuffle(selectedUtxos)
      }
      selectedUtxos.reduce((total, utxo) => {
        utxo.selected = total < payedAmount
        total += utxo.amount
        return total
      }, 0)
    },

    //################### MEMPOOL API ###################
    getAddressTxsDelayed: async function (addrData) {
      const {
        bitcoin: {addresses: addressesAPI}
      } = mempoolJS({
        hostname: new URL(this.config.data.mempool_endpoint).hostname
      })

      const fn = async () =>
        addressesAPI.getAddressTxs({
          address: addrData.address
        })
      const addressTxs = await retryWithDelay(fn)
      return this.addressHistoryFromTxs(addrData, addressTxs)
    },

    refreshRecommendedFees: async function () {
      const {
        bitcoin: {fees: feesAPI}
      } = mempoolJS({
        hostname: new URL(this.config.data.mempool_endpoint).hostname
      })

      const fn = async () => feesAPI.getFeesRecommended()
      this.payment.recommededFees = await retryWithDelay(fn)
    },
    getAddressTxsUtxoDelayed: async function (address) {
      const {
        bitcoin: {addresses: addressesAPI}
      } = mempoolJS({
        hostname: new URL(this.config.data.mempool_endpoint).hostname
      })

      const fn = async () =>
        addressesAPI.getAddressTxsUtxo({
          address
        })
      return retryWithDelay(fn)
    },
    fetchTxHex: async function (txId) {
      const {
        bitcoin: {transactions: transactionsAPI}
      } = mempoolJS({
        hostname: new URL(this.config.data.mempool_endpoint).hostname
      })

      try {
        const response = await transactionsAPI.getTxHex({txid: txId})
        return response
      } catch (error) {
        this.$q.notify({
          type: 'warning',
          message: `Failed to fetch transaction details for tx id: '${txId}'`,
          timeout: 10000
        })
        LNbits.utils.notifyApiError(error)
        throw error
      }
    },

    //################### OTHER ###################
    closeFormDialog: function () {
      this.formDialog.data = {
        is_unique: false
      }
    },
    openQrCodeDialog: function (addressData) {
      this.currentAddress = addressData
      this.addresses.note = addressData.note || ''
      this.addresses.show = true
    },
    searchInTab: function (tab, value) {
      this.tab = tab
      this[`${tab}Table`].filter = value
    },

    satBtc(val, showUnit = true) {
      const value = this.config.data.sats_denominated
        ? LNbits.utils.formatSat(val)
        : val == 0
        ? 0.0
        : (val / 100000000).toFixed(8)
      if (!showUnit) return value
      return this.config.data.sats_denominated ? value + ' sat' : value + ' BTC'
    },
    getAccountDescription: function (accountType) {
      return getAccountDescription(accountType)
    }
  },
  created: async function () {
    if (this.g.user.wallets.length) {
      await this.getConfig()
      await this.refreshWalletAccounts()
      await this.refreshAddresses()
      await this.scanAddressWithAmount()
    }
  }
})
