async function payment(path) {
  const t = await loadTemplateAsync(path)
  Vue.component('payment', {
    name: 'payment',
    template: t,

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
      immediate: true,
      accounts() {
        this.updateChangeAddress()
      },
      addresses() {
        this.updateChangeAddress()
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
        showChange: false,
        showPsbt: false,
        showFinalTx: false,
        feeRate: 1
      }
    },

    computed: {
      txSize: function () {
        const tx = this.createTx()
        return Math.round(txSize(tx))
      },
      txSizeNoChange: function () {
        const tx = this.createTx(true)
        return Math.round(txSize(tx))
      },
      feeValue: function () {
        return this.feeRate * this.txSize
      },
      selectedAmount: function () {
        return this.utxos
          .filter(utxo => utxo.selected)
          .reduce((t, a) => t + (a.amount || 0), 0)
      },
      changeAmount: function () {
        return (
          this.selectedAmount -
          this.totalPayedAmount -
          this.feeRate * this.txSize
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
        this.showChecking = true
        try {
          if (!this.serialSignerRef.isConnected()) {
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
          if (p2trUtxo) {
            this.$q.notify({
              type: 'warning',
              message: 'Taproot Signing not supported yet!',
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
              outputs: this.tx.outputs,
              feeRate: this.tx.fee_rate,
              feeValue: this.feeValue
            }
            await this.serialSignerRef.hwwSendPsbt(this.psbtBase64, txData)
            await this.serialSignerRef.isSendingPsbt()
          }
        } catch (error) {
          this.$q.notify({
            type: 'warning',
            message: 'Cannot check and sign PSBT!',
            caption: `${error}`,
            timeout: 10000
          })
        } finally {
          this.showChecking = false
          this.psbtBase64 = null
        }
      },
      showPsbtDialog: async function () {
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
        }
      },
      createPsbt: async function () {
        try {
          this.tx = this.createTx()
          for (const input of this.tx.inputs) {
            input.tx_hex = await this.fetchTxHex(input.tx_id)
          }

          const changeOutput = this.tx.outputs.find(o => o.branch_index === 1)
          if (changeOutput) changeOutput.amount = this.changeAmount

          const {data} = await LNbits.api.request(
            'POST',
            '/watchonly/api/v1/psbt',
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
          const diffAmount = this.selectedAmount - this.totalPayedAmount
          if (diffAmount >= this.DUST_LIMIT) {
            tx.outputs.push(change)
          }
        }
        tx.tx_size = Math.round(txSize(tx))
        tx.inputs = _.shuffle(tx.inputs)
        tx.outputs = _.shuffle(tx.outputs)

        return tx
      },
      createChangeOutput: function () {
        const change = this.changeAddress
        const walletAcount =
          this.accounts.find(w => w.id === change.wallet) || {}

        return {
          address: change.address,
          address_index: change.addressIndex,
          branch_index: change.isChange ? 1 : 0,
          wallet: walletAcount.id
        }
      },
      selectChangeAddress: function (account) {
        if (!account) this.changeAddress = ''
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
        try {
          this.showChecking = true
          this.psbtBase64Signed = psbtBase64

          const data = await this.extractTxFromPsbt(psbtBase64)
          this.showFinalTx = true
          if (data) {
            this.signedTx = JSON.parse(data.tx_json)
            this.signedTxHex = data.tx_hex
          } else {
            this.signedTx = null
            this.signedTxHex = null
          }
        } finally {
          this.showChecking = false
        }
      },
      extractTxFromPsbt: async function (psbtBase64) {
        try {
          const {data} = await LNbits.api.request(
            'PUT',
            '/watchonly/api/v1/psbt/extract',
            this.adminkey,
            {
              psbtBase64,
              inputs: this.tx.inputs,
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
      broadcastTransaction: async function () {
        try {
          const {data} = await LNbits.api.request(
            'POST',
            '/watchonly/api/v1/tx',
            this.adminkey,
            {tx_hex: this.signedTxHex}
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
          this.showFinalTx = false
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
        this.$refs.utxoList.refreshUtxoSelection(this.totalPayedAmount)
      },
      getTotalPaymentAmount: function () {
        return this.sendToList.reduce((t, a) => t + (a.amount || 0), 0)
      }
    },

    created: async function () {}
  })
}
