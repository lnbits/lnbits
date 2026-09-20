import {txSize, satOrBtc} from '../js/utils.js'
import {mapUtxoToPsbtInput} from '../js/map.js'
import {mempoolJS} from '../js/mempool-client.js'
window.app.component('onchain-payment', {
  name: 'onchain-payment',
  template: '#onchain-payment',

  props: [
    'accounts',
    'addresses',
    'utxos',
    'mempool-endpoint',
    'sats-denominated',
    'serial-signer-ref',
    'adminkey',
    'network'
  ],
  watch: {
    accounts: {handler: 'updateChangeAddress', immediate: true},
    addresses: 'updateChangeAddress',
    feeRate() {
      this.handleOutputsChange()
    },
    utxos() {
      this.handleOutputsChange()
    }
  },

  data: function () {
    return {
      DUST_LIMIT: 546,
      tx: null,
      psbtBase64: null,
      psbtBase64Signed: null,
      signedTx: null,
      signedTxHex: null,
      sentTxId: null,
      signedTxId: null,
      sendToList: [{address: '', amount: undefined}],
      changeWallet: null,
      changeAddress: {},
      showCustomFee: false,
      showCoinSelect: false,
      showChecking: false,
      finalizing: false,
      showChange: false,
      showPsbt: false,
      showFinalTx: false,
      feeRate: 1
    }
  },

  computed: {
    isHotWallet() {
      return (
        this.accounts?.length === 1 && this.accounts[0].wallet_kind === 'hot'
      )
    },
    canReview() {
      return (
        this.utxos.some(u => u.selected) &&
        this.sendToList.length > 0 &&
        this.sendToList.every(
          o =>
            o.address &&
            !o.error &&
            Number.isSafeInteger(o.amount) &&
            o.amount >= this.DUST_LIMIT
        ) &&
        Number.isFinite(this.feeRate) &&
        this.feeRate > 0 &&
        this.selectedAmount >=
          this.totalPayedAmount + Math.ceil(this.feeRate * this.txSizeNoChange)
      )
    },
    txSize: function () {
      const tx = this.createTx()
      return Math.ceil(txSize(tx))
    },
    txSizeNoChange: function () {
      const tx = this.createTx(true)
      return Math.ceil(txSize(tx))
    },
    feeValue: function () {
      const tx = this.createTx()
      const remainder =
        this.selectedAmount -
        tx.outputs.reduce((sum, o) => sum + (o.amount || 0), 0)
      return Math.max(Math.ceil(this.feeRate * this.txSize), remainder)
    },
    selectedAmount: function () {
      return this.utxos
        .filter(utxo => utxo.selected)
        .reduce((t, a) => t + (a.amount || 0), 0)
    },
    changeAmount: function () {
      const tx = this.createTx()
      const change = tx.outputs.find(o => o.branch_index === 1)
      return change
        ? change.amount
        : Math.min(
            0,
            this.selectedAmount -
              this.totalPayedAmount -
              Math.ceil(this.feeRate * this.txSizeNoChange)
          )
    },
    balance: function () {
      return this.utxos.reduce((t, a) => t + (a.amount || 0), 0)
    },
    totalPayedAmount: function () {
      return this.sendToList.reduce((t, a) => t + (a.amount || 0), 0)
    }
  },

  methods: {
    satBtc(val, showUnit = true) {
      return satOrBtc(val, showUnit, this.satsDenominated)
    },
    clearState: function () {
      this.psbtBase64 = null
      this.psbtBase64Signed = null
      this.signedTx = null
      this.signedTxHex = null
      this.signedTxId = null
      this.sendToList = [{address: '', amount: undefined}]
      this.showChecking = false
      this.showPsbt = false
      this.showFinalTx = false
    },
    checkAndSend: async function () {
      if (this.showChecking) return
      this.showChecking = true
      try {
        if (
          this.$refs?.paymentFormRef &&
          !(await this.$refs.paymentFormRef.validate())
        )
          return
        if (this.isHotWallet) {
          await this.createPsbt()
          if (!this.psbtBase64) return
          const maxFee =
            this.tx.inputs.reduce((sum, i) => sum + i.amount, 0) -
            this.tx.outputs.reduce((sum, o) => sum + o.amount, 0)
          const {data} = await LNbits.api.request(
            'POST',
            `/onchain/api/v1/hot-wallet/${this.accounts[0].id}/sign`,
            this.adminkey,
            {transaction: this.tx, max_fee_sat: maxFee}
          )
          if (!data.tx_hex)
            throw new Error('Signing did not return a transaction')
          this.signedTx = JSON.parse(data.tx_json)
          this.signedTxHex = data.tx_hex
          this.showFinalTx = true
          return
        }
        if (!this.serialSignerRef?.isConnected()) {
          this.$q.notify({
            type: 'warning',
            message: 'Please connect to a Signing device first!',
            timeout: 10000
          })
          return
        }
        const p2trUtxo = this.utxos.find(
          u => u.selected && u.accountType === 'p2tr'
        )
        if (p2trUtxo && !this.serialSignerRef.isTaprootSupported()) {
          this.$q.notify({
            type: 'warning',
            message: 'Taproot Signing not supported for this device!',
            caption: 'Please manually deselect the Taproot UTXOs',
            timeout: 10000
          })
          return
        }
        if (!this.serialSignerRef.isAuthenticated()) {
          await this.serialSignerRef.hwwShowPasswordDialog()
          const authenticated = await this.serialSignerRef.isAuthenticating()
          if (!authenticated) return
        }

        await this.createPsbt()

        if (this.psbtBase64) {
          const txData = {
            inputs: this.tx.inputs,
            outputs: this.tx.outputs,
            feeRate: this.tx.fee_rate,
            feeValue:
              this.tx.inputs.reduce((sum, input) => sum + input.amount, 0) -
              this.tx.outputs.reduce((sum, output) => sum + output.amount, 0)
          }
          await this.serialSignerRef.hwwSendPsbt(this.psbtBase64, txData)
          await this.serialSignerRef.isSendingPsbt()
        }
      } catch (error) {
        this.$q.notify({
          type: 'warning',
          message: 'Cannot check and sign transaction!',
          caption: `${error}`,
          timeout: 10000
        })
      } finally {
        this.showChecking = this.finalizing
        this.psbtBase64 = null
      }
    },
    showPsbtDialog: async function () {
      if (this.showChecking) return
      this.showChecking = true
      try {
        const valid = await this.$refs.paymentFormRef.validate()
        if (!valid) return

        const data = await this.createPsbt()
        if (data) {
          this.showPsbt = true
        }
      } catch (error) {
        this.$q.notify({
          type: 'warning',
          message: 'Failed to create PSBT!',
          caption: `${error}`,
          timeout: 10000
        })
      } finally {
        this.showChecking = false
      }
    },
    createPsbt: async function () {
      this.psbtBase64 = null
      try {
        this.signedTx = null
        this.signedTxHex = null
        this.showFinalTx = false
        this.tx = this.createTx()
        const changeOutput = this.tx.outputs.find(o => o.branch_index === 1)
        if (changeOutput) changeOutput.amount = this.changeAmount
        if (this.canReview === false)
          throw new Error('Check recipients, amounts, available coins and fee')
        for (const input of this.tx.inputs) {
          input.tx_hex = await this.fetchTxHex(input.tx_id)
        }

        const {data} = await LNbits.api.request(
          'POST',
          '/onchain/api/v1/psbt',
          this.adminkey,
          this.tx
        )

        this.psbtBase64 = data
        return data
      } catch (err) {
        LNbits.utils.notifyApiError(err)
      }
    },
    createTx: function (excludeChange = false) {
      const tx = {
        fee_rate: this.feeRate,
        masterpubs: this.accounts.map(w => ({
          id: w.id,
          public_key: w.masterpub,
          fingerprint: w.fingerprint
        }))
      }
      tx.inputs = this.utxos
        .filter(utxo => utxo.selected)
        .map(mapUtxoToPsbtInput)
        .sort((a, b) =>
          a.tx_id < b.tx_id ? -1 : a.tx_id > b.tx_id ? 1 : a.vout - b.vout
        )

      tx.outputs = this.sendToList.map(out => ({
        address: out.address,
        amount: out.amount
      }))

      if (!excludeChange) {
        const change = this.createChangeOutput()
        const remainder = this.selectedAmount - this.totalPayedAmount
        const withChange = {...tx, outputs: [...tx.outputs, change]}
        const changeValue =
          remainder - Math.ceil(this.feeRate * txSize(withChange))
        if (changeValue >= this.DUST_LIMIT) {
          if (!change.address)
            throw new Error('No unused change address is available')
          change.amount = changeValue
          tx.outputs.push(change)
        }
      }
      tx.tx_size = Math.ceil(txSize(tx))
      tx.inputs = _.shuffle(tx.inputs)
      tx.outputs = _.shuffle(tx.outputs)

      return tx
    },
    createChangeOutput: function () {
      const change = this.changeAddress
      const walletAcount = this.accounts.find(w => w.id === change.wallet) || {
        meta: {}
      }

      return {
        address: change.address,
        address_index: change.addressIndex,
        branch_index: change.isChange ? 1 : 0,
        wallet: walletAcount.id,
        accountPath: walletAcount.meta.accountPath,
        accountType: walletAcount.type
      }
    },
    selectChangeAddress: function (account) {
      if (!account) {
        this.changeAddress = {}
        return
      }
      this.changeAddress =
        this.addresses.find(
          a => a.wallet === account.id && a.isChange && !a.hasActivity
        ) || {}
    },
    updateChangeAddress: function () {
      if (this.changeWallet) {
        const changeAccount = (this.accounts || []).find(
          w => w.id === this.changeWallet.id
        )
        // change account deleted
        if (!changeAccount) {
          this.changeWallet = this.accounts[0]
        }
      } else {
        this.changeWallet = this.accounts[0]
      }
      this.selectChangeAddress(this.changeWallet)
    },
    updateSignedPsbt: async function (psbtBase64) {
      if (this.finalizing) return
      try {
        this.finalizing = true
        this.showChecking = true
        this.psbtBase64Signed = psbtBase64
        this.showFinalTx = false
        this.signedTx = null
        this.signedTxHex = null

        const data = await this.extractTxFromPsbt(psbtBase64)
        if (data?.tx_hex) {
          this.signedTx = JSON.parse(data.tx_json)
          this.signedTxHex = data.tx_hex
          this.showFinalTx = true
        }
      } finally {
        this.finalizing = false
        this.showChecking = false
      }
    },
    updateSignedTx: async function (txData) {
      if (this.finalizing) return
      try {
        this.finalizing = true
        this.showChecking = true
        this.showFinalTx = false
        this.signedTx = null
        this.signedTxHex = null

        const data = await this.extractTx(txData.serializedTx)
        if (data) {
          this.signedTx = data.tx_json
          this.signedTx.fee = txData.feeValue
          this.signedTxHex = txData.serializedTx
          this.showFinalTx = true
        }
      } finally {
        this.finalizing = false
        this.showChecking = false
      }
    },

    fetchUtxoHexForPsbt: async function (psbtBase64, expectedPsbtBase64) {
      if (expectedPsbtBase64 && this.tx?.inputs?.length) return this.tx.inputs

      const {data: psbtUtxos} = await LNbits.api.request(
        'PUT',
        '/onchain/api/v1/psbt/utxos',
        this.adminkey,
        {psbtBase64}
      )

      const inputs = []
      for (const utxo of psbtUtxos) {
        const txHex = await this.fetchTxHex(utxo.tx_id)
        inputs.push({tx_hex: txHex})
      }
      return inputs
    },
    extractTxFromPsbt: async function (psbtBase64) {
      try {
        // Capture before awaiting: the hardware signing call clears psbtBase64.
        const expectedPsbtBase64 = this.psbtBase64 || undefined
        const inputs = await this.fetchUtxoHexForPsbt(
          psbtBase64,
          expectedPsbtBase64
        )

        const {data} = await LNbits.api.request(
          'PUT',
          '/onchain/api/v1/psbt/extract',
          this.adminkey,
          {
            psbtBase64,
            expectedPsbtBase64,
            inputs,
            network: this.network
          }
        )
        return data
      } catch (error) {
        this.$q.notify({
          type: 'warning',
          message: 'Cannot finalize PSBT!',
          caption: `${error}`,
          timeout: 10000
        })
        LNbits.utils.notifyApiError(error)
      }
    },
    extractTx: async function (txHex) {
      try {
        const {data} = await LNbits.api.request(
          'PUT',
          '/onchain/api/v1/tx/extract',
          this.adminkey,
          {
            tx_hex: txHex,
            network: this.network
          }
        )
        return data
      } catch (error) {
        this.$q.notify({
          type: 'warning',
          message: 'Cannot extract transaction for tx hex!',
          caption: `${error}`,
          timeout: 10000
        })
        LNbits.utils.notifyApiError(error)
      }
    },
    broadcastTransaction: async function () {
      if (!this.signedTxHex || this.showChecking) return
      this.showChecking = true
      try {
        const {data} = await LNbits.api.request(
          'POST',
          '/onchain/api/v1/tx',
          this.adminkey,
          {tx_hex: this.signedTxHex, network: this.network}
        )
        this.sentTxId = data

        this.$q.notify({
          type: 'positive',
          message: 'Transaction broadcasted!',
          caption: `${data}`,
          timeout: 10000
        })

        this.clearState()
        this.$emit('broadcast-done', this.sentTxId)
      } catch (error) {
        this.sentTxId = null
        this.$q.notify({
          type: 'warning',
          message: 'Failed to broadcast!',
          caption: `${error}`,
          timeout: 10000
        })
      } finally {
        this.showChecking = false
      }
    },
    fetchTxHex: async function (txId) {
      const {
        bitcoin: {transactions: transactionsAPI}
      } = mempoolJS({
        hostname: this.mempoolEndpoint
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
    handleOutputsChange: function () {
      if (!this.$refs.utxoList || this.showChecking) return
      for (let i = 0; i <= this.utxos.length; i++) {
        const before = this.selectedAmount
        this.$refs.utxoList.refreshUtxoSelection(
          this.totalPayedAmount + Math.ceil(this.feeRate * this.txSize)
        )
        if (before === this.selectedAmount) break
      }
    },
    sendMaximum(output) {
      if (this.showChecking) return
      this.$refs.utxoList.utxoSelectionMode = 'Select All'
      this.utxos.forEach(u => {
        u.selected = true
      })
      const others = this.totalPayedAmount - (output.amount || 0)
      output.amount = Math.max(
        0,
        this.selectedAmount -
          others -
          Math.ceil(this.feeRate * this.txSizeNoChange)
      )
    },
    getTotalPaymentAmount: function () {
      return this.sendToList.reduce((t, a) => t + (a.amount || 0), 0)
    }
  },

  mounted() {
    this.handleOutputsChange()
  }
})
