async function serialSigner(path) {
  const t = await loadTemplateAsync(path)
  Vue.component('serial-signer', {
    name: 'serial-signer',
    template: t,

    props: [],
    data: function () {
      return {
        selectedPort: null,
        writableStreamClosed: null,
        writer: null,
        readableStreamClosed: null,
        reader: null,
        showAdvancedConfig: false,
        receivedData: '',
        config: {},
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
        }
      }
    },

    methods: {
      toggleSerialPortConection: async function () {
        if (!this.selectedPort) {
          this.openSerialPort()
        } else {
          this.closeSerialPort()
        }
      },
      openSerialPort: async function () {
        if (!this.checkSerialPortSupported()) return
        console.log('### openSerialPort', this.selectedPort)
        try {
          navigator.serial.addEventListener('connect', event => {
            console.log('### navigator.serial event: connected!', event)
          })

          navigator.serial.addEventListener('disconnect', () => {
            console.log('### navigator.serial event: disconnected!', event)
            this.hww.authenticated = false
            this.$q.notify({
              type: 'warning',
              message: 'Disconnected from Serial Port!',
              timeout: 10000
            })
          })
          this.selectedPort = await navigator.serial.requestPort()
          // Wait for the serial port to open.
          await this.selectedPort.open({baudRate: 9600})
          this.startSerialPortReading()

          const textEncoder = new TextEncoderStream()
          this.writableStreamClosed = textEncoder.readable.pipeTo(
            this.selectedPort.writable
          )

          this.writer = textEncoder.writable.getWriter()
        } catch (error) {
          this.selectedPort = null
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
          if (this.writer) this.writer.close()
          if (this.writableStreamClosed) await this.writableStreamClosed
          if (this.reader) this.reader.cancel()
          if (this.readableStreamClosed)
            await this.readableStreamClosed.catch(() => {
              /* Ignore the error */
            })
          if (this.selectedPort) await this.selectedPort.close()
          this.selectedPort = null
          this.$q.notify({
            type: 'positive',
            message: 'Serial port disconnected!',
            timeout: 5000
          })
        } catch (error) {
          this.selectedPort = null
          console.log('### error', error)
          this.$q.notify({
            type: 'warning',
            message: 'Cannot close serial port!',
            caption: `${error}`,
            timeout: 10000
          })
        }
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
        this.receivedData += value + '\n'
        const textArea = document.getElementById(
          'watchonly-serial-port-data-input'
        )
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
          await this.writer.write(
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
          await this.writer.write(COMMAND_SIGN_PSBT + '\n')
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
          await this.writer.write(COMMAND_SEED + '\n')
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
          this.hww.showPassword = false
        }
      }
    },
    created: async function () {}
  })
}
