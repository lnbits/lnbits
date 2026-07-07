window.__lnbitsWasmTestExtensionLoaded = true

;(function () {
  const channel = new MessageChannel()
  const pending = new Map()
  let counter = 0

  const ready = new Promise(resolve => {
    channel.port1.addEventListener('message', event => {
      const message = event.data || {}

      if (message.type === 'lnbits-extension:connected') {
        resolve(true)
        return
      }

      if (message.type !== 'lnbits-extension:response') return
      const callback = pending.get(message.id)
      if (!callback) return

      pending.delete(message.id)
      callback(message)
    })
    channel.port1.start()
    window.parent.postMessage(
      {type: 'lnbits-extension:connect', id: 'wasm-test-extension'},
      '*',
      [channel.port2]
    )
  })

  window.lnbitsWasmTestBridge = {
    ready() {
      return ready
    },
    request(message) {
      return ready.then(() => {
        return new Promise(resolve => {
          const id = `wasm-test-${++counter}`
          pending.set(id, resolve)
          channel.port1.postMessage({
            type: 'lnbits-extension:request',
            id,
            ...message
          })
        })
      })
    }
  }
})()
