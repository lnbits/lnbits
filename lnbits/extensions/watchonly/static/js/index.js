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
        filter: '', // todo: remove?

        scan: {
          scanning: false,
          scanCount: 0,
          scanIndex: 0
        },

        currentAddress: null,

        tab: 'addresses',
        paymentTab: 'destination',

        config: {
          data: {
            mempool_endpoint: 'https://mempool.space',
            receive_gap_limit: 20,
            change_gap_limit: 5
          },

          show: false
        },

        serial: {
          selectedPort: null,
          writableStreamClosed: null,
          writer: null,
          readableStreamClosed: null,
          reader: null,
          showAdvancedConfig: false,
          receivedData: '',
          config: {}
        },

        hww: {
          password: null,
          showPassword: false,
          mnemonic: null,
          showMnemonic: false,
          authenticated: false,
          showPasswordDialog: false,
          showWipeDialog: false,
          showRestoreDialog: false,
          showConsole: false,
          showSignedPsbt: false,
          sendingPsbt: false,
          signingPsbt: false,
          psbtSent: false
        },

        qrCodeDialog: {
          show: false,
          data: null
        },
        ...tables,
        ...tableData,

        walletAccounts: [],
        addresses: [],
        history: [],

        showAddress: false,
        addressNote: '',
        showPayment: false,
        showCustomFee: false,
        feeRate: 1,
        sendToList: []
      }
    },

    computed: {
      txSize: function() {
        const tx = this.createTx()
        return Math.round(txSize(tx))
      },
      txSizeNoChange: function() {
        const tx = this.createTx(true)
        return Math.round(txSize(tx))
      },
      feeValue: function(){
        return this.feeRate * this.txSize
      }
    },

    methods: {
      //################### CONFIG ###################

      //################### WALLETS ###################

      getWalletName: function (walletId) {
        const wallet = this.walletAccounts.find(wl => wl.id === walletId)
        return wallet ? wallet.title : 'unknown'
      },
      //################### ADDRESSES ###################

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
            this.addresses.find(a => a.id === addressData.id) || {}
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
      showAddressHistoryDetails: function (addressHistory) {
        addressHistory.expanded = true
      },

      //################### PAYMENT ###################
      createTx: function (excludeChange = false) {
        const tx = {
          fee_rate: this.feeRate,
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

        tx.outputs = this.sendToList.map(out => ({
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
        // todo: just shuffle
        tx.outputs.sort((a, b) => a.amount - b.amount)

        return tx
      },
      createChangeOutput: function () {
        const change = this.payment.changeAddress
        // const inputAmount = this.getTotalSelectedUtxoAmount() // todo: set amount separately
        // const payedAmount = this.getTotalPaymentAmount()
        const walletAcount =
          this.walletAccounts.find(w => w.id === change.wallet) || {}

        return {
          address: change.address,
          // amount: inputAmount - payedAmount - this.feeValue,
          addressIndex: change.addressIndex,
          addressIndex: change.addressIndex,
          masterpub_fingerprint: walletAcount.fingerprint
        }
      },

      initPaymentData: async function () {
        if (!this.payment.show) return
        await this.$refs.addressList.refreshAddresses()

        this.payment.showAdvanced = false
        this.payment.changeWallet = this.walletAccounts[0]
        this.selectChangeAddress(this.payment.changeWallet)

        this.payment.feeRate = this.payment.recommededFees.halfHourFee
      },

      getTotalPaymentAmount: function () {
        return this.payment.data.reduce((t, a) => t + (a.amount || 0), 0)
      },
      selectChangeAddress: function (wallet = {}) {
        this.payment.changeAddress =
          this.addresses.find(
            a => a.wallet === wallet.id && a.isChange && !a.hasActivity
          ) || {}
      },
      goToPaymentView: async function () {
        // this.payment.show = true
        this.showPayment = true
        // this.tab = 'utxos'
        await this.initPaymentData()
      },

      //################### PSBT ###################
      createPsbt: async function () {
        const wallet = this.g.user.wallets[0]
        try {
          // this.computeFee(this.feeRate)
          const tx = this.createTx()
          // txSize(tx)
          for (const input of tx.inputs) {
            input.tx_hex = await this.fetchTxHex(input.tx_id)
          }

          this.payment.tx = tx
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
      extractTxFromPsbt: async function (psbtBase64) {
        const wallet = this.g.user.wallets[0]
        try {
          const {data} = await LNbits.api.request(
            'PUT',
            '/watchonly/api/v1/psbt/extract',
            wallet.adminkey,
            {
              psbtBase64,
              inputs: this.payment.tx.inputs
            }
          )
          return data
        } catch (error) {
          this.$q.notify({
            type: 'warning',
            message: 'Cannot finalize PSBT!',
            timeout: 10000
          })
          LNbits.utils.notifyApiError(error)
        }
      },
      updateSignedPsbt: async function (value) {
        this.payment.psbtBase64Signed = value

        const data = await this.extractTxFromPsbt(this.payment.psbtBase64Signed)
        if (data) {
          this.payment.signedTx = JSON.parse(data.tx_json)
          this.payment.signedTxHex = data.tx_hex
        } else {
          this.payment.signedTx = null
          this.payment.signedTxHex = null
        }
      },
      broadcastTransaction: async function () {
        try {
          const wallet = this.g.user.wallets[0]
          const {data} = await LNbits.api.request(
            'POST',
            '/watchonly/api/v1/tx',
            wallet.adminkey,
            {tx_hex: this.payment.signedTxHex}
          )
          this.payment.sentTxId = data

          this.$q.notify({
            type: 'positive',
            message: 'Transaction broadcasted!',
            caption: `${data}`,
            timeout: 10000
          })

          this.hww.psbtSent = false
          this.payment.psbtBase64Signed = null
          this.payment.signedTxHex = null
          this.payment.signedTx = null
          this.payment.psbtBase64 = null

          await this.scanAddressWithAmount()
        } catch (error) {
          this.payment.sentTxId = null
          this.$q.notify({
            type: 'warning',
            message: 'Failed to broadcast!',
            caption: `${error}`,
            timeout: 10000
          })
        }
      },
      //################### SERIAL PORT ###################
      checkSerialPortSupported: function () {
        if (!navigator.serial) {
          this.$q.notify({
            type: 'warning',
            message: 'Serial port communication not supported!',
            caption:
              'Make sure your browser supports Serial Port and that you are using HTTPS.',
            timeout: 10000
          })
          return false
        }
        return true
      },
      openSerialPort: async function () {
        if (!this.checkSerialPortSupported()) return
        console.log('### openSerialPort', this.serial.selectedPort)
        try {
          navigator.serial.addEventListener('connect', event => {
            console.log('### navigator.serial event: connected!', event)
          })

          navigator.serial.addEventListener('disconnect', () => {
            this.hww.authenticated = false
            this.$q.notify({
              type: 'warning',
              message: 'Disconnected from Serial Port!',
              timeout: 10000
            })
          })
          this.serial.selectedPort = await navigator.serial.requestPort()
          // Wait for the serial port to open.
          await this.serial.selectedPort.open({baudRate: 9600})
          this.startSerialPortReading()

          const textEncoder = new TextEncoderStream()
          this.serial.writableStreamClosed = textEncoder.readable.pipeTo(
            this.serial.selectedPort.writable
          )

          this.serial.writer = textEncoder.writable.getWriter()
        } catch (error) {
          this.serial.selectedPort = null
          this.$q.notify({
            type: 'warning',
            message: 'Cannot open serial port!',
            caption: `${error}`,
            timeout: 10000
          })
        }
      },
      closeSerialPort: async function () {
        try {
          console.log('### closeSerialPort', this.serial.selectedPort)
          if (this.serial.writer) this.serial.writer.close()
          if (this.serial.writableStreamClosed)
            await this.serial.writableStreamClosed
          if (this.serial.reader) this.serial.reader.cancel()
          if (this.serial.readableStreamClosed)
            await this.serial.readableStreamClosed.catch(() => {
              /* Ignore the error */
            })
          if (this.serial.selectedPort) await this.serial.selectedPort.close()
          this.serial.selectedPort = null
          this.$q.notify({
            type: 'positive',
            message: 'Serial port disconnected!',
            timeout: 5000
          })
        } catch (error) {
          this.serial.selectedPort = null
          console.log('### error', error)
          this.$q.notify({
            type: 'warning',
            message: 'Cannot close serial port!',
            caption: `${error}`,
            timeout: 10000
          })
        }
      },

      startSerialPortReading: async function () {
        const port = this.serial.selectedPort

        while (port && port.readable) {
          const textDecoder = new TextDecoderStream()
          this.serial.readableStreamClosed = port.readable.pipeTo(
            textDecoder.writable
          )
          this.serial.reader = textDecoder.readable.getReader()
          const readStringUntil = readFromSerialPort(this.serial)

          try {
            while (true) {
              const {value, done} = await readStringUntil('\n')
              console.log('### value', value)
              if (value) {
                this.handleSerialPortResponse(value)
                this.updateSerialPortConsole(value)
              }
              console.log('### startSerialPortReading DONE', done)
              if (done) return
            }
          } catch (error) {
            this.$q.notify({
              type: 'warning',
              message: 'Serial port communication error!',
              caption: `${error}`,
              timeout: 10000
            })
          }
        }
        console.log('### startSerialPortReading port', port)
      },

      handleSerialPortResponse: function (value) {
        const msg = value.split(' ')
        if (msg[0] == COMMAND_SIGN_PSBT) this.handleSignResponse(msg[1])
        else if (msg[0] == COMMAND_PASSWORD) this.handleLoginResponse(msg[1])
        else if (msg[0] == COMMAND_PASSWORD_CLEAR)
          this.handleLogoutResponse(msg[1])
        else if (msg[0] == COMMAND_SEND_PSBT)
          this.handleSendPsbtResponse(msg[1])
        else if (msg[0] == COMMAND_WIPE) this.handleWipeResponse(msg[1])
        else console.log('### handleSerialPortResponse', value)
      },
      updateSerialPortConsole: function (value) {
        this.serial.receivedData += value + '\n'
        const textArea = document.getElementById(
          'watchonly-serial-port-data-input'
        )
        if (textArea) textArea.scrollTop = textArea.scrollHeight
      },
      sharePsbtWithAnimatedQRCode: async function () {
        console.log('### sharePsbtWithAnimatedQRCode')
      },
      //################### HARDWARE WALLET ###################
      hwwShowPasswordDialog: async function () {
        try {
          this.hww.showPasswordDialog = true
          await this.serial.writer.write(COMMAND_PASSWORD + '\n')
        } catch (error) {
          this.$q.notify({
            type: 'warning',
            message: 'Failed to connect to Hardware Wallet!',
            caption: `${error}`,
            timeout: 10000
          })
        }
      },
      hwwShowWipeDialog: async function () {
        try {
          this.hww.showWipeDialog = true
          await this.serial.writer.write(COMMAND_WIPE + '\n')
        } catch (error) {
          this.$q.notify({
            type: 'warning',
            message: 'Failed to connect to Hardware Wallet!',
            caption: `${error}`,
            timeout: 10000
          })
        }
      },
      hwwShowRestoreDialog: async function () {
        try {
          this.hww.showRestoreDialog = true
          await this.serial.writer.write(COMMAND_WIPE + '\n')
        } catch (error) {
          this.$q.notify({
            type: 'warning',
            message: 'Failed to connect to Hardware Wallet!',
            caption: `${error}`,
            timeout: 10000
          })
        }
      },
      hwwLogin: async function () {
        try {
          await this.serial.writer.write(
            COMMAND_PASSWORD + ' ' + this.hww.password + '\n'
          )
        } catch (error) {
          this.$q.notify({
            type: 'warning',
            message: 'Failed to send password to Hardware Wallet!',
            caption: `${error}`,
            timeout: 10000
          })
        } finally {
          this.hww.showPasswordDialog = false
          this.hww.password = null
          this.hww.showPassword = false
        }
      },
      handleLoginResponse: function (res = '') {
        this.hww.authenticated = res.trim() === '1'
        if (this.hww.authenticated) {
          this.$q.notify({
            type: 'positive',
            message: 'Login successfull!',
            timeout: 10000
          })
        } else {
          this.$q.notify({
            type: 'warning',
            message: 'Wrong password, try again!',
            timeout: 10000
          })
        }
      },
      hwwLogout: async function () {
        try {
          await this.serial.writer.write(COMMAND_PASSWORD_CLEAR + '\n')
        } catch (error) {
          this.$q.notify({
            type: 'warning',
            message: 'Failed to logout from Hardware Wallet!',
            caption: `${error}`,
            timeout: 10000
          })
        }
      },
      handleLogoutResponse: function (res = '') {
        this.hww.authenticated = !(res.trim() === '1')
        if (this.hww.authenticated) {
          this.$q.notify({
            type: 'warning',
            message: 'Failed to logout from Hardware Wallet',
            timeout: 10000
          })
        }
      },
      hwwExecuteDefaultCommand: function () {
        if (this.hww.authenticated) {
          this.hwwSendPsbt()
        } else {
          this.hwwShowPasswordDialog()
        }
      },
      hwwSendPsbt: async function () {
        try {
          this.hww.sendingPsbt = true
          await this.serial.writer.write(
            COMMAND_SEND_PSBT + ' ' + this.payment.psbtBase64 + '\n'
          )
          this.$q.notify({
            type: 'positive',
            message: 'Data sent to serial port device!',
            timeout: 5000
          })
        } catch (error) {
          this.$q.notify({
            type: 'warning',
            message: 'Failed to send data to serial port!',
            caption: `${error}`,
            timeout: 10000
          })
        }
      },
      handleSendPsbtResponse: function (res = '') {
        this.hww.psbtSent = true
        this.hww.sendingPsbt = false
      },
      hwwSignPsbt: async function () {
        try {
          this.hww.signingPsbt = true
          await this.serial.writer.write(COMMAND_SIGN_PSBT + '\n')
          this.$q.notify({
            type: 'positive',
            message: 'PSBT signed!',
            timeout: 5000
          })
        } catch (error) {
          this.$q.notify({
            type: 'warning',
            message: 'Failed to sign PSBT!',
            caption: `${error}`,
            timeout: 10000
          })
        }
      },
      handleSignResponse: function (res = '') {
        this.hww.signingPsbt = false
        this.updateSignedPsbt(res)
        if (this.hww.authenticated) {
          this.$q.notify({
            type: 'positive',
            message: 'Transaction Signed',
            timeout: 10000
          })
        }
      },
      hwwHelp: async function () {
        try {
          await this.serial.writer.write(COMMAND_HELP + '\n')
          this.$q.notify({
            type: 'positive',
            message: 'Check display or console for details!',
            timeout: 5000
          })
        } catch (error) {
          this.$q.notify({
            type: 'warning',
            message: 'Failed to ask for help!',
            caption: `${error}`,
            timeout: 10000
          })
        }
      },
      hwwWipe: async function () {
        try {
          this.hww.showWipeDialog = false
          await this.serial.writer.write(
            COMMAND_WIPE + ' ' + this.hww.password + '\n'
          )
        } catch (error) {
          this.$q.notify({
            type: 'warning',
            message: 'Failed to ask for help!',
            caption: `${error}`,
            timeout: 10000
          })
        } finally {
          this.hww.password = null
          this.hww.showPassword = false
        }
      },
      handleWipeResponse: function (res = '') {
        const wiped = res.trim() === '1'
        console.log('### wiped', wiped)
        if (wiped) {
          this.$q.notify({
            type: 'positive',
            message: 'Wallet wiped!',
            timeout: 10000
          })
        } else {
          this.$q.notify({
            type: 'warning',
            message: 'Failed to wipe wallet!',
            caption: `${error}`,
            timeout: 10000
          })
        }
      },
      hwwShowSeed: async function () {
        try {
          await this.serial.writer.write(COMMAND_SEED + '\n')
        } catch (error) {
          this.$q.notify({
            type: 'warning',
            message: 'Failed to show seed!',
            caption: `${error}`,
            timeout: 10000
          })
        }
      },
      hwwRestore: async function () {
        try {
          await this.serial.writer.write(
            COMMAND_RESTORE + ' ' + this.hww.mnemonic + '\n'
          )
          await this.serial.writer.write(
            COMMAND_PASSWORD + ' ' + this.hww.password + '\n'
          )
        } catch (error) {
          this.$q.notify({
            type: 'warning',
            message: 'Failed to restore from seed!',
            caption: `${error}`,
            timeout: 10000
          })
        } finally {
          this.hww.showRestoreDialog = false
          this.hww.mnemonic = null
          this.hww.showMnemonic = false
          this.hww.password = null
          this.hww.showPassword = false
        }
      },
      //################### UTXOs ###################
      scanAllAddresses: async function () {
        await this.$refs.addressList.refreshAddresses()
        this.history = []
        let addresses = this.addresses
        this.utxos.data = []
        this.utxos.total = 0
        // Loop while new funds are found on the gap adresses.
        // Use 1000 limit as a safety check (scan 20 000 addresses max)
        for (let i = 0; i < 1000 && addresses.length; i++) {
          await this.updateUtxosForAddresses(addresses)
          const oldAddresses = this.addresses.slice()
          await this.$refs.addressList.refreshAddresses()
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
        console.log('### scanAddressWithAmount1', this.addresses)
        const addresses = this.addresses.filter(a => a.hasActivity)
        console.log('### scanAddressWithAmount2', addresses)
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
      // todo: move/dedup
      getTotalSelectedUtxoAmount: function () {
        const total = this.utxos.data
          .filter(u => u.selected)
          .reduce((t, a) => t + (a.amount || 0), 0)
        return total
      },

      //################### MEMPOOL API ###################
      getAddressTxsDelayed: async function (addrData) {
        const {
          bitcoin: {addresses: addressesAPI}
        } = mempoolJS()

        const fn = async () =>
          addressesAPI.getAddressTxs({
            address: addrData.address
          })
        const addressTxs = await retryWithDelay(fn)
        return this.addressHistoryFromTxs(addrData, addressTxs)
      },

      getAddressTxsUtxoDelayed: async function (address) {
        const {
          bitcoin: {addresses: addressesAPI}
        } = mempoolJS()

        const fn = async () =>
          addressesAPI.getAddressTxsUtxo({
            address
          })
        return retryWithDelay(fn)
      },
      fetchTxHex: async function (txId) {
        const {
          bitcoin: {transactions: transactionsAPI}
        } = mempoolJS()

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

      openQrCodeDialog: function (addressData) {
        this.currentAddress = addressData
        this.addressNote = addressData.note || ''
        this.showAddress = true
      },
      searchInTab: function (tab, value) {
        this.tab = tab
        this[`${tab}Table`].filter = value
      },

      satBtc(val, showUnit = true) {
        return satOrBtc(val, showUnit, this.config.data.sats_denominated)
      },
      updateAccounts: async function (accounts) {
        this.walletAccounts = accounts
        // await this.refreshAddressesxx() // todo: automatic now?
        await this.scanAddressWithAmount()

        if (this.payment.changeWallet) {
          const changeAccount = this.walletAccounts.find(
            w => w.id === this.payment.changeWallet.id
          )
          // change account deleted
          if (!changeAccount) {
            this.payment.changeWallet = this.walletAccounts[0]
            this.selectChangeAddress(this.payment.changeWallet)
          }
        }
      },
      showAddressDetails: function (addressData) {
        this.openQrCodeDialog(addressData)
      },
      handleAddressesUpdated: async function (addresses) {
        this.addresses = addresses
        await this.scanAddressWithAmount()
      },
    },
    created: async function () {
      if (this.g.user.wallets.length) {
        // await this.$refs.addressList.refreshAddresses()
        await this.scanAddressWithAmount()
      }
    }
  })
}
watchOnly()
