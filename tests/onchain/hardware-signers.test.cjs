const assert = require('node:assert/strict')
const {readFileSync} = require('./source.cjs')
const {resolve} = require('node:path')
const {test} = require('node:test')
const vm = require('node:vm')
const {
  webcrypto,
  createECDH,
  createHash,
  createCipheriv,
  createDecipheriv
} = require('node:crypto')

function harness(name = 'serial-signer', trezor = {}, timerDelay) {
  const components = {}
  const logs = []
  const events = []
  const timers = []
  const context = vm.createContext({
    TextEncoder,
    TextDecoder,
    Uint8Array,
    crypto: webcrypto,
    setTimeout(fn, timeout) {
      timers.push(timeout)
      return setTimeout(fn, timerDelay ? timerDelay(timeout) : timeout)
    },
    clearTimeout,
    console: {log: (...args) => logs.push(args)},
    TrezorConnect: trezor,
    LNbits: {utils: {}},
    document: {getElementById: () => null}
  })
  context.window = context
  context.self = context
  context.location = {host: 'watchonly.test'}
  context.app = {
    component: (name, component) => {
      components[name] = component
    }
  }
  for (const file of [
    'js/utils.js',
    'js/map.js',
    'js/crypto/noble-secp256k1.js',
    'js/crypto/aes.js',
    `components/${name}.js`
  ]) {
    vm.runInContext(
      readFileSync(
        resolve(__dirname, '../../lnbits/onchain/static', file),
        'utf8'
      ),
      context
    )
  }
  const component = components['onchain-' + name]
  const instance = {
    ...component.data(),
    network: 'Testnet',
    $q: {notify() {}},
    $emit: (...args) => events.push(args)
  }
  for (const [key, method] of Object.entries(component.methods))
    instance[key] = method.bind(instance)
  return {instance, logs, events, timers, context, component}
}

const transaction = () => ({
  inputs: [
    {
      accountPath: "m/84'/1'/0'",
      accountType: 'p2wpkh',
      branch_index: 0,
      address_index: 1,
      tx_id: 'ab'.repeat(32),
      vout: 0,
      amount: 10000
    }
  ],
  outputs: [{address: 'recipient', amount: 9000}],
  feeValue: 1000,
  feeRate: 2
})

// Exercise the real byte streams and handshake against the firmware's wire
// format, using Node crypto independently of Watchonly's bundled crypto code.
function serialHarness(options = {}) {
  const state = harness('serial-signer', {}, timeout =>
    timeout === 1000 ? 0 : options.timeout || timeout
  )
  const {instance: signer, context} = state
  const notifications = []
  signer.$q.notify = value => notifications.push(value)
  const device = createECDH('secp256k1')
  device.generateKeys()
  let secret
  let input
  let dialog
  let expectedCode
  let requests = 0
  let closes = 0
  const listeners = []
  const commands = []
  const reply = line => {
    const bytes = new TextEncoder().encode(line + '\r\n')
    // Device responses can span USB packets or share a single packet.
    input.enqueue(bytes.slice(0, 3))
    input.enqueue(bytes.slice(3))
  }
  const encrypt = line => {
    const body = Buffer.from(`${Buffer.byteLength(line)} ${line}`)
    const padded = Buffer.alloc(Math.ceil(body.length / 16) * 16, 32)
    body.copy(padded)
    const iv = Buffer.alloc(16, 7)
    const cipher = createCipheriv('aes-256-cbc', secret, iv)
    cipher.setAutoPadding(false)
    return Buffer.concat([cipher.update(padded), cipher.final(), iv]).toString(
      'hex'
    )
  }
  const decrypt = line => {
    const data = Buffer.from(line, 'hex')
    const cipher = createDecipheriv('aes-256-cbc', secret, data.subarray(-16))
    cipher.setAutoPadding(false)
    const plain = Buffer.concat([
      cipher.update(data.subarray(0, -16)),
      cipher.final()
    ])
    const separator = plain.indexOf(32)
    const length = Number(plain.subarray(0, separator).toString())
    return plain.subarray(separator + 1, separator + 1 + length).toString()
  }
  const port = {
    addEventListener(name, callback) {
      if (name === 'disconnect') listeners.push(callback)
    },
    removeEventListener(name, callback) {
      if (name === 'disconnect') {
        const index = listeners.indexOf(callback)
        if (index !== -1) listeners.splice(index, 1)
      }
    },
    async open(config) {
      if (options.openError) throw new Error('Port is already in use')
      assert.equal(config.baudRate, 9600)
      this.readable = new ReadableStream({
        start: controller => (input = controller)
      })
      this.writable = new WritableStream({
        write: bytes => {
          assert.ok(bytes instanceof Uint8Array)
          let line = new TextDecoder().decode(bytes).trim()
          if (!line.startsWith('/')) line = decrypt(line)
          commands.push(line)
          const [command, ...args] = line.split(' ')
          if (command === options.silentCommand) return
          if (command === '/ping') {
            reply(
              options.pingResponse ||
                '\r\n/log boot\r\n/new\r\n/ping 0 test-device'
            )
          } else if (command === '/pair') {
            assert.match(args[0], /^[0-9a-f]{128}$/)
            secret = device.computeSecret(Buffer.from('04' + args[0], 'hex'))
            expectedCode = createHash('sha256')
              .update(secret.toString('hex'))
              .digest('hex')
              .slice(0, 5)
              .toUpperCase()
            reply(
              options.pairResponse ||
                '/pair 0 ' + device.getPublicKey('hex', 'uncompressed').slice(2)
            )
          } else if (command === '/password') {
            reply(encrypt('/password 1'))
          } else if (command === '/xpub') {
            reply(encrypt('/xpub 1 tpubExample 00112233'))
          } else if (command === '/trng') {
            reply(encrypt('/trng 1 5000 103.42 34 69 healthy'))
          }
        }
      })
      if (options.writerError) {
        this.writable.getWriter = () => {
          throw new Error('Cannot acquire serial writer')
        }
      }
    },
    async close() {
      assert.ok(
        !this.readable?.locked,
        'reader must be released before closing'
      )
      assert.ok(
        !this.writable?.locked,
        'writer must be released before closing'
      )
      closes++
    }
  }
  context.navigator = {
    serial: {
      requestPort: async () => {
        requests++
        return port
      }
    }
  }
  context.LNbits.utils.confirmDialog = message => {
    assert.equal(message, 'Confirm code from display: ' + expectedCode)
    const callbacks = {}
    dialog = {
      onOk(fn) {
        callbacks.ok = fn
        return this
      },
      onDismiss(fn) {
        callbacks.dismiss = fn
        return this
      },
      hide() {
        callbacks.dismiss()
      },
      accept() {
        callbacks.ok()
        callbacks.dismiss()
      }
    }
    return dialog
  }
  return {
    ...state,
    port,
    commands,
    notifications,
    options,
    reply,
    get dialog() {
      return dialog
    },
    get closes() {
      return closes
    },
    get requests() {
      return requests
    },
    disconnect() {
      listeners.forEach(callback => callback())
    },
    end() {
      input.close()
    },
    error() {
      input.error(new Error('Device lost'))
    }
  }
}

async function until(predicate) {
  for (let count = 0; count < 1000; count++) {
    if (predicate()) return
    await new Promise(resolve => setTimeout(resolve, 1))
  }
  assert.fail('Expected serial state was not reached')
}

test('Bowser connects only after matching code confirmation, then unlocks and imports over encrypted serial', async () => {
  const state = serialHarness()
  const {instance: signer, events, commands} = state
  const connecting = signer.openSerialPort()
  await until(() => state.dialog)
  assert.equal(signer.isConnected(), false)
  assert.equal(events.length, 0)
  assert.equal(signer.isConnecting, true)
  await assert.rejects(
    signer.sendCommandSecure('/password', ['test-password']),
    /pairing code/
  )
  assert.equal(await signer.openSerialPort(), false)
  assert.equal(state.requests, 1)
  state.dialog.accept()
  assert.equal(await connecting, true)
  assert.equal(signer.isConnected(), true)
  assert.equal(signer.isConnecting, false)
  assert.deepEqual(events, [['device:connected', 'usb-device']])
  await signer.hwwShowPasswordDialog()
  signer.hww.password = 'test-password'
  signer.hww.hasPassphrase = true
  signer.hww.passphrase = 'café space'
  await signer.hwwLogin()
  assert.equal(signer.isAuthenticated(), true)
  assert.ok(commands.includes('/password test-password café space'))
  await signer.hwwXpub("m/84'/1'/0'")
  assert.equal(signer.xpubData.fingerprint, '00112233')
  await signer.closeSerialPort()
  assert.equal(signer.isConnected(), false)
  assert.equal(signer.isAuthenticated(), false)
  assert.equal(state.closes, 1)
})

for (const options of [
  {openError: true},
  {writerError: true},
  {pingResponse: '/ping 1 invalid'},
  {pairResponse: '/pair 1  connection_period_expired'},
  {pairResponse: '/pair 1 rng_failure'},
  {pairResponse: '/pair 0 invalid'},
  {silentCommand: '/ping', timeout: 10},
  {silentCommand: '/pair', timeout: 10}
]) {
  test(`Bowser failed connection releases the port and allows retry: ${JSON.stringify(options)}`, async () => {
    const state = serialHarness({...options})
    const {instance: signer, events} = state
    assert.equal(await signer.openSerialPort(), false)
    assert.equal(signer.selectedPort, null)
    assert.equal(signer.isConnecting, false)
    assert.equal(signer.isConnected(), false)
    assert.equal(signer.sharedSecret, null)
    assert.equal(signer.reader, null)
    assert.equal(signer.writer, null)
    assert.equal(events.length, 0)
    assert.equal(state.closes, 1)
    assert.deepEqual(Object.keys(signer.pendingCommands), [])
    if (options.pairResponse?.includes('connection_period_expired')) {
      assert.match(state.notifications.at(-1).caption, /Restart Bowser/)
    }
    for (const key of Object.keys(state.options)) delete state.options[key]
    const retry = signer.openSerialPort()
    await until(() => state.dialog)
    state.dialog.accept()
    assert.equal(await retry, true)
    await signer.closeSerialPort(false)
    assert.equal(state.closes, 2)
  })
}

for (const mode of ['cancel', 'disconnect', 'end', 'error']) {
  test(`Bowser ${mode} during code confirmation cannot mark a closed port connected`, async () => {
    const state = serialHarness()
    const {instance: signer, events} = state
    const connecting = signer.openSerialPort()
    await until(() => state.dialog)
    if (mode === 'cancel') state.dialog.hide()
    else state[mode]()
    assert.equal(await connecting, false)
    state.dialog.accept() // A late dialog callback must not revive the session.
    assert.equal(signer.isConnected(), false)
    assert.equal(signer.selectedPort, null)
    assert.equal(signer.sharedSecret, null)
    assert.equal(events.length, 0)
    assert.equal(state.closes, 1)
  })
}

test('Bowser unplug rejects an in-flight command and reconnect uses fresh streams', async () => {
  const state = serialHarness({silentCommand: '/xpub'})
  const {instance: signer} = state
  const connecting = signer.openSerialPort()
  await until(() => state.dialog)
  state.dialog.accept()
  await connecting
  const xpub = assert.rejects(
    signer.hwwXpub("m/84'/1'/0'"),
    /connection closed/
  )
  state.disconnect()
  await xpub
  await signer.closePromise
  assert.equal(signer.isConnected(), false)
  assert.equal(signer.selectedPort, null)
  assert.deepEqual(Object.keys(signer.xpubData), [])
  const oldDialog = state.dialog
  const reconnecting = signer.openSerialPort()
  await until(() => state.dialog !== oldDialog)
  state.dialog.accept()
  assert.equal(await reconnecting, true)
  await signer.closeSerialPort(false)
  assert.equal(state.closes, 2)
})

test('leaving Watchonly while the serial chooser is open cancels the connection', async () => {
  const state = serialHarness()
  const {instance: signer, context, component} = state
  let selectPort
  context.navigator.serial.requestPort = () =>
    new Promise(resolve => {
      selectPort = resolve
    })
  const connecting = signer.openSerialPort()
  component.beforeUnmount.call(signer)
  await signer.closePromise
  selectPort(state.port)
  assert.equal(await connecting, false)
  assert.equal(signer.selectedPort, null)
  assert.equal(state.commands.length, 0)
})

test('leaving Watchonly during serial open releases the port when open finishes', async () => {
  const state = serialHarness()
  const {instance: signer, component} = state
  const open = state.port.open.bind(state.port)
  let opened
  state.port.open = async config => {
    await new Promise(resolve => {
      opened = resolve
    })
    await open(config)
  }
  const connecting = signer.openSerialPort()
  await until(() => opened)
  component.beforeUnmount.call(signer)
  await signer.closePromise
  opened()
  assert.equal(await connecting, false)
  assert.equal(signer.selectedPort, null)
  assert.equal(state.commands.length, 0)
  assert.equal(state.closes, 2)
})

for (const [command, method] of [
  ['/wipe', 'hwwWipe'],
  ['/restore', 'hwwRestore']
]) {
  test(`Bowser ${command} success unlocks seed viewing on the existing connection`, async () => {
    const {instance: signer} = harness()
    const port = {}
    const writer = {}
    const reader = {}
    const sharedSecret = new Uint8Array(32).fill(1)
    const privateKey = new Uint8Array(32).fill(2)
    Object.assign(signer, {
      selectedPort: port,
      writer,
      reader,
      sharedSecret,
      decryptionKey: privateKey,
      xpubData: {xpub: 'previous-wallet'}
    })
    const commands = []
    signer.sendCommandSecure = async (name, args) => {
      commands.push([name, args])
      await signer.handleSerialPortResponse(
        name,
        name === '/seed' ? '1 displayed' : '1'
      )
    }
    signer.hww.password = 'test-password'
    signer.hww.confirmedPassword = 'test-password'
    signer.hww.mnemonic = 'test mnemonic'
    await signer[method]()
    assert.equal(commands[0][0], command)
    assert.equal(signer.isAuthenticated(), true)
    assert.equal(signer.selectedPort, port)
    assert.equal(signer.writer, writer)
    assert.equal(signer.reader, reader)
    assert.equal(signer.sharedSecret, sharedSecret)
    assert.equal(signer.decryptionKey, privateKey)
    assert.deepEqual(Object.keys(signer.xpubData), [])
    if (command === '/restore') {
      assert.equal(signer.hww.showSeedDialog, false)
      await signer.hwwShowSeed()
    }
    assert.equal(signer.hww.showSeedDialog, true)
    assert.equal(commands[1][0], '/seed')
    assert.equal(commands[1][1][0], 1)
    assert.equal(commands.length, 2)
  })

  test(`Bowser ${command} failure locks the UI without breaking response handling`, async () => {
    const {instance: signer} = harness()
    const port = {}
    signer.selectedPort = port
    signer.hww.authenticated = true
    signer.hww.password = 'test-password'
    signer.hww.confirmedPassword = 'test-password'
    signer.hww.mnemonic = 'test mnemonic'
    signer.sendCommandSecure = async name => {
      assert.equal(name, command)
      await signer.handleSerialPortResponse(name, '0')
    }
    const notifications = []
    signer.$q.notify = message => notifications.push(message)
    await signer[method]()
    assert.equal(signer.isAuthenticated(), false)
    assert.equal(signer.hww.showSeedDialog, false)
    assert.equal(signer.selectedPort, port)
    assert.equal(notifications[0].type, 'warning')
    await signer.handleSerialPortResponse('/password', '1')
    assert.equal(signer.isAuthenticated(), false)
  })
}

test('Bowser seed navigation waits for acknowledgement and prevents repeated clicks', async () => {
  const {instance: signer} = harness()
  const sent = []
  signer.sendCommandSecure = async (command, args) => sent.push([command, args])
  signer.hww.showSeedDialog = true
  const next = signer.showNextSeedWord()
  await signer.showNextSeedWord()
  assert.equal(sent.length, 1)
  assert.equal(signer.hww.seedWordPosition, 1)
  assert.equal(signer.hww.seedLoading, true)
  await signer.handleSerialPortResponse('/seed', '2 displayed')
  await next
  assert.equal(signer.hww.seedWordPosition, 2)
  assert.equal(signer.hww.seedLoading, false)
  await signer.handleSerialPortResponse('/seed', '3 displayed')
  assert.equal(signer.hww.seedWordPosition, 3)
  signer.hww.showSeedDialog = false
  await signer.handleSerialPortResponse('/seed', '4 displayed')
  assert.equal(signer.hww.seedWordPosition, 3)
})

test('Bowser address verification rejects a mismatched device address', async () => {
  const {instance: signer} = harness()
  const notices = []
  signer.$q.notify = notice => notices.push(notice)
  signer.requestCommand = async () => '1 wrong-address'
  await signer.hwwShowAddress("m/84'/1'/0'/0/0", 'expected-address')
  assert.equal(notices.length, 1)
  assert.match(notices[0].caption, /did not match/)
  signer.requestCommand = async () => '1 expected-address'
  await signer.hwwShowAddress("m/84'/1'/0'/0/0", 'expected-address')
  assert.equal(notices.length, 1)
})

test('Bowser serializes requests and a stale write failure cannot cancel a new request', async () => {
  const {instance: signer} = harness()
  let rejectWrite
  let resolveWrite
  signer.sendCommandSecure = () =>
    new Promise((resolve, reject) => {
      resolveWrite = resolve
      rejectWrite = reject
    })
  await assert.rejects(signer.requestCommand('/xpub', [], 5), /timed out/)
  const rejectOldWrite = rejectWrite
  const next = signer.requestCommand('/xpub', [], 1000)
  await assert.rejects(
    signer.requestCommand('/wipe', [], 1000),
    /already pending/
  )
  rejectOldWrite(new Error('late write failure'))
  await Promise.resolve()
  await signer.handleSerialPortResponse('/xpub', '1 xpub 00112233')
  resolveWrite()
  assert.equal(await next, '1 xpub 00112233')
})

for (const writeFails of [false, true]) {
  test(`Bowser waits for the ping write before pairing, including write failure: ${writeFails}`, async () => {
    const state = serialHarness()
    const {instance: signer, commands} = state
    const send = signer.sendCommandClearText
    let finishWrite
    signer.sendCommandClearText = async (command, attrs) => {
      await send(command, attrs)
      if (command === '/ping') {
        await new Promise((resolve, reject) => {
          finishWrite = () =>
            writeFails ? reject(new Error('Serial write failed')) : resolve()
        })
      }
    }
    const connecting = signer.openSerialPort()
    await until(() => finishWrite && !signer.pendingCommands['/ping'])
    assert.equal(state.dialog, undefined)
    assert.deepEqual(
      commands.map(line => line.split(' ')[0]),
      ['/ping']
    )
    finishWrite()
    if (writeFails) {
      assert.equal(await connecting, false)
      assert.equal(state.closes, 1)
      assert.match(state.notifications.at(-1).caption, /Serial write failed/)
      assert.deepEqual(
        commands.map(line => line.split(' ')[0]),
        ['/ping']
      )
    } else {
      await until(() => state.dialog)
      state.dialog.accept()
      assert.equal(await connecting, true)
      assert.deepEqual(
        commands.map(line => line.split(' ')[0]),
        ['/ping', '/pair']
      )
      await signer.closeSerialPort(false)
    }
  })
}

for (const method of ['hwwWipe', 'hwwRestore']) {
  test(`Bowser ${method} exposes progress and ignores duplicate submissions`, async () => {
    const {instance: signer} = harness()
    let finish
    let calls = 0
    signer.requestCommand = () => {
      calls++
      return new Promise(resolve => {
        finish = resolve
      })
    }
    signer.hww.password = 'test-password'
    signer.hww.confirmedPassword = 'test-password'
    signer.hww.mnemonic = 'test-only mnemonic'
    signer.hww.showWipeDialog = method === 'hwwWipe'
    signer.hww.showRestoreDialog = method === 'hwwRestore'
    const pending = signer[method]()
    assert.equal(signer.hww.settingUp, true)
    assert.equal(
      signer.hww.showWipeDialog || signer.hww.showRestoreDialog,
      true
    )
    await signer[method]()
    assert.equal(calls, 1)
    finish('0')
    await pending
    assert.equal(signer.hww.settingUp, false)
    assert.equal(
      signer.hww.showWipeDialog || signer.hww.showRestoreDialog,
      false
    )
    assert.equal(signer.hww.password, null)
  })

  test(`Bowser ${method} rejects passwords that cannot be sent as a single token`, async () => {
    const {instance: signer} = harness()
    signer.sendCommandSecure = () =>
      assert.fail('Invalid password must not be sent')
    const notices = []
    signer.$q.notify = notice => notices.push(notice)
    signer.hww.password = 'password with spaces'
    signer.hww.confirmedPassword = signer.hww.password
    signer.hww.mnemonic = 'test mnemonic'
    await signer[method]()
    assert.match(notices[0].caption, /without spaces/)
    assert.equal(signer.hww.password, null)
  })
}

test('Account paths reject malformed and out-of-range indices', () => {
  const {context} = harness()
  for (const path of ['m', "m/84'/1'/0'", 'm/0/2147483647'])
    assert.equal(context.findAccountPathIssues(path), undefined)
  for (const path of ['m/', 'm//0', 'm/1x', 'm/-1', 'm/1.5', 'm/2147483648'])
    assert.ok(context.findAccountPathIssues(path))
})

test('Bowser TRNG runs over encrypted serial without unlocking or exporting raw samples', async () => {
  const state = serialHarness()
  const {instance: signer, timers, commands} = state
  const connecting = signer.openSerialPort()
  await until(() => state.dialog)
  state.dialog.accept()
  await connecting
  assert.equal(signer.hww.authenticated, false)
  await signer.hwwTestTrng()
  assert.equal(commands.at(-1), '/trng')
  assert.ok(timers.includes(60000))
  assert.equal(signer.trng.showDialog, true)
  assert.equal(signer.trng.running, false)
  assert.equal(signer.trng.result.looksHealthy, true)
  assert.equal(signer.trng.result.samples, 5000)
  assert.equal(signer.trng.result.chiSquared, 103.42)
  assert.equal(signer.trng.result.minimumCount, 34)
  assert.equal(signer.trng.result.maximumCount, 69)
  await signer.closeSerialPort(false)
  assert.equal(signer.trng.showDialog, false)
  assert.equal(signer.trng.result, null)
})

test('Bowser TRNG shows an unexpected distribution without turning it into a passing result', async () => {
  const {instance: signer} = harness()
  signer.connected = true
  signer.requestCommand = async () => '1 5000 160.25 22 83 unexpected'
  await signer.hwwTestTrng()
  assert.equal(signer.trng.result.looksHealthy, false)
  assert.equal(signer.trng.error, null)
})

for (const response of [
  '0 health_failed',
  '1 4999 103.42 34 69 healthy',
  '1 5000 NaN 34 69 healthy',
  '1 5000 -1 34 69 healthy',
  '1 5000 103.42 -1 69 healthy',
  '1 5000 103.42 34 33 healthy',
  '1 5000 103.42 34 5001 healthy',
  '1 5000 103.42 34 69 unknown',
  '1 5000 103.42 34 69 healthy extra'
]) {
  test(`Bowser TRNG refuses invalid diagnostic response: ${response}`, async () => {
    const {instance: signer} = harness()
    signer.connected = true
    signer.trng.result = {looksHealthy: true}
    signer.requestCommand = async () => response
    await signer.hwwTestTrng()
    assert.equal(signer.trng.result, null)
    assert.equal(signer.trng.running, false)
    assert.equal(
      signer.trng.error,
      'Bowser Wallet did not complete the TRNG visual check'
    )
  })
}

for (const mode of ['timeout', 'disconnect']) {
  test(`Bowser TRNG ${mode} settles the pending check`, async () => {
    const {instance: signer} = harness('serial-signer', {}, () => 5)
    signer.connected = true
    signer.sendCommandSecure = async () => {}
    const checking = signer.hwwTestTrng()
    assert.equal(signer.trng.running, true)
    if (mode === 'disconnect') await signer.closeSerialPort(false)
    await checking
    assert.equal(signer.trng.result, null)
    assert.equal(signer.trng.running, false)
    assert.match(signer.trng.error, mode === 'timeout' ? /timed out/ : /closed/)
    assert.deepEqual(Object.keys(signer.pendingCommands), [])
  })
}

test('Bowser TRNG cannot start disconnected, during signing or unlock, or twice concurrently', async () => {
  const {instance: signer} = harness()
  let calls = 0
  let complete
  signer.requestCommand = () => {
    calls++
    return new Promise(resolve => {
      complete = resolve
    })
  }
  await signer.hwwTestTrng()
  assert.equal(calls, 0)
  signer.connected = true
  for (const busy of ['loggingIn', 'sendingPsbt', 'signingPsbt']) {
    signer.hww[busy] = true
    await signer.hwwTestTrng()
    assert.equal(calls, 0)
    signer.hww[busy] = false
  }
  const checking = signer.hwwTestTrng()
  await signer.hwwTestTrng()
  assert.equal(calls, 1)
  complete('1 5000 103.42 34 69 healthy')
  await checking
})

test('Bowser uploads acknowledged chunks and signs only after physical review', async () => {
  const {instance: signer, events} = harness()
  signer.hww.authenticated = true
  const commands = []
  const chunks = []
  let releaseReview
  signer.sendCommandSecure = async (command, args) => {
    commands.push(command)
    if (command === '/psbt-begin') {
      await signer.handleSerialPortResponse(
        command,
        `1 ${Math.ceil(args[1] / 64)}`
      )
    } else if (command === '/psbt-chunk') {
      assert.ok(args[1].length <= 64)
      chunks.push(args[1])
      await signer.handleSerialPortResponse(command, `1 ${args[0]}`)
    } else if (command === '/psbt-commit') {
      await signer.handleSerialPortResponse('/psbt-review', 'output 0 1')
      releaseReview = () => signer.handleSerialPortResponse(command, '1')
    } else if (command === '/sign') {
      await signer.handleSerialPortResponse('/psbt-review', 'sign')
      await signer.handleSerialPortResponse(command, '1 cHNidP8signed')
    }
  }
  const psbt = 'cHNidP8' + 'A'.repeat(140)
  const signing = signer.hwwSendPsbt(psbt, transaction())
  while (!releaseReview) await new Promise(resolve => setImmediate(resolve))
  assert.equal(chunks.join(''), psbt)
  assert.equal(signer.hww.confirm.stage, 'output')
  assert.ok(!commands.includes('/sign'))
  await signer.handleSerialPortResponse('/psbt-review', 'output 9 1')
  assert.equal(signer.hww.confirm.outputIndex, 0)
  await signer.handleSerialPortResponse('/psbt-review', 'fee')
  assert.equal(signer.hww.confirm.showFee, true)
  await releaseReview()
  await signing
  assert.deepEqual(events, [['signed:psbt', 'cHNidP8signed']])
  assert.ok(!commands.includes('/confirm-next'))
  assert.equal(signer.hww.showConfirmationDialog, false)
})

for (const [failureAt, response] of [
  ['/psbt-begin', '0 no_memory'],
  ['/psbt-chunk', '1 99'],
  ['/psbt-commit', 'review_rejected'],
  ['/sign', 'review_rejected']
]) {
  test(`Bowser stops on ${failureAt} rejection`, async () => {
    const {instance: signer, events} = harness()
    signer.hww.authenticated = true
    const commands = []
    signer.sendCommandSecure = async command => {
      commands.push(command)
      const replies = {
        '/psbt-begin': '1 1',
        '/psbt-chunk': '1 0',
        '/psbt-commit': '1'
      }
      await signer.handleSerialPortResponse(
        command,
        command === failureAt ? response : replies[command]
      )
    }
    await assert.rejects(signer.hwwSendPsbt('cHNidP8', transaction()))
    assert.equal(commands.at(-1), failureAt)
    assert.equal(events.length, 0)
    assert.equal(signer.hww.sendingPsbt, false)
    assert.equal(signer.hww.signingPsbt, false)
    assert.deepEqual(Object.keys(signer.pendingCommands), [])
  })
}

test('Bowser enforces its size/count limits without sending data', async () => {
  const {instance: signer} = harness()
  signer.hww.authenticated = true
  signer.sendCommandSecure = () => assert.fail('must not send')
  await assert.rejects(
    signer.hwwSendPsbt('A'.repeat(16385), transaction()),
    /16,384/
  )
  await assert.rejects(
    signer.hwwSendPsbt('cHNidP8', {
      ...transaction(),
      inputs: Array(65).fill({})
    }),
    /64 inputs/
  )
})

test('Bowser request failures settle on timeout, disconnect, reboot and write error', async () => {
  for (const mode of ['timeout', 'disconnect', 'reboot', 'write']) {
    const {instance: signer} = harness()
    signer.sendCommandSecure = async () => {
      if (mode === 'write') throw new Error('write failed')
    }
    const response = signer.requestCommand('/psbt-commit', [], 5)
    const rejected = assert.rejects(response)
    if (mode === 'disconnect')
      signer.failPendingCommands(new Error('disconnected'))
    if (mode === 'reboot')
      await signer.handleSerialPortResponse('/password-clear', '1')
    await rejected
    assert.deepEqual(Object.keys(signer.pendingCommands), [])
  }
})

test('Bowser recognizes plaintext transfer/review and empty-wallet messages', async () => {
  const {instance: signer} = harness()
  signer.decryptData = () => assert.fail('plaintext must not be decrypted')
  for (const line of [
    '/psbt-begin 1 2',
    '/psbt-chunk 1 0',
    '/psbt-review output 0 1',
    '/new'
  ]) {
    const parsed = await signer.extractCommand(line)
    assert.equal(parsed.command, line.split(' ')[0])
  }
})

test('Bowser unlock and xpub handle immediate responses without resolver races', async () => {
  const {instance: signer, timers} = harness()
  signer.sendCommandSecure = async (command, args) => {
    if (command === '/password') {
      assert.deepEqual(Array.from(args), ['test-password', ''])
      await signer.handleSerialPortResponse(command, '1')
    } else
      await signer.handleSerialPortResponse(command, '1 tpubExample 00112233')
  }
  await signer.hwwShowPasswordDialog()
  signer.hww.password = 'test-password'
  const login = signer.isAuthenticating()
  await signer.hwwLogin()
  assert.equal(await login, true)
  assert.ok(timers.includes(120000))
  await signer.hwwXpub("m/84'/1'/0'")
  assert.equal((await signer.isFetchingXpub()).fingerprint, '00112233')
  assert.equal(signer.hww.password, null)
})

test('canceling Bowser unlock settles the waiting payment', async () => {
  const {instance: signer} = harness()
  await signer.hwwShowPasswordDialog()
  const login = signer.isAuthenticating()
  signer.passwordDialogClosed()
  assert.equal(await login, false)
})

test('Bowser unlock preserves UTF-8 and surrounding spaces in passphrases', async () => {
  const {instance: signer} = harness()
  signer.connected = true
  signer.sharedSecret = new Uint8Array(32).fill(1)
  let written
  signer.writer = {
    write: async value => {
      written = new TextDecoder().decode(value).trim()
      await signer.handleSerialPortResponse('/password', '1')
    }
  }
  signer.hww.password = 'test-password'
  signer.hww.hasPassphrase = true
  signer.hww.passphrase = '  caf\u00e9 space  '
  await signer.hwwLogin()
  assert.equal(
    await signer.decryptData(written),
    '/password test-password   caf\u00e9 space  '
  )
  assert.equal(signer.hww.passphrase, null)
  assert.equal(signer.isAuthenticated(), true)
})

test('Bowser keeps seed acknowledgements on-device and omits response data from logs', async () => {
  const {instance: signer, logs} = harness()
  signer.handleShowSeedResponse('24 displayed')
  assert.equal(signer.hww.seedWordPosition, 24)
  assert.equal(signer.hww.seedWord, null)
  signer.logPublicCommandsResponse('/xpub', 'private test payload')
  await signer.handleSerialPortResponse('/log', 'private test payload')
  assert.ok(!JSON.stringify(logs).includes('private test payload'))
})

test('Bowser Testnet4 uses the existing Testnet hardware protocol', async () => {
  const {instance: signer} = harness()
  signer.network = 'Testnet4'
  signer.hww.authenticated = true
  const commands = []
  signer.sendCommandSecure = async (command, args) => {
    commands.push([command, args])
  }
  signer.requestCommand = async (command, args) => {
    commands.push([command, args])
    return {
      '/xpub': '1 tpubExample 00112233',
      '/address': '1 tb1qExample',
      '/psbt-begin': '1 1',
      '/psbt-chunk': '1 0',
      '/psbt-commit': '1',
      '/sign': '1 cHNidP8signed'
    }[command]
  }
  await signer.hwwXpub("m/84'/1'/0'")
  await signer.hwwShowAddress("m/84'/1'/0'/0/0", 'tb1qExample')
  await signer.hwwSendPsbt('cHNidP8', transaction())
  for (const command of ['/xpub', '/address', '/psbt-begin']) {
    assert.equal(commands.find(([name]) => name === command)[1][0], 'Testnet')
  }
})

test('Trezor connection cancellation is not reported as connected', async () => {
  const {instance: signer, events} = harness('trezor-signer', {
    getFeatures: async () => ({success: false, payload: {error: 'Cancelled'}})
  })
  await signer.connectToDevice()
  assert.equal(signer.connected, false)
  assert.equal(signer.isConnecting, false)
  assert.equal(events.length, 0)
})

test('Trezor fingerprints preserve leading zeroes for account origins', async () => {
  const {instance: signer} = harness('trezor-signer', {
    getPublicKey: async () => ({
      success: true,
      payload: {xpub: 'test-xpub', fingerprint: 0x1234}
    })
  })
  await signer.hwwXpub("m/84'/1'/0'")
  assert.equal(signer.xpubData.fingerprint, '00001234')
  assert.equal(signer.isAuthenticated(), true)
})

for (const network of ['Mainnet', 'Testnet', 'Testnet4']) {
  test(`Trezor ${network} connects and imports using Trezor Connect`, async () => {
    let requested
    const features = {success: true, payload: {label: 'Test Trezor'}}
    const {instance: signer, events} = harness('trezor-signer', {
      getFeatures: async () => features,
      getPublicKey: async args => {
        requested = args
        return {
          success: true,
          payload: {xpub: 'trezor-xpub', fingerprint: 0x1234abcd}
        }
      }
    })
    signer.network = network
    await signer.connectToDevice()
    assert.equal(signer.isConnected(), true)
    assert.equal(signer.features, features)
    assert.deepEqual(events, [['device:connected', 'trezor-device']])
    const path = network === 'Mainnet' ? "m/84'/0'/0'" : "m/84'/1'/0'"
    await signer.hwwXpub(path)
    assert.equal(requested.path, path)
    assert.equal(requested.coin, network === 'Mainnet' ? 'btc' : 'test')
    assert.equal(requested.showOnTrezor, true)
    assert.equal(signer.xpubData.xpub, 'trezor-xpub')
    assert.equal(signer.xpubData.fingerprint, '1234abcd')
  })

  for (const [accountType, inputType, outputType] of [
    ['p2pkh', 'SPENDADDRESS', 'PAYTOADDRESS'],
    ['p2sh', 'SPENDP2SHWITNESS', 'PAYTOP2SHWITNESS'],
    ['p2wpkh', 'SPENDWITNESS', 'PAYTOWITNESS'],
    ['p2tr', 'SPENDTAPROOT', 'PAYTOTAPROOT']
  ]) {
    test(`Trezor ${network} ${accountType} retains its native signing contract`, async () => {
      let submitted
      const {instance: signer, events} = harness('trezor-signer', {
        signTransaction: async tx => {
          submitted = tx
          return {success: true, payload: {serializedTx: 'signed-trezor-tx'}}
        }
      })
      signer.network = network
      const tx = transaction()
      tx.inputs[0].accountType = accountType
      tx.outputs.push({
        accountPath: tx.inputs[0].accountPath,
        branch_index: 1,
        address_index: 0,
        accountType,
        amount: 100
      })
      await signer.hwwSendPsbt('ignored PSBT', tx)
      assert.equal(submitted.coin, network === 'Mainnet' ? 'btc' : 'test')
      assert.equal(submitted.inputs[0].script_type, inputType)
      assert.equal(submitted.outputs[1].script_type, outputType)
      assert.equal(submitted.outputs[0].address, 'recipient')
      assert.equal(events[0][0], 'signed:tx')
      assert.equal(events[0][1].serializedTx, 'signed-trezor-tx')
      assert.equal(events[0][1].feeValue, 1000)
    })
  }
}

for (const matches of [true, false]) {
  test(`Trezor receive verification checks the returned address: ${matches}`, async () => {
    let requested
    const {instance: signer} = harness('trezor-signer', {
      getAddress: async args => {
        requested = args
        return {
          success: true,
          payload: {address: matches ? 'expected-address' : 'different-address'}
        }
      }
    })
    signer.network = 'Testnet4'
    const verify = signer.hwwShowAddress("m/84'/1'/0'/0/1", 'expected-address')
    if (matches) await verify
    else await assert.rejects(verify, /does not match/)
    assert.equal(requested.coin, 'test')
    assert.equal(requested.showOnTrezor, true)
  })
}
