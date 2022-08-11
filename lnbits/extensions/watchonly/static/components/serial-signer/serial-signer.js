async function serialSigner(path) {
  const t = await loadTemplateAsync(path)
  Vue.component('serial-signer', {
    name: 'serial-signer',
    template: t,

    props: ['sats-denominated', 'network'],
    data: function () {
      return {
        selectedPort: null,
        writableStreamClosed: null,
        writer: null,
        readableStreamClosed: null,
        reader: null,
        receivedData: '',
        config: {},
        decryptionKey: null,
        dheKey: null, // todo: store in secure local storage

        hww: {
          password: null,
          showPassword: false,
          mnemonic: null,
          showMnemonic: false,
          authenticated: false,
          showPasswordDialog: false,
          showConfigDialog: false,
          showWipeDialog: false,
          showRestoreDialog: false,
          showConfirmationDialog: false,
          showSignedPsbt: false,
          sendingPsbt: false,
          signingPsbt: false,
          loginResolve: null,
          psbtSentResolve: null,
          xpubResolve: null,
          seedWordPosition: 1,
          showSeedDialog: false,
          confirm: {
            outputIndex: 0,
            showFee: false
          }
        },
        tx: null, // todo: move to hww

        showConsole: false
      }
    },

    methods: {
      satBtc(val, showUnit = true) {
        return satOrBtc(val, showUnit, this.satsDenominated)
      },
      openSerialPortDialog: async function () {
        await this.openSerialPort()
      },
      openSerialPort: async function (config = {baudRate: 9600}) {
        if (!this.checkSerialPortSupported()) return false
        if (this.selectedPort) {
          this.$q.notify({
            type: 'warning',
            message: 'Already connected. Disconnect first!',
            timeout: 10000
          })
          return true
        }

        try {
          navigator.serial.addEventListener('connect', event => {
            console.log('### navigator.serial event: connected!', event)
          })

          navigator.serial.addEventListener('disconnect', () => {
            console.log('### navigator.serial event: disconnected!', event)
            this.selectedPort = null
            this.hww.authenticated = false
            this.$q.notify({
              type: 'warning',
              message: 'Disconnected from Serial Port!',
              timeout: 10000
            })
          })
          this.selectedPort = await navigator.serial.requestPort()
          // Wait for the serial port to open.
          await this.selectedPort.open(config)
          this.startSerialPortReading()

          const textEncoder = new TextEncoderStream()
          this.writableStreamClosed = textEncoder.readable.pipeTo(
            this.selectedPort.writable
          )

          this.writer = textEncoder.writable.getWriter()
          return true
        } catch (error) {
          this.selectedPort = null
          this.$q.notify({
            type: 'warning',
            message: 'Cannot open serial port!',
            caption: `${error}`,
            timeout: 10000
          })
          return false
        }
      },
      openSerialPortConfig: async function () {
        this.hww.showConfigDialog = true
      },
      closeSerialPort: async function () {
        try {
          if (this.writer) this.writer.close()
          if (this.writableStreamClosed) await this.writableStreamClosed
          if (this.reader) this.reader.cancel()
          if (this.readableStreamClosed)
            await this.readableStreamClosed.catch(() => {
              /* Ignore the error */
            })
          if (this.selectedPort) await this.selectedPort.close()
          this.$q.notify({
            type: 'positive',
            message: 'Serial port disconnected!',
            timeout: 5000
          })
        } catch (error) {
          this.$q.notify({
            type: 'warning',
            message: 'Cannot close serial port!',
            caption: `${error}`,
            timeout: 10000
          })
        } finally {
          this.selectedPort = null
          this.hww.authenticated = false
        }
      },

      isConnected: function () {
        return !!this.selectedPort
      },
      isAuthenticated: function () {
        return this.hww.authenticated
      },
      isAuthenticating: function () {
        if (this.isAuthenticated()) return false
        return new Promise(resolve => {
          this.loginResolve = resolve
        })
      },

      isSendingPsbt: async function () {
        if (!this.hww.sendingPsbt) return false
        return new Promise(resolve => {
          this.psbtSentResolve = resolve
        })
      },

      isFetchingXpub: async function () {
        return new Promise(resolve => {
          this.xpubResolve = resolve
        })
      },

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
      startSerialPortReading: async function () {
        const port = this.selectedPort

        while (port && port.readable) {
          const textDecoder = new TextDecoderStream()
          this.readableStreamClosed = port.readable.pipeTo(textDecoder.writable)
          this.reader = textDecoder.readable.getReader()
          const readStringUntil = readFromSerialPort(this.reader)

          try {
            while (true) {
              const {value, done} = await readStringUntil('\n')
              if (value) {
                this.handleSerialPortResponse(value)
                this.updateSerialPortConsole(value)
              }
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
      },
      handleSerialPortResponse: function (value) {
        const command = value.split(' ')[0]
        const commandData = value.substring(command.length).trim()

        switch (command) {
          case COMMAND_SIGN_PSBT:
            this.handleSignResponse(commandData)
            break
          case COMMAND_PASSWORD:
            this.handleLoginResponse(commandData)
            break
          case COMMAND_PASSWORD_CLEAR:
            this.handleLogoutResponse(commandData)
            break
          case COMMAND_SEND_PSBT:
            this.handleSendPsbtResponse(commandData)
            break
          case COMMAND_WIPE:
            this.handleWipeResponse(commandData)
            break
          case COMMAND_XPUB:
            this.handleXpubResponse(commandData)
            break
          case COMMAND_DH_EXCHANGE:
            this.handleDhExchangeResponse(commandData)
            break
          default:
            console.log('### console', value)
        }
      },
      updateSerialPortConsole: function (value) {
        this.receivedData += value + '\n'
        const textArea = document.getElementById('serial-port-console')
        if (textArea) textArea.scrollTop = textArea.scrollHeight
      },
      hwwShowPasswordDialog: async function () {
        try {
          this.hww.showPasswordDialog = true
          await this.sendCommandSecure(COMMAND_PASSWORD)
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
          await this.sendCommandSecure(COMMAND_WIPE)
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
          await this.sendCommandSecure(COMMAND_WIPE)
        } catch (error) {
          this.$q.notify({
            type: 'warning',
            message: 'Failed to connect to Hardware Wallet!',
            caption: `${error}`,
            timeout: 10000
          })
        }
      },
      hwwConfirmNext: async function () {
        this.hww.confirm.outputIndex += 1
        if (this.hww.confirm.outputIndex >= this.tx.outputs.length) {
          this.hww.confirm.showFee = true
        }
        await this.sendCommandSecure(COMMAND_CONFIRM_NEXT)
      },
      cancelOperation: async function () {
        try {
          await this.sendCommandSecure(COMMAND_CANCEL)
        } catch (error) {
          this.$q.notify({
            type: 'warning',
            message: 'Failed to send cancel!',
            caption: `${error}`,
            timeout: 10000
          })
        }
      },
      hwwConfigAndConnect: async function () {
        this.hww.showConfigDialog = false
        const config = this.$refs.serialPortConfig.getConfig()
        await this.openSerialPort(config)
        return true
      },
      hwwLogin: async function () {
        try {
          await this.sendCommandSecure(COMMAND_PASSWORD, [this.hww.password])
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
        if (this.loginResolve) {
          this.loginResolve(this.hww.authenticated)
        }

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
          await this.sendCommandSecure(COMMAND_PASSWORD_CLEAR)
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
      hwwSendPsbt: async function (psbtBase64, tx) {
        try {
          this.tx = tx
          this.hww.sendingPsbt = true
          await this.sendCommandSecure(COMMAND_SEND_PSBT, [this.network, psbtBase64])
          this.$q.notify({
            type: 'positive',
            message: 'Data sent to serial port device!',
            timeout: 5000
          })
        } catch (error) {
          this.hww.sendingPsbt = false
          this.$q.notify({
            type: 'warning',
            message: 'Failed to send data to serial port!',
            caption: `${error}`,
            timeout: 10000
          })
        }
      },
      handleSendPsbtResponse: function (res = '') {
        try {
          const psbtOK = res.trim() === '1'
          if (!psbtOK) {
            this.$q.notify({
              type: 'warning',
              message: 'Failed to send PSBT!',
              caption: `${res}`,
              timeout: 10000
            })
            return
          }
          this.hww.confirm.outputIndex = 0
          this.hww.showConfirmationDialog = true
          this.hww.confirm = {
            outputIndex: 0,
            showFee: false
          }
          this.hww.sendingPsbt = false
        } catch (error) {
          this.$q.notify({
            type: 'warning',
            message: 'Failed to send PSBT!',
            caption: `${error}`,
            timeout: 10000
          })
        } finally {
          this.psbtSentResolve()
        }
      },
      hwwSignPsbt: async function () {
        try {
          this.hww.showConfirmationDialog = false
          this.hww.signingPsbt = true
          await this.sendCommandSecure(COMMAND_SIGN_PSBT)
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
        const [count, psbt] = res.trim().split(' ')
        if (!psbt || !count || count.trim() === '0') {
          this.$q.notify({
            type: 'warning',
            message: 'No input signed!',
            caption: 'Are you using the right seed?',
            timeout: 10000
          })
          return
        }
        this.updateSignedPsbt(psbt)
        this.$q.notify({
          type: 'positive',
          message: 'Transaction Signed',
          message: `Inputs signed: ${count}`,
          timeout: 10000
        })
      },
      hwwHelp: async function () {
        // const sharedSecret =
        //   'f96c85875055a5586688fea4cf7c4a2bd9541ffcf34f9d663d97e0cf2f6af4af'
        // const sharedSecretBytes = hexToBytes(sharedSecret)
        // // console.log('### sharedSecret', sharedSecret)
        // const key = await window.crypto.subtle.importKey(
        //   'raw',
        //   sharedSecretBytes,
        //   {
        //     name: 'AES-CBC',
        //     length: 256
        //   },
        //   true,
        //   ['encrypt', 'decrypt']
        // )
        // d2b9e5e3ff8945236455424e9e25590b8264f13c7484862cca4f5b7b8bf8f1686d218b4f1aacdc27a1df71fa4b530adfd6c8cae6bd926d3f8be8ff55ee4358d1a32569e9f5263ffae7d0eaf413788498
        // xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
        // 6bc1bee22e409f96e93d7e117393172aae2d8a571e03ac9c9eb76fac45af8e5130c81c46a35ce411e5fbc1191a0a52eff69f2445df4f9b17ad2b417be66c3710
        // 8f13a7763f021d7701f4100631f6c3d80576fcd0e3718b2594ceb7b910ceed29a334d1019dd6f0ffdba5b6be8c11637d6124d7adbd29c88af13800cb1f980f7d

        // const message =
        //   'TextMustBe16ByteTextMustBe16ByteTextMustBe16ByteTextMustBe16Byte'
        // const encoded = asciiToUint8Array(message)
        // const encrypted = await encryptMessage(key, encoded)
        // const encryptedHex = bytesToHex(encrypted)
        // console.log('### encrypted hex: ', encryptedHex)

        // const encryptedHex2 = await encryptMessage2(sharedSecretBytes, message)
        // console.log('### encryptedHex2', encryptedHex2)

        // const decrypted = await decryptMessage(key, encrypted)
        // console.log(
        //   '### decrypted hex: ',
        //   bytesToHex(new Uint8Array(decrypted))
        // )
        // console.log(
        //   '### decrypted ascii: ',
        //   new TextDecoder().decode(new Uint8Array(decrypted))
        // )

        try {
          this.decryptionKey = nobleSecp256k1.utils.randomPrivateKey()
          const publicKey = nobleSecp256k1.Point.fromPrivateKey(
            this.decryptionKey
          )
          const publicKeyHex = publicKey.toHex().slice(2)
          console.log('### publicKeyHex:', publicKeyHex)
          await this.writer.write(
            COMMAND_DH_EXCHANGE + ' ' + publicKeyHex + '\n'
          )
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
          await this.sendCommandSecure(COMMAND_WIPE, [this.hww.password])
        } catch (error) {
          this.$q.notify({
            type: 'warning',
            message: 'Failed to ask for help!',
            caption: `${error}`,
            timeout: 10000
          })
        } finally {
          this.hww.password = null
          this.hww.confirmedPassword = null
          this.hww.showPassword = false
        }
      },
      handleWipeResponse: function (res = '') {
        const wiped = res.trim() === '1'
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
      hwwXpub: async function (path) {
        try {
          console.log(
            '### hwwXpub',
            COMMAND_XPUB + ' ' + this.network + ' ' + path
          )

          await this.sendCommandSecure(COMMAND_XPUB, [this.network, path])
        } catch (error) {
          this.$q.notify({
            type: 'warning',
            message: 'Failed to fetch XPub!',
            caption: `${error}`,
            timeout: 10000
          })
        }
      },
      handleXpubResponse: function (res = '') {
        const args = res.trim().split(' ')
        if (args.length < 3 || args[0].trim() !== '1') {
          this.$q.notify({
            type: 'warning',
            message: 'Failed to fetch XPub!',
            caption: `${res}`,
            timeout: 10000
          })
          this.xpubResolve({})
          return
        }
        const xpub = args[1].trim()
        const fingerprint = args[2].trim()
        this.xpubResolve({xpub, fingerprint})
      },
      handleDhExchangeResponse: async function (res = '') {
        console.log('### handleDhExchangeResponse', res)
        const [pubKeyHex, fingerprint] = res.trim().split(' ')
        if (!pubKeyHex) {
          this.$q.notify({
            type: 'warning',
            message: 'Failed to exchange DH secret!',
            caption: `${res}`,
            timeout: 10000
          })

          return
        }
        const hwwPublicKey = nobleSecp256k1.Point.fromHex('04' + pubKeyHex)

        const sharedSecret = nobleSecp256k1.getSharedSecret(
          this.decryptionKey,
          hwwPublicKey
        ).slice(1, 33)
        console.log(
          '### sharedSecret',
          nobleSecp256k1.utils.bytesToHex(sharedSecret)
        )
        this.dheKey = await window.crypto.subtle.importKey(
          'raw',
          sharedSecret,
          {
            name: 'AES-CBC',
            length: 256
          },
          true,
          ['encrypt', 'decrypt']
        )
      },
      hwwShowSeed: async function () {
        try {
          this.hww.showSeedDialog = true
          this.hww.seedWordPosition = 1

          await this.sendCommandSecure(COMMAND_SEED, [this.hww.seedWordPosition])
        } catch (error) {
          this.$q.notify({
            type: 'warning',
            message: 'Failed to show seed!',
            caption: `${error}`,
            timeout: 10000
          })
        }
      },
      showNextSeedWord: async function () {
        this.hww.seedWordPosition++
        await this.sendCommandSecure(COMMAND_SEED, [this.hww.seedWordPosition])
      },
      showPrevSeedWord: async function () {
        this.hww.seedWordPosition = Math.max(1, this.hww.seedWordPosition - 1)
        await this.sendCommandSecure(COMMAND_SEED, [this.hww.seedWordPosition])
      },
      handleShowSeedResponse: function (res = '') {
        const args = res.trim().split(' ')
        if (args.length < 2 || args[0].trim() !== '1') {
          this.$q.notify({
            type: 'warning',
            message: 'Failed to show seed!',
            caption: `${res}`,
            timeout: 10000
          })
          return
        }
      },
      hwwRestore: async function () {
        try {
          await this.sendCommandSecure(COMMAND_RESTORE, [this.hww.mnemonic])
          await this.sendCommandSecure(COMMAND_PASSWORD, [this.hww.password])
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
          this.hww.confirmedPassword = null
          this.hww.showPassword = false
        }
      },

      updateSignedPsbt: async function (value) {
        this.$emit('signed:psbt', value)
      },

      sendCommandSecure: async function (command, attrs = []) {
        const message = [command].concat(attrs).join(' ')

        const encodedMessage = asciiToUint8Array(message.length + ' ' + message)
        const encrypted = await encryptMessage(this.dheKey, encodedMessage)

        const encryptedHex = nobleSecp256k1.utils.bytesToHex(encrypted)
        console.log('### encrypted hex: ', encryptedHex)

        await this.writer.write(encryptedHex + '\n')
      }
    },
    created: async function () {
      console.log('### nobleSecp256k1.utils', nobleSecp256k1.utils)
    }
  })
}
