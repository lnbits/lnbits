import {
  DEFAULT_RECEIVE_GAP_LIMIT,
  satOrBtc,
  addressBalance
} from './js/utils.js'
import {
  mapAddressesData,
  mapInputToSentHistory,
  mapOutputToReceiveHistory,
  mapAddressDataToUtxo
} from './js/map.js'

import {OnchainLiveUpdates} from './js/live-updates.js'
import './components/utxo-list.js'
import './components/serial-signer.js'
import './components/hot-wallet.js'
import './components/trezor-signer.js'
import './components/wallet-list.js'
import './components/address-list.js'
import './components/payment.js'
import './components/seed-input.js'
import './components/fee-rate.js'
import './components/wallet-config.js'
import './components/send-to.js'
import './components/serial-port-config.js'
export default {
  name: 'OnchainWallet',
  template: '#page-onchain',
  props: ['chartConfig'],
  emits: ['synced', 'update-wallet', 'update:addresses'],
  data() {
    return {
      scan: {
        scanning: false,
        scanCount: 0,
        scanIndex: 0
      },

      currentAddress: null,

      tab: 'history',
      selectedWalletId: null,
      receiving: false,
      receiveAmount: null,
      lastSynced: null,
      lastBroadcastTxId: null,
      liveUpdates: null,
      stateLoading: false,
      lastStateVersion: null,
      disposed: false,
      syncError: false,

      config: {sats_denominated: true},

      utxos: {data: [], total: 0},

      walletAccounts: [],
      addresses: [],
      history: [],
      transactionFirstSeen: {},
      activityNow: Date.now(),
      historyFilter: '',
      activityPagination: {
        page: 1,
        rowsPerPage: 10,
        sortBy: 'time',
        descending: true
      },

      showAddress: false,
      addressNote: '',
      showPayment: false,
      paymentData: {accounts: [], addresses: [], utxos: []},
      fetchedUtxos: false,
      utxosFilter: '',
      network: null,

      showEnterSignedPsbt: false,
      signedBase64Psbt: null,

      connectedDeviceType: null
    }
  },
  computed: {
    liveWatchAddresses() {
      const watched = [this.currentAddress?.address]
      for (const account of this.walletAccounts) {
        const receiving = this.addresses
          .filter(a => a.wallet === account.id && !a.isChange)
          .sort((a, b) => b.addressIndex - a.addressIndex)
        const issued = receiving.find(a => a.addressIndex <= account.address_no)
        watched.push((issued || receiving[receiving.length - 1])?.address)
      }
      watched.push(
        ...this.addresses.filter(a => a.amount > 0).map(a => a.address)
      )
      return watched.filter(Boolean)
    },
    selectedWallet() {
      return (
        this.walletAccounts.find(w => w.id === this.selectedWalletId) || null
      )
    },
    selectedAccounts() {
      return this.selectedWallet ? [this.selectedWallet] : []
    },
    selectedAddresses() {
      return this.addresses.filter(a => a.wallet === this.selectedWalletId)
    },
    selectedUtxos() {
      return this.utxos.data.filter(u => u.wallet === this.selectedWalletId)
    },
    selectedBalance() {
      return addressBalance(this.selectedAddresses)
    },
    pendingBalance() {
      return this.selectedUtxos
        .filter(u => !u.confirmed)
        .reduce((sum, u) => sum + u.amount, 0)
    },
    balanceLabel() {
      return this.formatAmount(this.selectedBalance)
    },
    walletKindLabel() {
      return this.selectedWallet?.wallet_kind === 'hot'
        ? 'Server wallet'
        : this.selectedWallet?.meta?.xpub
          ? 'Hardware wallet'
          : 'Watch-only wallet'
    },
    canTransact() {
      return (
        this.selectedWallet &&
        (this.selectedWallet.wallet_kind !== 'hot' ||
          this.selectedWallet.backup_confirmed)
      )
    },
    receiveUri() {
      if (!this.currentAddress) return ''
      const amount = this.receiveAmount
      return (
        'bitcoin:' +
        this.currentAddress.address +
        (Number.isSafeInteger(amount) &&
        amount > 0 &&
        amount <= 2100000000000000
          ? '?amount=' + (amount / 100000000).toFixed(8)
          : '')
      )
    },
    activityColumns() {
      return [
        {
          name: 'time',
          label: 'Transaction / Date',
          align: 'left',
          sortable: true,
          field: row =>
            row.confirmed
              ? row.timestamp || row.height || 0
              : Number.MAX_SAFE_INTEGER
        },
        {
          name: 'amount',
          label: this.config.sats_denominated
            ? 'Amount (sats)'
            : 'Amount (BTC)',
          align: 'right',
          field: 'amount',
          sortable: true
        }
      ]
    },
    activity() {
      const addresses = new Set(this.selectedAddresses.map(a => a.address))
      const grouped = new Map()
      for (const row of this.history) {
        if (!addresses.has(row.address)) continue
        if (!grouped.has(row.txId)) {
          grouped.set(row.txId, {
            ...row,
            amount: 0,
            outputs: new Set(),
            receivedAddresses: new Set()
          })
        }
        const transaction = grouped.get(row.txId)
        transaction.amount += row.received ? row.amount : -row.amount
        for (const output of row.outputAddresses || [])
          transaction.outputs.add(output)
        if (row.received) transaction.receivedAddresses.add(row.address)
      }
      const needle = (this.historyFilter || '').trim().toLowerCase()
      return [...grouped.values()]
        .map(row => {
          const recipients = [...row.outputs].filter(
            address => !addresses.has(address)
          )
          row.transactionAddresses =
            row.amount < 0 && recipients.length
              ? recipients
              : [...row.receivedAddresses]
          return row
        })
        .filter(
          row =>
            row.txId.includes(needle) ||
            row.address.toLowerCase().includes(needle) ||
            row.transactionAddresses.some(address =>
              address.toLowerCase().includes(needle)
            ) ||
            String(row.amount).includes(needle) ||
            this.formatActivityAmount(row.amount).includes(needle) ||
            (row.amount < 0 ? 'sent bitcoin' : 'received bitcoin').includes(
              needle
            )
        )
    },
    hasFiatRate() {
      return this.g.fiatTracking && Number(this.g.exchangeRate) > 0
    },
    selectedFiat() {
      return LNbits.utils.formatCurrency(
        (this.selectedBalance * (this.g.exchangeRate || 0)) / 100000000,
        this.g.wallet.currency
      )
    },
    mempoolHostname: function () {
      if (!this.config.isLoaded) return
      if (this.config.explorer_url) return this.config.explorer_url
      let hostname = this.config.mempool_endpoint.replace(/\/$/, '')
      if (this.config.network === 'Testnet') {
        hostname += '/testnet'
      } else if (this.config.network === 'Testnet4') {
        hostname += '/testnet4'
      }
      return hostname
    },
    signerDevice: function () {
      if (this.connectedDeviceType === 'trezor-device') {
        return this.$refs.trezorSigner
      }
      return this.$refs.serialSigner
    }
  },

  watch: {
    'config.explorer_provider'() {
      this.liveUpdates?.update()
    },
    'config.lnbits_explorer_network'() {
      this.liveUpdates?.update()
    },
    'currentAddress.address'() {
      this.liveUpdates?.update()
    },
    historyFilter() {
      this.activityPagination.page = 1
    },
    selectedWalletId() {
      this.activityPagination.page = 1
    },
    'config.network': function () {
      this.scan = {scanning: false, scanCount: 0, scanIndex: 0}
      this.selectedWalletId = null
      this.showPayment = false
      this.showAddress = false
      this.lastSynced = null
      this.lastBroadcastTxId = null
      this.walletAccounts = []
      this.addresses = []
      this.history = []
      this.transactionFirstSeen = {}
      this.utxos.data = []
      this.utxos.total = 0
      this.lastStateVersion = null
      this.liveUpdates?.update()
    }
  },

  methods: {
    formatActivityAmount(value) {
      return satOrBtc(value, false, this.config.sats_denominated)
    },
    activityDate(row) {
      const timestamp = row.confirmed ? row.timestamp : row.firstSeen
      // Older cached history contains only the localized LLL date string.
      const date = timestamp
        ? moment.unix(timestamp)
        : moment(row.date || '', 'LLL', true)
      return date.isValid()
        ? date.from(moment(this.activityNow))
        : row.confirmed
          ? 'Confirmed'
          : 'Pending confirmation'
    },
    shortActivityAddress(address) {
      return address.length > 26
        ? address.slice(0, 14) + '…' + address.slice(-10)
        : address
    },
    formatAmount(value) {
      return satOrBtc(value, true, this.config.sats_denominated)
    },
    async receiveBitcoin() {
      if (!this.canTransact || this.receiving) return
      this.receiving = true
      try {
        await this.$refs.walletList.openGetFreshAddressDialog(
          this.selectedWalletId
        )
      } catch (error) {
        LNbits.utils.notifyApiError(error)
      } finally {
        this.receiving = false
      }
    },
    async hotWalletCreated(wallet) {
      this.selectedWalletId = wallet.id
      await this.$refs.walletList.refreshWalletAccounts()
    },

    updateNoteForAddress: async function ({addressId, note}) {
      try {
        const wallet = this.g.wallet
        await LNbits.api.request(
          'PUT',
          `/onchain/api/v1/address/${addressId}`,
          wallet.adminkey,
          {note}
        )
        const updatedAddress =
          this.addresses.find(a => a.id === addressId) || {}
        updatedAddress.note = note
      } catch (err) {
        LNbits.utils.notifyApiError(err)
      }
    },

    //################### ADDRESS HISTORY ###################
    addressHistoryFromTxs: function (addressData, txs) {
      const addressHistory = []
      this.activityNow = Date.now()
      txs.forEach(tx => {
        if (!this.transactionFirstSeen[tx.txid]) {
          this.transactionFirstSeen[tx.txid] = Math.floor(
            this.activityNow / 1000
          )
        }
        const outputAddresses = [
          ...new Set(
            tx.vout.map(output => output.scriptpubkey_address).filter(Boolean)
          )
        ]
        const sent = tx.vin
          .filter(
            vin => vin.prevout?.scriptpubkey_address === addressData.address
          )
          .map(vin => mapInputToSentHistory(tx, addressData, vin))

        const received = tx.vout
          .filter(vout => vout.scriptpubkey_address === addressData.address)
          .map(vout => mapOutputToReceiveHistory(tx, addressData, vout))
        addressHistory.push(
          ...[...sent, ...received].map(row => ({
            ...row,
            timestamp: tx.status.block_time,
            firstSeen: this.transactionFirstSeen[tx.txid],
            outputAddresses
          }))
        )
      })
      return addressHistory
    },

    //################### PAYMENT ###################

    initPaymentData: function () {
      // A scan may finish while the user edits or reviews a payment. Keep its
      // coins and change address stable, independent of the live balance cache.
      this.paymentData = {
        accounts: this.selectedAccounts.map(account => ({...account})),
        addresses: this.selectedAddresses.map(address => ({...address})),
        utxos: this.selectedUtxos.map(utxo => ({...utxo, selected: false}))
      }
    },

    goToPaymentView: function () {
      if (this.showPayment || !this.canTransact || !this.selectedUtxos.length)
        return
      this.initPaymentData()
      this.showPayment = true
    },

    //################### PSBT ###################

    updateSignedPsbt: async function (psbtBase64) {
      this.$refs.paymentRef?.updateSignedPsbt(psbtBase64)
    },

    updateSignedTx: async function (txHex) {
      this.$refs.paymentRef?.updateSignedTx(txHex)
    },

    showEnterSignedPsbtDialog: function () {
      this.signedBase64Psbt = ''
      this.showEnterSignedPsbt = true
    },

    checkPsbt: async function () {
      await this.$refs.paymentRef.updateSignedPsbt(this.signedBase64Psbt)
      if (this.$refs.paymentRef.showFinalTx) this.showEnterSignedPsbt = false
    },
    async openImportPsbt() {
      if (!this.showPayment) this.initPaymentData()
      this.showPayment = true
      await this.$nextTick()
      this.showEnterSignedPsbtDialog()
    },
    exportActivity() {
      LNbits.utils.exportCSV(
        [
          {label: 'Transaction', field: 'txId'},
          {label: 'Net amount (sats)', field: 'amount'},
          {label: 'Confirmed', field: 'confirmed'},
          {label: 'Date', field: 'date'}
        ],
        this.activity,
        'onchain-activity'
      )
    },

    //################### UTXOs ###################
    async hydrateState() {
      if (this.disposed || this.stateLoading) return
      this.stateLoading = true
      const coreWalletId = this.g.wallet.id
      try {
        const {data} = await LNbits.api.request(
          'GET',
          '/onchain/api/v1/state',
          this.g.wallet.inkey
        )
        if (this.disposed || coreWalletId !== this.g.wallet.id) return
        this.scan.scanning = data.scanning
        this.syncError = !!data.error
        this.lastSynced = data.checked_at
          ? moment.unix(data.checked_at).format('HH:mm')
          : null
        const accounts = new Map(this.walletAccounts.map(w => [w.id, w]))
        this.addresses = data.addresses.map(a => ({
          ...mapAddressesData(a),
          accountType: accounts.get(a.wallet)?.type
        }))
        const snapshots = new Map(data.snapshots.map(s => [s.address_id, s]))
        const history = []
        const coins = []
        const seenAddresses = new Set()
        const seenCoins = new Set()
        for (const address of this.addresses) {
          const snapshot = snapshots.get(address.id)
          const account = accounts.get(address.wallet)
          if (!snapshot || !account) continue
          for (const tx of snapshot.transactions) {
            this.transactionFirstSeen[tx.txid] = tx.first_seen
          }
          if (!seenAddresses.has(address.address)) {
            history.push(
              ...this.addressHistoryFromTxs(address, snapshot.transactions)
            )
            seenAddresses.add(address.address)
          }
          for (const coin of snapshot.utxos) {
            const id = `${account.id}:${coin.txid}:${coin.vout}`
            if (seenCoins.has(id)) continue
            seenCoins.add(id)
            coins.push(mapAddressDataToUtxo(account, address, coin))
          }
        }
        this.history = history
        this.utxos.data = coins
        this.utxos.total = coins.reduce((sum, u) => sum + u.amount, 0)
        this.g.wallet.sat = data.balance_sat
        this.g.wallet.msat = data.balance_sat * 1000
        this.g.fiatBalance =
          (data.balance_sat * (this.g.exchangeRate || 0)) / 100000000
        // Charts contain confirmed activity, not scan timestamps. Ignore a
        // refresh that simply rechecks the same transactions, and publish charts
        // once the scan has finished rather than after each address snapshot.
        const version = JSON.stringify(
          history
            .filter(row => row.confirmed)
            .map(row =>
              JSON.stringify([
                row.txId,
                row.address,
                !!row.sent,
                row.amount,
                row.timestamp,
                row.fee
              ])
            )
            .sort()
        )
        if (!data.scanning && version !== this.lastStateVersion) {
          this.lastStateVersion = version
          this.$emit('synced')
        }
      } catch (error) {
        if (!this.disposed) this.syncError = true
      } finally {
        this.stateLoading = false
        this.liveUpdates?.update()
      }
    },
    async scanAllAddresses() {
      if (this.disposed) return
      await this.hydrateState()
      try {
        await LNbits.api.request(
          'POST',
          '/onchain/api/v1/sync',
          this.g.wallet.adminkey
        )
        if (!this.disposed) this.scan.scanning = true
        this.liveUpdates?.update()
      } catch (error) {
        this.syncError = true
        LNbits.utils.notifyApiError(error)
      }
    },
    scanAddressWithAmount() {
      return this.scanAllAddresses()
    },
    scanAddress() {
      return this.scanAllAddresses()
    },
    refreshAddresses: async function () {
      if (!this.walletAccounts) return
      const accounts = this.walletAccounts
      const network = this.config.network
      const addresses = []
      for (const {id, type} of accounts) {
        const newAddresses = await this.getAddressesForWallet(id)
        if (accounts !== this.walletAccounts || network !== this.config.network)
          return
        const uniqueAddresses = newAddresses.filter(
          newAddr =>
            !addresses.find(
              a => a.wallet === newAddr.wallet && a.address === newAddr.address
            )
        )

        const lastActiveAddress = uniqueAddresses
          .filter(a => !a.isChange && a.hasActivity)
          .pop() || {addressIndex: -1}

        uniqueAddresses.forEach(a => {
          a.expanded = false
          a.accountType = type
          a.gapLimitExceeded =
            !a.isChange &&
            a.addressIndex >
              lastActiveAddress.addressIndex + DEFAULT_RECEIVE_GAP_LIMIT
        })
        addresses.push(...uniqueAddresses)
      }
      this.addresses = addresses
      this.$emit('update:addresses', this.addresses)
    },
    getAddressesForWallet: async function (walletId) {
      try {
        const {data} = await LNbits.api.request(
          'GET',
          '/onchain/api/v1/addresses/' + walletId,
          this.g.wallet.inkey
        )
        return data.map(mapAddressesData)
      } catch (error) {
        this.$q.notify({
          type: 'warning',
          message: `Failed to fetch addresses for wallet with id ${walletId}.`,
          timeout: 10000
        })
        LNbits.utils.notifyApiError(error)
      }
      throw new Error('Could not load wallet addresses')
    },
    openQrCodeDialog: function (addressData) {
      this.receiveAmount = null
      this.currentAddress = addressData
      this.addressNote = addressData.note || ''
      this.showAddress = true
    },
    searchInTab: function ({tab, value}) {
      this.tab = tab
      this[`${tab}Filter`] = value
    },

    updateAccounts: async function (accounts) {
      this.walletAccounts = accounts
      const walletIds = new Set(accounts.map(w => w.id))
      this.addresses = this.addresses.filter(a => walletIds.has(a.wallet))
      this.utxos.data = this.utxos.data.filter(u => walletIds.has(u.wallet))
      this.utxos.total = this.utxos.data.reduce((sum, u) => sum + u.amount, 0)
      const retainedAddresses = new Set(this.addresses.map(a => a.address))
      this.history = this.history.filter(h => retainedAddresses.has(h.address))
      if (!accounts.some(w => w.id === this.selectedWalletId))
        this.selectedWalletId = accounts[0]?.id || null
      // Publish new wallets/addresses immediately; an active scan queues the next pass.
      await this.refreshAddresses()
      await this.scanAllAddresses()
    },
    showAddressDetails: function (addressData) {
      this.openQrCodeDialog(addressData)
    },
    showAddressDetailsWithConfirmation: async function ({addressData, wallet}) {
      this.showAddressDetails(addressData)
      if (wallet.wallet_kind === 'hot') return
      const signer = this.signerDevice
      if (!signer?.isConnected() || !wallet.meta?.accountPath) return
      if (!signer.isAuthenticated()) {
        this.$q.notify({
          type: 'warning',
          message: 'Unlock the hardware wallet to verify this address.'
        })
        return
      }
      const path =
        wallet.meta.accountPath +
        `/${addressData.isChange ? 1 : 0}/${addressData.addressIndex}`
      try {
        await signer.hwwShowAddress(path, addressData.address)
      } catch (_) {
        this.$q.notify({
          type: 'negative',
          message:
            'Address verification failed. Check the connected device and wallet before receiving.'
        })
      }
    },
    initUtxos: function (addresses) {
      if (!this.fetchedUtxos && addresses.length) {
        this.fetchedUtxos = true
        this.addresses = addresses
        this.scanAddressWithAmount()
      }
    },
    handleBroadcastSuccess: async function (txId) {
      this.tab = 'history'
      this.historyFilter = ''
      this.lastBroadcastTxId = txId
      this.showPayment = false
      await this.refreshAddresses()
      await this.scanAllAddresses()
    },
    handleDeviceConnected: async function (deviceType) {
      this.connectedDeviceType = deviceType
    }
  },
  mounted() {
    this.liveUpdates = Vue.markRaw(
      new OnchainLiveUpdates({
        refresh: () => this.hydrateState(),
        scan: () => this.scanAllAddresses(),
        scanning: () => this.scan.scanning,
        clock: () => {
          this.activityNow = Date.now()
        },
        localExplorer: () =>
          this.config.explorer_provider === 'lnbits' &&
          this.config.lnbits_explorer_network === this.config.network,
        addresses: () => this.liveWatchAddresses
      })
    )
    this.liveUpdates.start()
  },
  beforeUnmount() {
    this.disposed = true
    this.liveUpdates?.stop()
    this.scan = {scanning: false, scanCount: 0, scanIndex: 0}
    this.walletAccounts = []
  },
  created: async function () {
    if (this.g.user.wallets.length) {
      await this.refreshAddresses()
    }
  }
}
