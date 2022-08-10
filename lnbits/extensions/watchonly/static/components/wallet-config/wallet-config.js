async function walletConfig(path) {
  const t = await loadTemplateAsync(path)
  Vue.component('wallet-config', {
    name: 'wallet-config',
    template: t,

    props: ['total', 'config-data', 'adminkey'],
    data: function () {
      return {
        networOptions: ['Mainnet', 'Testnet'],
        internalConfig: {},
        show: false
      }
    },

    computed: {
      config: {
        get() {
          return this.internalConfig
        },
        set(value) {
          value.isLoaded = true
          this.internalConfig = JSON.parse(JSON.stringify(value))
          this.$emit(
            'update:config-data',
            JSON.parse(JSON.stringify(this.internalConfig))
          )
        }
      }
    },

    methods: {
      satBtc(val, showUnit = true) {
        return satOrBtc(val, showUnit, this.config.sats_denominated)
      },
      updateConfig: async function () {
        try {
          const {data} = await LNbits.api.request(
            'PUT',
            '/watchonly/api/v1/config',
            this.adminkey,
            this.config
          )
          this.show = false
          this.config = data
        } catch (error) {
          LNbits.utils.notifyApiError(error)
        }
      },
      getConfig: async function () {
        try {
          const {data} = await LNbits.api.request(
            'GET',
            '/watchonly/api/v1/config',
            this.adminkey
          )
          this.config = data
        } catch (error) {
          LNbits.utils.notifyApiError(error)
        }
      },
      deriveSecretKey: async function (privateKey, publicKey) {
        return window.crypto.subtle.deriveKey(
          {
            name: 'ECDH',
            public: publicKey
          },
          privateKey,
          {
            name: 'AES-GCM',
            length: 256
          },
          true,
          ['encrypt', 'decrypt']
        )
      },
      old: async function () {
        const alicesKeyPair = await window.crypto.subtle.generateKey(
          {
            name: 'ECDH',
            namedCurve: 'P-256'
          },
          true,
          ['deriveKey']
        )
        const bobsKeyPair = await window.crypto.subtle.generateKey(
          {
            name: 'ECDH',
            namedCurve: 'P-256'
          },
          true,
          ['deriveKey']
        )
        console.log('### alicesKeyPair', alicesKeyPair)
        console.log('### alicesKeyPair.privateKey', alicesKeyPair.privateKey)
        console.log('### alicesKeyPair.publicKey', alicesKeyPair.publicKey)
        const alicesPriveKey = await window.crypto.subtle.exportKey(
          'jwk',
          alicesKeyPair.privateKey
        )
        console.log('### alicesPriveKey', alicesPriveKey)

        const alicesPriveKeyBase64 = toStdBase64(alicesPriveKey.d)
        console.log(
          '### alicesPriveKeyBase64',
          alicesPriveKeyBase64,
          base64ToHex(alicesPriveKeyBase64)
        )

        const bobPublicKey = await window.crypto.subtle.exportKey(
          'raw',
          bobsKeyPair.publicKey
        )
        console.log('### bobPublicKey hex', buf2hex(bobPublicKey))

        // const sharedSecret01 = await this.deriveSecretKey(alicesKeyPair.privateKey, bobsKeyPair.publicKey)
        // console.log('### sharedSecret01', sharedSecret01)
        // const sharedSecret01Raw = await window.crypto.subtle.exportKey('jwk', sharedSecret01)
        // console.log('### sharedSecret01Raw', sharedSecret01Raw)

        // const sharedSecret02 = await this.deriveSecretKey(bobsKeyPair.privateKey, alicesKeyPair.publicKey)
        // console.log('### sharedSecret02', sharedSecret02)
        // const sharedSecret02Raw = await window.crypto.subtle.exportKey('jwk', sharedSecret02)
        // console.log('### sharedSecret02Raw', sharedSecret02Raw)

        const sharedSecret = nobleSecp256k1.getSharedSecret(
          alicesPriveKey,
          buf2hex(bobPublicKey)
        )
        console.log('###', getSharedSecret)
      },
      importSecretKey: async function (rawKey) {
        return window.crypto.subtle.importKey('raw', rawKey, 'AES-GCM', true, [
          'encrypt',
          'decrypt'
        ])
      }
    },

    created: async function () {
      await this.getConfig()
      //    ### in:  6bc1bee22e409f96e93d7e117393172aae2d8a571e03ac9c9eb76fac45af8e5130c81c46a35ce411e5fbc1191a0a52eff69f2445df4f9b17ad2b417be66c3710
      //    ### in2: 073059e23605fe508919d892501974905f8b5e13728db63b1b7b9326951abbe4f722c104bc82a4bcf3f1e15ede8ab7d5eb00be8c46271e1f65867f984e9cb5f1

      const alicesPrivateKey =
        '359A8CA1418C49DD26DC7D92C789AC33347F64C6B7789C666098805AF3CC60E5'

      const bobsPrivateKey =
        'AB52F1F981F639BD83F884703BC690B10DB709FF48806680A0D3FBC6475E6093'

      const alicesPublicKey = nobleSecp256k1.Point.fromPrivateKey(
        alicesPrivateKey
      )
      console.log('### alicesPublicKey', alicesPublicKey.toHex())

      const bobsPublicKey = nobleSecp256k1.Point.fromPrivateKey(bobsPrivateKey)
      console.log('### bobsPublicKey', bobsPublicKey.toHex())

      const sharedSecret = nobleSecp256k1.getSharedSecret(
        alicesPrivateKey,
        bobsPublicKey
      )

      console.log('### sharedSecret naked', sharedSecret)

      console.log(
        '### sharedSecret a',
        nobleSecp256k1.utils.bytesToHex(sharedSecret)
      )
      console.log(
        '### sharedSecret b',
        nobleSecp256k1.Point.fromHex(sharedSecret)
      )
      console.log(
        '### sharedSecret b',
        nobleSecp256k1.Point.fromHex(sharedSecret).toHex(true)
      )

      const alicesPrivateKeyBytes = nobleSecp256k1.utils.hexToBytes(
        alicesPrivateKey
      )
      const x = await this.importSecretKey(alicesPrivateKeyBytes)
      console.log('### x', x)
    }
  })
}
