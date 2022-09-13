const watchOnly = async () => {
  Vue.component(VueQrcode.name, VueQrcode)

  await walletConfig('static/components/wallet-config/wallet-config.html')
  await walletList('static/components/wallet-list/wallet-list.html')
  await addressList('static/components/address-list/address-list.html')
  await history('static/components/history/history.html')
  await utxoList('static/components/utxo-list/utxo-list.html')
  await feeRate('static/components/fee-rate/fee-rate.html')
  await sendTo('static/components/send-to/send-to.html')
  await payment('static/components/payment/payment.html')
  await serialSigner('static/components/serial-signer/serial-signer.html')
  await serialPortConfig(
    'static/components/serial-port-config/serial-port-config.html'
  )

  Vue.filter('reverse', function (value) {
    // slice to make a copy of array, then reverse the copy
    return value.slice().reverse()
  })

  new Vue({
    el: '#vue',
    mixins: [windowMixin],
    data: function () {
      return {
        scan: {
          scanning: false,
          scanCount: 0,
          scanIndex: 0
        },

        currentAddress: null,

        tab: 'addresses',

        config: {sats_denominated: true},

        qrCodeDialog: {
          show: false,
          data: null
        },
        ...tables,
        ...tableData,

        walletAccounts: [],
        addresses: [],
        history: [],
        historyFilter: '',

        showAddress: false,
        addressNote: '',
        showPayment: false,
        fetchedUtxos: false,
        utxosFilter: '',
        network: null
      }
    },
    computed: {
      mempoolHostname: function () {
        if (!this.config.isLoaded) return
        let hostname = new URL(this.config.mempool_endpoint).hostname
        if (this.config.network === 'Testnet') {
          hostname += '/testnet'
        }
        return hostname
      }
    },

    methods: {
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

          // todo: account deleted
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
      updateNoteForAddress: async function ({addressId, note}) {
        try {
          const wallet = this.g.user.wallets[0]
          await LNbits.api.request(
            'PUT',
            `/watchonly/api/v1/address/${addressId}`,
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

      markSameTxAddressHistory: function () {
        this.history
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

      //################### PAYMENT ###################

      initPaymentData: async function () {
        if (!this.payment.show) return
        await this.refreshAddresses()
      },

      goToPaymentView: async function () {
        this.showPayment = true
        await this.initPaymentData()
      },

      //################### PSBT ###################

      updateSignedPsbt: async function (psbtBase64) {
        this.$refs.paymentRef.updateSignedPsbt(psbtBase64)
      },

      //################### SERIAL PORT ###################

      //################### HARDWARE WALLET ###################

      //################### UTXOs ###################
      scanAllAddresses: async function () {
        await this.refreshAddresses()
        this.history = []
        let addresses = this.addresses
        this.utxos.data = []
        this.utxos.total = 0
        // Loop while new funds are found on the gap adresses.
        // Use 1000 limit as a safety check (scan 20 000 addresses max)
        for (let i = 0; i < 1000 && addresses.length; i++) {
          await this.updateUtxosForAddresses(addresses)
          const oldAddresses = this.addresses.slice()
          await this.refreshAddresses()
          const newAddresses = this.addresses.slice()
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
        this.history = []
        const addresses = this.addresses.filter(a => a.hasActivity)
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
      refreshAddresses: async function () {
        if (!this.walletAccounts) return
        this.addresses = []
        for (const {id, type} of this.walletAccounts) {
          const newAddresses = await this.getAddressesForWallet(id)
          const uniqueAddresses = newAddresses.filter(
            newAddr => !this.addresses.find(a => a.address === newAddr.address)
          )

          const lastAcctiveAddress =
            uniqueAddresses.filter(a => !a.isChange && a.hasActivity).pop() ||
            {}

          uniqueAddresses.forEach(a => {
            a.expanded = false
            a.accountType = type
            a.gapLimitExceeded =
              !a.isChange &&
              a.addressIndex >
                lastAcctiveAddress.addressIndex + DEFAULT_RECEIVE_GAP_LIMIT
          })
          this.addresses.push(...uniqueAddresses)
        }
        this.$emit('update:addresses', this.addresses)
      },
      getAddressesForWallet: async function (walletId) {
        try {
          const {data} = await LNbits.api.request(
            'GET',
            '/watchonly/api/v1/addresses/' + walletId,
            this.g.user.wallets[0].inkey
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
        return []
      },
      updateUtxosForAddresses: async function (addresses = []) {
        this.scan = {scanning: true, scanCount: addresses.length, scanIndex: 0}

        try {
          for (addrData of addresses) {
            const addressHistory = await this.getAddressTxsDelayed(addrData)
            // remove old entries
            this.history = this.history.filter(
              h => h.address !== addrData.address
            )

            // add new entries
            this.history.push(...addressHistory)
            this.history.sort((a, b) => (!a.height ? -1 : b.height - a.height))
            this.markSameTxAddressHistory()

            if (addressHistory.length) {
              // search only if it ever had any activity
              const utxos = await this.getAddressTxsUtxoDelayed(
                addrData.address
              )
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

      //################### MEMPOOL API ###################
      getAddressTxsDelayed: async function (addrData) {
        const accounts = this.walletAccounts
        const {
          bitcoin: {addresses: addressesAPI}
        } = mempoolJS({
          hostname: this.mempoolHostname
        })
        const fn = async () => {
          if (!accounts.find(w => w.id === addrData.wallet)) return []
          return addressesAPI.getAddressTxs({
            address: addrData.address
          })
        }
        const addressTxs = await retryWithDelay(fn)
        return this.addressHistoryFromTxs(addrData, addressTxs)
      },

      getAddressTxsUtxoDelayed: async function (address) {
        const endpoint = this.mempoolHostname
        const {
          bitcoin: {addresses: addressesAPI}
        } = mempoolJS({
          hostname: endpoint
        })

        const fn = async () => {
          if (endpoint !== this.mempoolHostname) return []
          return addressesAPI.getAddressTxsUtxo({
            address
          })
        }
        return retryWithDelay(fn)
      },

      //################### OTHER ###################

      openQrCodeDialog: function (addressData) {
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
        await this.refreshAddresses()
        await this.scanAddressWithAmount()
      },
      showAddressDetails: function (addressData) {
        this.openQrCodeDialog(addressData)
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
        this.searchInTab({tab: 'history', value: txId})
        this.showPayment = false
        await this.refreshAddresses()
        await this.scanAddressWithAmount()
      }
    },
    created: async function () {
      if (this.g.user.wallets.length) {
        await this.refreshAddresses()
        await this.scanAddressWithAmount()
      }
    }
  })
}
watchOnly()
