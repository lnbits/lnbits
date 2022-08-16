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
            console.log('### navigator.serial event: disconnected!')
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
          await this.writer.write(COMMAND_PASSWORD + '\n')
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
          await this.writer.write(COMMAND_WIPE + '\n')
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
          await this.writer.write(COMMAND_WIPE + '\n')
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
        await this.writer.write(COMMAND_CONFIRM_NEXT + '\n')
      },
      cancelOperation: async function () {
        try {
          await this.writer.write(COMMAND_CANCEL + '\n')
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
          await this.writer.write(
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
          await this.writer.write(COMMAND_PASSWORD_CLEAR + '\n')
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
          await this.writer.write(
            COMMAND_SEND_PSBT + ' ' + this.network + ' ' + psbtBase64 + '\n'
          )
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
          await this.writer.write(COMMAND_SIGN_PSBT + '\n')
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
        try {
          await this.writer.write(COMMAND_HELP + '\n')
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
          await this.writer.write(COMMAND_WIPE + ' ' + this.hww.password + '\n')
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
          await this.writer.write(
            COMMAND_XPUB + ' ' + this.network + ' ' + path + '\n'
          )
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
      hwwShowSeed: async function () {
        try {
          this.hww.showSeedDialog = true
          this.hww.seedWordPosition = 1
          await this.writer.write(
            COMMAND_SEED + ' ' + this.hww.seedWordPosition + '\n'
          )
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
        await this.writer.write(
          COMMAND_SEED + ' ' + this.hww.seedWordPosition + '\n'
        )
      },
      showPrevSeedWord: async function () {
        this.hww.seedWordPosition = Math.max(1, this.hww.seedWordPosition - 1)
        console.log('### this.hww.seedWordPosition', this.hww.seedWordPosition)
        await this.writer.write(
          COMMAND_SEED + ' ' + this.hww.seedWordPosition + '\n'
        )
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
          await this.writer.write(
            COMMAND_RESTORE + ' ' + this.hww.mnemonic + '\n'
          )
          await this.writer.write(
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
          this.hww.confirmedPassword = null
          this.hww.showPassword = false
        }
      },

      updateSignedPsbt: async function (value) {
        this.$emit('signed:psbt', value)
      }
    },
    created: async function () {}
  })
}
