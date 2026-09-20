import {
  mapDerivationPathToTrezor,
  mapOutputAccountTypeToTrezor,
  mapInputAccountTypeToTrezor
} from '../js/map.js'
window.app.component('onchain-trezor-signer', {
  name: 'onchain-trezor-signer',
  template: '#onchain-trezor-signer',
  props: ['sats-denominated', 'network'],
  data: function () {
    return {
      features: null,
      featuresJson: null,
      showFeatures: false,
      connected: false,
      isConnecting: false,
      xpubData: {xpub: null, fingerprint: null}
    }
  },

  methods: {
    connectToDevice: async function () {
      if (this.isConnecting) return
      try {
        this.isConnecting = true
        if (typeof TrezorConnect === 'undefined') {
          await LNbits.utils.loadScript(
            '/onchain/static/js/lib/trezor-web-connect.js'
          )
          window.TrezorConnect = window.trezor.default
          await TrezorConnect.init({
            lazyLoad: true,
            manifest: {email: 'vlad@lnbits.com', appUrl: 'https://lnbits.com'}
          })
        }
        this.features = await TrezorConnect.getFeatures()
        if (!this.features.success)
          throw new Error('Trezor connection was cancelled or failed')
        this.featuresJson = JSON.stringify(this.features, null, 2)
        this.showFeatures = false
        this.connected = true
        this.$emit('device:connected', 'trezor-device')
      } catch (err) {
        this.showFeatures = false
        this.connected = false
      } finally {
        this.isConnecting = false
      }
    },

    isConnected: function () {
      return this.connected
    },
    isTaprootSupported: function () {
      return true
    },
    isAuthenticated: function () {
      return true
    },
    hwwXpub: async function (accountPath) {
      const coin = this.network === 'Mainnet' ? 'btc' : 'test'
      const data = await TrezorConnect.getPublicKey({
        path: accountPath,
        showOnTrezor: true,
        coin
      })
      if (!data.success) {
        throw new Error(data.payload.error)
      }
      this.xpubData = {
        xpub: data.payload.xpub,
        fingerprint: data.payload.fingerprint.toString(16).padStart(8, '0')
      }
    },
    isFetchingXpub: async function () {
      return this.xpubData
    },
    hwwSendPsbt: async function (_, txData) {
      const coin = this.network === 'Mainnet' ? 'btc' : 'test'
      const inputs = txData.inputs.map(input => ({
        address_n: mapDerivationPathToTrezor(
          `${input.accountPath}/${input.branch_index}/${input.address_index}`
        ),
        prev_index: input.vout,
        prev_hash: input.tx_id,
        amount: input.amount,
        script_type: mapInputAccountTypeToTrezor(input.accountType)
      }))
      const outputs = txData.outputs.map(out => {
        const o = {
          amount: out.amount,
          script_type: 'PAYTOADDRESS'
        }
        if (out.accountPath) {
          o.address_n = mapDerivationPathToTrezor(
            `${out.accountPath}/${out.branch_index}/${out.address_index}`
          )
        } else {
          o.address = out.address
        }
        if (out.accountType) {
          o.script_type = mapOutputAccountTypeToTrezor(out.accountType)
        }
        return o
      })
      const tx = {
        coin,
        inputs,
        outputs
      }
      const data = await TrezorConnect.signTransaction(tx)
      if (!data.success) {
        throw new Error(data.payload.error)
      }
      this.$emit('signed:tx', {
        serializedTx: data.payload.serializedTx,
        feeValue: txData.feeValue
      })
    },
    hwwShowAddress: async function (path, expectedAddress) {
      const result = await TrezorConnect.getAddress({
        path,
        coin: this.network === 'Mainnet' ? 'btc' : 'test',
        showOnTrezor: true
      })
      if (!result.success || result.payload.address !== expectedAddress)
        throw new Error('Device address does not match this wallet')
    },
    isSendingPsbt: function () {
      return false
    },
    hwwShowPasswordDialog: function () {}
  },

  created: async function () {}
})
