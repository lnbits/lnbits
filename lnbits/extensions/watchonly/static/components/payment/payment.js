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
      'sats_denominated'
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
        paymentTab: 'destination',
        sendToList: [{address: '', amount: undefined}],
        changeWallet: null,
        changeAddress: {},
        changeAmount: 0,
        showCustomFee: false,
        showCoinSelect: false,
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
      createTx: function (excludeChange = false) {
        const tx = {
          fee_rate: this.feeRate,
          // tx_size: this.payment.txSize, ???
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

        if (excludeChange) {
          this.changeAmount = 0
        } else {
          const change = this.createChangeOutput()
          this.changeAmount = change.amount // todo: compute separately
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
        const change = this.changeAddress
        // const inputAmount = this.getTotalSelectedUtxoAmount() // todo: set amount separately
        // const payedAmount = this.getTotalPaymentAmount()
        const walletAcount =
          this.accounts.find(w => w.id === change.wallet) || {}

        return {
          address: change.address,
          // amount: inputAmount - payedAmount - this.feeValue,
          addressIndex: change.addressIndex,
          addressIndex: change.addressIndex,
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
      getTotalPaymentAmount: function () {
        return this.sendToList.reduce((t, a) => t + (a.amount || 0), 0)
      }
    },

    created: async function () {}
  })
}
