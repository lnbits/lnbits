import {
  PSBT_BASE64_PREFIX,
  COMMAND_PING,
  COMMAND_PASSWORD,
  COMMAND_PASSWORD_CLEAR,
  COMMAND_ADDRESS,
  COMMAND_SEND_PSBT,
  COMMAND_PSBT_BEGIN,
  COMMAND_PSBT_CHUNK,
  COMMAND_PSBT_COMMIT,
  COMMAND_PSBT_REVIEW,
  COMMAND_NEW,
  COMMAND_SIGN_PSBT,
  COMMAND_HELP,
  COMMAND_WIPE,
  COMMAND_SEED,
  COMMAND_TRNG,
  COMMAND_RESTORE,
  COMMAND_CANCEL,
  COMMAND_XPUB,
  COMMAND_PAIR,
  COMMAND_LOG,
  getSigningNetwork,
  HWW_DEFAULT_CONFIG,
  sleep,
  satOrBtc,
  asciiToUint8Array
} from '../js/utils.js'
window.app.component('onchain-serial-signer', {
  name: 'onchain-serial-signer',
  template: '#onchain-serial-signer',

  props: ['sats-denominated', 'network'],
  data: function () {
    return {
      selectedPort: null,
      disconnectHandler: null,
      writer: null,
      reader: null,
      readTask: null,
      closePromise: null,
      pairingDialog: null,
      connected: false,
      isConnecting: false,
      connectionAttempt: 0,
      deviceId: null,
      closingSerialPort: false,
      receivedData: '',
      config: {},
      decryptionKey: null,
      sharedSecret: null,
      pendingCommands: {},
      loginPromise: null,
      loginResolve: null,
      xpubData: {},
      trng: {
        running: false,
        showDialog: false,
        result: null,
        error: null
      },

      hww: {
        password: null,
        showPassword: false,
        mnemonic: null,
        showMnemonic: false,
        quickMnemonicInput: false,
        passphrase: null,
        showPassphrase: false,
        hasPassphrase: false,
        authenticated: false,
        loggingIn: false,
        settingUp: false,
        showPasswordDialog: false,
        showConfigDialog: false,
        showWipeDialog: false,
        showRestoreDialog: false,
        showConfirmationDialog: false,
        showSignedPsbt: false,
        sendingPsbt: false,
        signingPsbt: false,
        seedWordPosition: 1,
        seedLoading: false,
        seedWord: null,
        showSeedWord: false,
        showSeedDialog: false,
        // config: null,

        confirm: {
          outputIndex: 0,
          showFee: false,
          stage: ''
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
      this.config = {...HWW_DEFAULT_CONFIG}
      await this.openSerialPort(this.config)
    },
    openSerialPort: async function (config = HWW_DEFAULT_CONFIG) {
      if (!this.checkSerialPortSupported()) return false
      if (this.isConnecting || this.closingSerialPort) return false
      if (this.connected) {
        if (!this.hww.authenticated) await this.hwwShowPasswordDialog()
        return true
      }

      this.isConnecting = true
      const attempt = ++this.connectionAttempt
      try {
        const port = await navigator.serial.requestPort()
        if (attempt !== this.connectionAttempt) return false
        this.selectedPort = port
        this.disconnectHandler = () => {
          if (this.selectedPort === port) void this.closeSerialPort()
        }
        port.addEventListener('disconnect', this.disconnectHandler)
        await port.open(config)
        if (attempt !== this.connectionAttempt) {
          await port.close()
          return false
        }
        if (!port.readable || !port.writable) {
          throw new Error('Serial port has no readable or writable stream')
        }
        this.reader = port.readable.getReader()
        this.writer = port.writable.getWriter()
        this.readTask = this.startSerialPortReading()
        await sleep(1000)
        if (this.selectedPort !== port || this.closingSerialPort) {
          throw new Error('Serial device disconnected')
        }
        await this.hwwPing()
        await this.hwwPair()
        if (this.selectedPort !== port || this.closingSerialPort) {
          throw new Error('Serial device disconnected')
        }
        this.connected = true
        this.$emit('device:connected', 'usb-device')
        this.$q.notify({
          type: 'positive',
          message: 'Paired with device!',
          timeout: 5000
        })
        return true
      } catch (error) {
        await this.closeSerialPort(false)
        if (error.name !== 'NotFoundError') {
          this.$q.notify({
            type: 'warning',
            message: 'Cannot connect to Bowser Wallet!',
            caption: error.message,
            timeout: 10000
          })
        }
        return false
      } finally {
        this.isConnecting = false
      }
    },
    openSerialPortConfig: async function () {
      this.config = {...HWW_DEFAULT_CONFIG}
      this.hww.showConfigDialog = true
    },
    closeSerialPort: function (notify = true) {
      if (this.closePromise) return this.closePromise
      this.closePromise = this.releaseSerialPort(notify).finally(() => {
        this.closePromise = null
      })
      return this.closePromise
    },
    releaseSerialPort: async function (notify) {
      this.closingSerialPort = true
      this.connectionAttempt++
      this.connected = false
      this.failPendingCommands(new Error('Serial connection closed'))
      this.pairingDialog?.hide()
      this.pairingDialog = null
      const port = this.selectedPort
      if (port && this.disconnectHandler)
        port.removeEventListener('disconnect', this.disconnectHandler)
      this.disconnectHandler = null
      try {
        // Cancel the read before closing the port, and always release both locks.
        if (this.reader) await this.reader.cancel().catch(() => {})
        if (this.readTask) await this.readTask.catch(() => {})
        else if (this.reader) this.reader.releaseLock()
        if (this.writer) this.writer.releaseLock()
        if (port) await port.close()
        if (notify && port) {
          this.$q.notify({
            type: 'positive',
            message: 'Serial port disconnected!',
            timeout: 5000
          })
        }
      } catch (error) {
        if (notify) {
          this.$q.notify({
            type: 'warning',
            message: 'Cannot close serial port!',
            caption: error.message,
            timeout: 10000
          })
        }
      } finally {
        this.selectedPort = null
        this.writer = null
        this.reader = null
        this.readTask = null
        this.sharedSecret?.fill(0)
        this.decryptionKey?.fill(0)
        this.sharedSecret = null
        this.decryptionKey = null
        this.deviceId = null
        this.xpubData = {}
        this.trng.showDialog = false
        this.trng.result = null
        this.hww.showPasswordDialog = false
        this.hww.authenticated = false
        this.hww.password = null
        this.hww.passphrase = null
        this.clearSetupSecrets()
        this.hww.showSeedDialog = false
        this.hww.showWipeDialog = false
        this.hww.showRestoreDialog = false
        this.closingSerialPort = false
      }
    },

    isConnected: function () {
      return this.connected
    },
    isTaprootSupported: function () {
      return true
    },
    isAuthenticated: function () {
      return this.hww.authenticated
    },

    seedInputDone: function (mnemonic) {
      this.hww.mnemonic = mnemonic
    },
    isAuthenticating: function () {
      return this.isAuthenticated() ? Promise.resolve(true) : this.loginPromise
    },

    isSendingPsbt: async function () {
      return false
    },

    isFetchingXpub: async function () {
      return this.xpubData
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
      const reader = this.reader
      const decoder = new TextDecoder()
      let buffered = ''
      try {
        while (true) {
          const {value, done} = await reader.read()
          if (done || this.closingSerialPort) break
          buffered += decoder.decode(value, {stream: true})
          const lines = buffered.split('\n')
          buffered = lines.pop()
          for (const line of lines) {
            if (!line.trim()) continue
            const {command, commandData} = await this.extractCommand(
              line.trim()
            )
            if (this.closingSerialPort) break
            await this.handleSerialPortResponse(command, commandData)
            this.updateSerialPortConsole(command)
          }
        }
      } catch (error) {
        if (!this.closingSerialPort) {
          this.$q.notify({
            type: 'warning',
            message: 'Serial port communication error!',
            caption: error.message,
            timeout: 10000
          })
        }
      } finally {
        reader.releaseLock()
        if (!this.closingSerialPort) void this.closeSerialPort(false)
      }
    },
    handleSerialPortResponse: async function (command, commandData) {
      this.logPublicCommandsResponse(command, commandData)
      const pending = this.pendingCommands[command]
      if (pending) {
        clearTimeout(pending.timer)
        delete this.pendingCommands[command]
        pending.resolve(commandData)
        return
      }

      switch (command) {
        case COMMAND_PASSWORD_CLEAR:
          this.handleLogoutResponse(commandData)
          break
        case COMMAND_PSBT_REVIEW:
          this.handlePsbtReview(commandData)
          break
        case COMMAND_SEED:
          // Hardware buttons can also advance the on-device backup.
          if (this.hww.showSeedDialog) this.handleShowSeedResponse(commandData)
          break
        case COMMAND_LOG:
          break
        case COMMAND_NEW:
          this.hww.authenticated = false
          break
        default:
          console.log(`   %c${command}`, 'background: #222; color: red')
      }
    },
    logPublicCommandsResponse: function (command, commandData) {
      switch (command) {
        case COMMAND_SIGN_PSBT:
        case COMMAND_PASSWORD:
        case COMMAND_PASSWORD_CLEAR:
        case COMMAND_SEND_PSBT:
        case COMMAND_WIPE:
        case COMMAND_XPUB:
        case COMMAND_PAIR:
          console.log(`   %c${command}`, 'background: #222; color: yellow')
      }
    },
    updateSerialPortConsole: function (value) {
      this.receivedData += value + '\n'
      const textArea = document.getElementById('serial-port-console')
      if (textArea) textArea.scrollTop = textArea.scrollHeight
    },
    hwwPing: async function () {
      const res = await this.requestCommand(
        COMMAND_PING,
        [window.location.host],
        20000,
        false
      )
      const [status, deviceId] = res.trim().split(/\s+/)
      if (status !== '0' || !deviceId) {
        throw new Error('Bowser Wallet returned an invalid ping response')
      }
      this.deviceId = deviceId
    },
    hwwShowPasswordDialog: async function () {
      if (this.loginResolve) return
      this.loginPromise = new Promise(resolve => {
        this.loginResolve = resolve
      })
      this.hww.showPasswordDialog = true
    },
    passwordDialogClosed: function () {
      if (!this.hww.loggingIn) {
        this.hww.password = null
        this.hww.passphrase = null
      }
      if (!this.hww.loggingIn && this.loginResolve) {
        this.loginResolve(false)
        this.loginResolve = null
      }
    },
    hwwShowWipeDialog: async function () {
      this.hww.showWipeDialog = true
    },
    hwwShowRestoreDialog: async function () {
      this.hww.showRestoreDialog = true
    },
    closeSeedDialog: function () {
      this.hww.seedWord = null
      this.hww.showSeedWord = false
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
      return this.openSerialPort(this.config)
    },
    hwwLogin: async function () {
      if (this.hww.loggingIn) return
      this.hww.loggingIn = true
      try {
        const response = await this.requestCommand(
          COMMAND_PASSWORD,
          [
            this.hww.password,
            this.hww.hasPassphrase ? this.hww.passphrase || '' : ''
          ],
          120000
        )
        this.handleLoginResponse(response)
      } catch (error) {
        this.hww.authenticated = false
        if (this.loginResolve) this.loginResolve(false)
        this.$q.notify({
          type: 'warning',
          message: 'Failed to send password to Hardware Wallet!',
          caption: `${error}`,
          timeout: 10000
        })
      } finally {
        this.loginResolve = null
        this.hww.loggingIn = false
        this.hww.showPasswordDialog = false
        this.hww.password = null
        this.hww.passphrase = null
        this.hww.showPassword = false
        this.hww.showPassphrase = false
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
        const response = await this.requestCommand(COMMAND_PASSWORD_CLEAR)
        if (response.trim() !== '1') throw new Error('Logout was not confirmed')
        this.handleLogoutResponse(response)
      } catch (error) {
        this.$q.notify({
          type: 'warning',
          message: 'Failed to logout from Hardware Wallet!',
          caption: `${error}`,
          timeout: 10000
        })
      }
    },
    hwwShowAddress: async function (path, address) {
      try {
        const response = await this.requestCommand(COMMAND_ADDRESS, [
          getSigningNetwork(this.network),
          path,
          address
        ])
        const [status, derivedAddress] = response.trim().split(/\s+/)
        if (status !== '1' || derivedAddress !== address)
          throw new Error('The address returned by Bowser Wallet did not match')
      } catch (error) {
        this.$q.notify({
          type: 'warning',
          message: 'Failed to verify address on Bowser Wallet!',
          caption: `${error}`,
          timeout: 10000
        })
      }
    },
    handleLogoutResponse: function (res = '') {
      if (this.hww.authenticated) {
        this.$q.notify({
          type: 'positive',
          message: 'Logged Out',
          timeout: 10000
        })
      }
      this.failPendingCommands(new Error('Bowser Wallet locked or restarted'))
    },
    hwwSendPsbt: async function (psbtBase64, tx) {
      if (!this.hww.authenticated) throw new Error('Unlock Bowser Wallet first')
      if (this.hww.sendingPsbt || this.hww.signingPsbt) {
        throw new Error('A signing operation is already in progress')
      }
      if (!psbtBase64 || psbtBase64.length > 16384) {
        throw new Error('Bowser PSBT must fit within 16,384 base64 characters')
      }
      if (tx.inputs.length > 64 || tx.outputs.length > 64) {
        throw new Error('Bowser supports at most 64 inputs and 64 outputs')
      }
      try {
        this.tx = tx
        this.hww.sendingPsbt = true
        this.hww.confirm = {outputIndex: 0, showFee: false, stage: 'transfer'}
        this.hww.showConfirmationDialog = true
        const count = Math.ceil(psbtBase64.length / 64)
        const started = await this.requestCommand(COMMAND_PSBT_BEGIN, [
          getSigningNetwork(this.network),
          psbtBase64.length
        ])
        if (started !== `1 ${count}`)
          throw new Error('Bowser Wallet refused the PSBT transfer')
        for (let index = 0; index < count; index++) {
          const response = await this.requestCommand(COMMAND_PSBT_CHUNK, [
            index,
            psbtBase64.slice(index * 64, (index + 1) * 64)
          ])
          if (response !== `1 ${index}`)
            throw new Error('Bowser Wallet rejected a PSBT chunk')
        }
        this.hww.confirm.stage = 'review'
        const reviewed = await this.requestCommand(
          COMMAND_PSBT_COMMIT,
          [],
          15 * 60000
        )
        if (reviewed !== '1')
          throw new Error('Bowser Wallet did not approve the PSBT')
        this.hww.sendingPsbt = false
        await this.hwwSignPsbt()
      } finally {
        this.hww.sendingPsbt = false
        this.hww.signingPsbt = false
        this.hww.showConfirmationDialog = false
        this.tx = null
      }
    },
    handlePsbtReview: function (res = '') {
      if (!this.tx || (!this.hww.sendingPsbt && !this.hww.signingPsbt)) return
      const [stage, index, total] = res.split(' ')
      if (
        stage === 'output' &&
        /^\d+$/.test(index) &&
        +index < this.tx.outputs.length &&
        +total === this.tx.outputs.length
      ) {
        this.hww.confirm = {outputIndex: +index, showFee: false, stage}
      } else if (res === 'fee' || res === 'sign') {
        this.hww.confirm.showFee = true
        this.hww.confirm.stage = res
      }
    },
    hwwSignPsbt: async function () {
      this.hww.signingPsbt = true
      this.hww.confirm.stage = 'sign'
      const res = await this.requestCommand(COMMAND_SIGN_PSBT, [], 120000)
      const [count, psbt] = res.trim().split(/\s+/)
      if (
        !/^\d+$/.test(count) ||
        +count < 1 ||
        !psbt?.startsWith(PSBT_BASE64_PREFIX)
      ) {
        throw new Error('Bowser Wallet did not return a signed PSBT')
      }
      this.updateSignedPsbt(psbt)
      this.$q.notify({
        type: 'positive',
        message: 'Transaction Signed',
        caption: `Inputs signed: ${count}`,
        timeout: 10000
      })
    },
    hwwPair: async function () {
      this.decryptionKey = nobleSecp256k1.utils.randomPrivateKey()
      const publicKeyHex = nobleSecp256k1.Point.fromPrivateKey(
        this.decryptionKey
      )
        .toHex(false)
        .slice(2)
      const res = await this.requestCommand(
        COMMAND_PAIR,
        [publicKeyHex],
        20000,
        false
      )
      const [status, pubKeyHex] = res.trim().split(/\s+/)
      if (status !== '0') {
        if (pubKeyHex === 'connection_period_expired') {
          throw new Error(
            'Restart Bowser Wallet and connect during the startup countdown.'
          )
        }
        if (pubKeyHex === 'rng_failure') {
          throw new Error(
            'Device hardware RNG health check failed. Pairing refused.'
          )
        }
        throw new Error('Device refused pairing')
      }
      if (!/^[0-9a-f]{128}$/i.test(pubKeyHex || '')) {
        throw new Error('Invalid device pairing key')
      }
      const hwwPublicKey = nobleSecp256k1.Point.fromHex('04' + pubKeyHex)
      this.sharedSecret = nobleSecp256k1
        .getSharedSecret(this.decryptionKey, hwwPublicKey, false)
        .slice(1, 33)
      const sharedSecretHex = nobleSecp256k1.utils.bytesToHex(this.sharedSecret)
      const sharedSecretHash = await nobleSecp256k1.utils.sha256(
        asciiToUint8Array(sharedSecretHex)
      )
      const fingerprint = nobleSecp256k1.utils
        .bytesToHex(sharedSecretHash)
        .substring(0, 5)
        .toUpperCase()
      if (!this.selectedPort || this.closingSerialPort) {
        throw new Error('Serial device disconnected')
      }
      const confirmed = await new Promise(resolve => {
        this.pairingDialog = LNbits.utils
          .confirmDialog('Confirm code from display: ' + fingerprint)
          .onOk(() => resolve(true))
          .onDismiss(() => resolve(false))
      })
      this.pairingDialog = null
      if (!confirmed) throw new Error('Pairing code was not confirmed')
    },
    hwwHelp: async function () {
      try {
        await this.sendCommandSecure(COMMAND_HELP)
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
    clearSetupSecrets: function () {
      this.hww.password = null
      this.hww.confirmedPassword = null
      this.hww.mnemonic = null
      this.hww.showPassword = false
      this.hww.showMnemonic = false
    },
    validateNewPassword: function () {
      const password = this.hww.password || ''
      if (password.length < 8 || /\s/.test(password))
        throw new Error(
          'Use a password of at least 8 characters without spaces'
        )
      if (password !== this.hww.confirmedPassword)
        throw new Error('Passwords do not match')
    },
    hwwWipe: async function () {
      if (this.hww.settingUp) return
      this.hww.settingUp = true
      try {
        this.validateNewPassword()
        const response = await this.requestCommand(
          COMMAND_WIPE,
          [this.hww.password],
          60000
        )
        this.hww.showWipeDialog = false
        await this.handleWipeResponse(response)
      } catch (error) {
        this.$q.notify({
          type: 'warning',
          message: 'Failed to wipe!',
          caption: `${error}`,
          timeout: 10000
        })
      } finally {
        this.hww.settingUp = false
        this.hww.showWipeDialog = false
        this.hww.password = null
        this.hww.confirmedPassword = null
        this.hww.showPassword = false
      }
    },
    handleWipeResponse: async function (res = '') {
      const wiped = res.trim() === '1'
      this.hww.authenticated = wiped
      if (wiped) {
        this.xpubData = {}
        this.$q.notify({
          type: 'positive',
          message: 'Wallet wiped!',
          timeout: 10000
        })
        await this.hwwShowSeed()
      } else {
        this.$q.notify({
          type: 'warning',
          message: 'Failed to wipe wallet!',
          timeout: 10000
        })
      }
    },
    hwwTestTrng: async function () {
      if (
        !this.connected ||
        this.trng.running ||
        this.hww.loggingIn ||
        this.hww.sendingPsbt ||
        this.hww.signingPsbt
      )
        return
      this.trng.running = true
      this.trng.showDialog = true
      this.trng.result = null
      this.trng.error = null
      try {
        const response = await this.requestCommand(COMMAND_TRNG, [], 60000)
        const [
          status,
          sampleCount,
          statistic,
          minimum,
          maximum,
          verdict,
          ...rest
        ] = response.trim().split(/\s+/)
        const samples = Number(sampleCount)
        const chiSquared = Number(statistic)
        const minimumCount = Number(minimum)
        const maximumCount = Number(maximum)
        if (
          status !== '1' ||
          rest.length !== 0 ||
          !Number.isInteger(samples) ||
          samples !== 5000 ||
          !Number.isFinite(chiSquared) ||
          chiSquared < 0 ||
          !Number.isInteger(minimumCount) ||
          minimumCount < 0 ||
          !Number.isInteger(maximumCount) ||
          maximumCount < minimumCount ||
          maximumCount > samples ||
          (verdict !== 'healthy' && verdict !== 'unexpected')
        ) {
          throw new Error(
            'Bowser Wallet did not complete the TRNG visual check'
          )
        }
        this.trng.result = {
          samples,
          chiSquared,
          minimumCount,
          maximumCount,
          looksHealthy: verdict === 'healthy'
        }
      } catch (error) {
        this.trng.error = error.message
      } finally {
        this.trng.running = false
      }
    },
    hwwXpub: async function (path) {
      this.xpubData = {}
      const res = await this.requestCommand(COMMAND_XPUB, [
        getSigningNetwork(this.network),
        path
      ])
      const args = res.trim().split(/\s+/)
      if (
        args.length !== 3 ||
        args[0] !== '1' ||
        !/^[0-9a-f]{8}$/i.test(args[2])
      ) {
        throw new Error('Bowser Wallet did not return a valid XPub response')
      }
      const xpub = args[1].trim()
      const fingerprint = args[2].trim()
      this.xpubData = {xpub, fingerprint}
    },

    hwwShowSeed: async function () {
      if (this.hww.seedLoading) return
      this.hww.showSeedDialog = true
      await this.requestSeedWord(1)
    },
    requestSeedWord: async function (position) {
      if (this.hww.seedLoading) return
      this.hww.seedLoading = true
      try {
        const response = await this.requestCommand(
          COMMAND_SEED,
          [position],
          12000
        )
        if (this.hww.showSeedDialog && !this.handleShowSeedResponse(response))
          throw new Error(
            'Bowser Wallet did not confirm on-device seed display'
          )
      } catch (error) {
        this.$q.notify({
          type: 'warning',
          message: 'Failed to show seed!',
          caption: `${error}`,
          timeout: 10000
        })
      } finally {
        this.hww.seedLoading = false
      }
    },
    showNextSeedWord: async function () {
      await this.requestSeedWord(Math.min(24, this.hww.seedWordPosition + 1))
    },
    showPrevSeedWord: async function () {
      await this.requestSeedWord(Math.max(1, this.hww.seedWordPosition - 1))
    },
    handleShowSeedResponse: function (res = '') {
      const [pos, status, ...rest] = res.trim().split(/\s+/)
      this.hww.seedWord = null
      if (
        status === 'displayed' &&
        rest.length === 0 &&
        /^\d+$/.test(pos) &&
        +pos >= 1 &&
        +pos <= 24
      ) {
        this.hww.seedWordPosition = +pos
        return true
      }
      return false
    },
    hwwRestore: async function () {
      if (this.hww.settingUp) return
      this.hww.settingUp = true
      try {
        this.validateNewPassword()
        if (!this.hww.mnemonic?.trim())
          throw new Error('Enter the recovery words')
        const response = await this.requestCommand(
          COMMAND_RESTORE,
          [this.hww.password, this.hww.mnemonic],
          60000
        )
        this.handleRestoreResponse(response)
      } catch (error) {
        this.$q.notify({
          type: 'warning',
          message: 'Failed to restore from seed!',
          caption: `${error}`,
          timeout: 10000
        })
      } finally {
        this.hww.settingUp = false
        this.hww.showRestoreDialog = false
        this.hww.mnemonic = null
        this.hww.showMnemonic = false
        this.hww.password = null
        this.hww.confirmedPassword = null
        this.hww.showPassword = false
      }
    },

    handleRestoreResponse: function (res = '') {
      const restored = res.trim() === '1'
      this.hww.authenticated = restored
      if (restored) this.xpubData = {}
      this.$q.notify({
        type: restored ? 'positive' : 'warning',
        message: restored ? 'Wallet restored!' : 'Failed to restore wallet!',
        timeout: 10000
      })
    },

    updateSignedPsbt: async function (value) {
      this.$emit('signed:psbt', value)
    },

    requestCommand: function (
      command,
      attrs = [],
      timeout = 20000,
      secure = true
    ) {
      if (Object.keys(this.pendingCommands).length)
        return Promise.reject(
          new Error('A device operation is already pending')
        )
      let sending
      const response = new Promise((resolve, reject) => {
        const fail = error => {
          const pending = this.pendingCommands[command]
          if (!pending || pending.resolve !== resolve) return
          clearTimeout(pending.timer)
          delete this.pendingCommands[command]
          reject(error)
        }
        const timer = setTimeout(
          () => fail(new Error(`${command} timed out`)),
          timeout
        )
        this.pendingCommands[command] = {resolve, reject, timer}
        const send = secure ? this.sendCommandSecure : this.sendCommandClearText
        sending = send(command, attrs)
        sending.catch(fail)
      })
      // Match Bowser's client: a response alone must not advance the handshake
      // while the serial write is still pending or has failed.
      return Promise.all([response, sending]).then(([result]) => result)
    },
    failPendingCommands: function (error) {
      for (const pending of Object.values(this.pendingCommands)) {
        clearTimeout(pending.timer)
        pending.reject(error)
      }
      this.pendingCommands = {}
      if (this.loginResolve) this.loginResolve(false)
      this.loginResolve = null
      this.hww.authenticated = false
      this.hww.sendingPsbt = false
      this.hww.signingPsbt = false
      this.hww.showConfirmationDialog = false
    },

    sendCommandSecure: async function (command, attrs = []) {
      if (!this.connected || !this.writer) {
        throw new Error(
          'Connect and confirm the Bowser Wallet pairing code first'
        )
      }
      const message = [command].concat(attrs).join(' ')
      const iv = window.crypto.getRandomValues(new Uint8Array(16))
      if (!this.sharedSecret || !this.sharedSecret.length) {
        throw new Error(
          `Secure connection not estabileshed. Tried to run command: ${command}`
        )
      }
      const encrypted = await this.encryptMessage(
        this.sharedSecret,
        iv,
        new TextEncoder().encode(message).length + ' ' + message
      )

      const encryptedHex = nobleSecp256k1.utils.bytesToHex(encrypted)
      const encryptedIvHex = nobleSecp256k1.utils.bytesToHex(iv)
      await this.writer.write(
        new TextEncoder().encode(encryptedHex + encryptedIvHex + '\n')
      )
    },
    sendCommandClearText: async function (command, attrs = []) {
      const message = [command].concat(attrs).join(' ')
      await this.writer.write(new TextEncoder().encode(message + '\n'))
    },
    extractCommand: async function (value) {
      const command = value.split(' ')[0]
      const commandData = value.substring(command.length).trim()

      if (
        command === COMMAND_PAIR ||
        command === COMMAND_LOG ||
        command === COMMAND_NEW ||
        command === COMMAND_PSBT_BEGIN ||
        command === COMMAND_PSBT_CHUNK ||
        command === COMMAND_PSBT_REVIEW ||
        command === COMMAND_PASSWORD_CLEAR ||
        command === COMMAND_PING
      )
        return {command, commandData}

      const decryptedValue = await this.decryptData(value)
      const decryptedCommand = decryptedValue.split(' ')[0]
      const decryptedCommandData = decryptedValue
        .substring(decryptedCommand.length)
        .trim()
      return {
        command: decryptedCommand,
        commandData: decryptedCommandData
      }
    },
    decryptData: async function (value) {
      if (!this.sharedSecret) {
        console.log('/error Secure session not established!')
        return '/error Secure session not established!'
      }
      try {
        const ivSize = 32
        const messageHex = value.substring(0, value.length - ivSize)
        const ivHex = value.substring(value.length - ivSize)
        const messageBytes = nobleSecp256k1.utils.hexToBytes(messageHex)
        const iv = nobleSecp256k1.utils.hexToBytes(ivHex)
        const decrypted1 = await this.decryptMessage(
          this.sharedSecret,
          iv,
          messageBytes
        )
        const separator = decrypted1.indexOf(32)
        const lengthText = new TextDecoder().decode(
          decrypted1.slice(0, separator)
        )
        const length = Number(lengthText)
        if (
          separator < 1 ||
          !/^\d+$/.test(lengthText) ||
          !Number.isSafeInteger(length) ||
          separator + 1 + length > decrypted1.length
        ) {
          throw new Error('Invalid encrypted response length')
        }
        return new TextDecoder().decode(
          decrypted1.slice(separator + 1, separator + 1 + length)
        )
      } catch (error) {
        console.log('/error Failed to decrypt message from device!')
        return '/error Failed to decrypt message from device!'
      }
    },
    encryptMessage: async function (key, iv, message) {
      const bytes = new TextEncoder().encode(message)
      const encodedMessage = new Uint8Array(
        Math.ceil(bytes.length / 16) * 16
      ).fill(32)
      encodedMessage.set(bytes)

      const aesCbc = new aesjs.ModeOfOperation.cbc(key, iv)
      const encryptedBytes = aesCbc.encrypt(encodedMessage)

      return encryptedBytes
    },
    decryptMessage: async function (key, iv, encryptedBytes) {
      const aesCbc = new aesjs.ModeOfOperation.cbc(key, iv)
      const decryptedBytes = aesCbc.decrypt(encryptedBytes)
      return decryptedBytes
    }
  },
  beforeUnmount: function () {
    void this.closeSerialPort(false)
  },
  created: async function () {
    window.localStorage.removeItem('lnbits-paired-devices')
  }
})
