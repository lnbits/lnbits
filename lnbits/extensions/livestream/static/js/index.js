/* globals Quasar, Vue, _, VueQrcode, windowMixin, LNbits, LOCALE */

Vue.component(VueQrcode.name, VueQrcode)

new Vue({
  el: '#vue',
  mixins: [windowMixin],
  data() {
    return {
      cancelListener: () => {},
      selectedWallet: null,
      nextCurrentTrack: null,
      livestream: {
        tracks: [],
        producers: []
      },
      trackDialog: {
        show: false,
        data: {}
      }
    }
  },
  computed: {
    sortedTracks() {
      return this.livestream.tracks.sort((a, b) => a.name - b.name)
    },
    tracksMap() {
      return Object.fromEntries(
        this.livestream.tracks.map(track => [track.id, track])
      )
    },
    producersMap() {
      return Object.fromEntries(
        this.livestream.producers.map(prod => [prod.id, prod])
      )
    }
  },
  methods: {
    getTrackLabel(trackId) {
      let track = this.tracksMap[trackId]
      return `${track.name}, ${this.producersMap[track.producer].name}`
    },
    disabledAddTrackButton() {
      return (
        !this.trackDialog.data.name ||
        this.trackDialog.data.name.length === 0 ||
        !this.trackDialog.data.producer ||
        this.trackDialog.data.producer.length === 0
      )
    },
    changedWallet(wallet) {
      this.selectedWallet = wallet
      this.loadLivestream()
      this.startPaymentNotifier()
    },
    loadLivestream() {
      LNbits.api
        .request(
          'GET',
          '/livestream/api/v1/livestream',
          this.selectedWallet.inkey
        )
        .then(response => {
          this.livestream = response.data
          this.nextCurrentTrack = this.livestream.current_track
        })
        .catch(err => {
          LNbits.utils.notifyApiError(err)
        })
    },
    startPaymentNotifier() {
      this.cancelListener()

      this.cancelListener = LNbits.events.onInvoicePaid(
        this.selectedWallet,
        payment => {
          let satoshiAmount = Math.round(payment.amount / 1000)
          let trackName = (
            this.tracksMap[payment.extra.track] || {name: '[unknown]'}
          ).name

          this.$q.notify({
            message: `Someone paid <b>${satoshiAmount} sat</b> for the track <em>${trackName}</em>.`,
            caption: payment.extra.comment
              ? `<em>"${payment.extra.comment}"</em>`
              : undefined,
            color: 'secondary',
            html: true,
            timeout: 0,
            actions: [{label: 'Dismiss', color: 'white', handler: () => {}}]
          })
        }
      )
    },
    addTrack() {
      let {id, name, producer, price_sat, download_url} = this.trackDialog.data

      const [method, path] = id
        ? ['PUT', `/livestream/api/v1/livestream/tracks/${id}`]
        : ['POST', '/livestream/api/v1/livestream/tracks']

      LNbits.api
        .request(method, path, this.selectedWallet.inkey, {
          download_url:
            download_url && download_url.length > 0 ? download_url : undefined,
          name,
          price_msat: price_sat * 1000 || 0,
          producer_name: typeof producer === 'string' ? producer : undefined,
          producer_id: typeof producer === 'object' ? producer.id : undefined
        })
        .then(response => {
          this.$q.notify({
            message: `Track '${this.trackDialog.data.name}' added.`,
            timeout: 700
          })
          this.loadLivestream()
          this.trackDialog.show = false
          this.trackDialog.data = {}
        })
        .catch(err => {
          LNbits.utils.notifyApiError(err)
        })
    },
    openAddTrackDialog() {
      this.trackDialog.show = true
      this.trackDialog.data = {}
    },
    openUpdateDialog(itemId) {
      this.trackDialog.show = true
      let item = this.livestream.tracks.find(item => item.id === itemId)
      this.trackDialog.data = {
        ...item,
        producer: this.livestream.producers.find(
          prod => prod.id === item.producer
        ),
        price_sat: Math.round(item.price_msat / 1000)
      }
    },
    deleteTrack(trackId) {
      LNbits.utils
        .confirmDialog('Are you sure you want to delete this track?')
        .onOk(() => {
          LNbits.api
            .request(
              'DELETE',
              '/livestream/api/v1/livestream/tracks/' + trackId,
              this.selectedWallet.inkey
            )
            .then(response => {
              this.$q.notify({
                message: `Track deleted`,
                timeout: 700
              })
              this.livestream.tracks.splice(
                this.livestream.tracks.findIndex(track => track.id === trackId),
                1
              )
            })
            .catch(err => {
              LNbits.utils.notifyApiError(err)
            })
        })
    },
    updateCurrentTrack(track) {
      if (this.livestream.current_track === track) {
        // if clicking the same, stop it
        track = 0
      }

      LNbits.api
        .request(
          'PUT',
          '/livestream/api/v1/livestream/track/' + track,
          this.selectedWallet.inkey
        )
        .then(() => {
          this.livestream.current_track = track
          this.$q.notify({
            message: `Current track updated.`,
            timeout: 700
          })
        })
        .catch(err => {
          LNbits.utils.notifyApiError(err)
        })
    },
    updateFeePct() {
      LNbits.api
        .request(
          'PUT',
          '/livestream/api/v1/livestream/fee/' + this.livestream.fee_pct,
          this.selectedWallet.inkey
        )
        .then(() => {
          this.$q.notify({
            message: `Percentage updated.`,
            timeout: 700
          })
        })
        .catch(err => {
          LNbits.utils.notifyApiError(err)
        })
    },
    producerAdded(added, cb) {
      cb(added)
    }
  },
  created() {
    this.selectedWallet = this.g.user.wallets[0]
    this.loadLivestream()
    this.startPaymentNotifier()
  }
})
