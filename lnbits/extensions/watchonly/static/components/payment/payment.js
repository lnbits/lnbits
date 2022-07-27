async function payment(path) {
  const t = await loadTemplateAsync(path)
  Vue.component('payment', {
    name: 'payment',
    template: t,

    props: [
      'accounts',
      'addresses',
      'utxos',
      'mempool_endpoint',
      'sats_denominated',
      'serial-signer-ref',
      'adminkey'
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
        paymentTab: 'destination',
        sendToList: [{address: '', amount: undefined}],
        changeWallet: null,
        changeAddress: {},
        showCustomFee: false,
        showCoinSelect: false,
        showChecking: false,
        showChange: false,
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
          this.feeRate * this.txSizeNoChange
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
        return satOrBtc(val, showUnit, this['sats_denominated'])
      },
      checkAndSend: async function () {
        this.showChecking = true
        try {
          if (!this.serialSignerRef.isConnected()) {
            await this.serialSignerRef.openSerialPort()
            return
          }
          if (!this.serialSignerRef.isAuthenticated()) {
            await this.serialSignerRef.hwwShowPasswordDialog()
            return
          }

          await this.createPsbt()

          if (this.psbtBase64) {
            await this.serialSignerRef.hwwSendPsbt(this.psbtBase64)
            await this.serialSignerRef.isSendingPsbt()
          }

          console.log('### hwwSendPsbt')
        } catch (error) {
        } finally {
          this.showChecking = false
          this.psbtBase64 = null
        }
      },
      createPsbt: async function () {
        try {
          console.log('### this.createPsbt')
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
        } catch (err) {
          LNbits.utils.notifyApiError(err)
        }
      },
      createTx: function (excludeChange = false) {
        const tx = {
          fee_rate: this.feeRate,
          masterpubs: this.accounts.map(w => ({
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
          if (this.changeAmount >= this.DUST_LIMIT) {
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
          masterpub_fingerprint: walletAcount.fingerprint
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
        console.log('### payment updateSignedPsbt psbtBase64', psbtBase64)

        const data = await this.extractTxFromPsbt(psbtBase64)
        if (data) {
          this.signedTx = JSON.parse(data.tx_json)
          this.signedTxHex = data.tx_hex
        } else {
          this.signedTx = null
          this.signedTxHex = null
        }
      },
      extractTxFromPsbt: async function (psbtBase64) {
        console.log('### extractTxFromPsbt psbtBase64', psbtBase64)
        try {
          const {data} = await LNbits.api.request(
            'PUT',
            '/watchonly/api/v1/psbt/extract',
            this.adminkey,
            {
              psbtBase64,
              inputs: this.tx.inputs
            }
          )
          console.log('### extractTxFromPsbt data', data)
          return data
        } catch (error) {
          console.log('### error', error)
          this.$q.notify({
            type: 'warning',
            message: 'Cannot finalize PSBT!',
            timeout: 10000
          })
          LNbits.utils.notifyApiError(error)
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
      fetchTxHex: async function (txId) {
        const {
          bitcoin: {transactions: transactionsAPI}
        } = mempoolJS() // todo: hostname

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
