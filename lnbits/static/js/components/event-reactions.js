Vue.component('lnbits-event-reactions', {
  name: 'lnbits-event-reactions',
  methods: {
    makeItRain() {
        document.getElementById("vue").disabled = true
        var end = Date.now() + (2 * 1000)
        var colors = ['#FFD700', '#ffffff']
        function frame() {
          confetti({
            particleCount: 2,
            angle: 60,
            spread: 55,
            origin: { x: 0 },
            colors: colors,
            zIndex: 999999
          })
          confetti({
            particleCount: 2,
            angle: 120,
            spread: 55,
            origin: { x: 1 },
            colors: colors,
            zIndex: 999999
          })
          if (Date.now() < end) {
            requestAnimationFrame(frame)
          }
          else {
            document.getElementById("vue").disabled = false
          }
        }
        frame()
      },
      connectWebocket(event_id) {
        self = this
        if (location.protocol !== 'http:') {
          localUrl =
            'wss://' +
            document.domain +
            ':' +
            location.port +
            '/api/v1/ws/' +
            wallet_id
        } else {
          localUrl =
            'ws://' +
            document.domain +
            ':' +
            location.port +
            '/api/v1/ws/' +
            wallet_id
        }
        this.connection = new WebSocket(localUrl)
        this.connection.onmessage = function (e) {
          self.makeItRain()
        }
      }
  }
})