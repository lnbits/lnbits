/* globals Quasar, Vue, _, VueQrcode, windowMixin, LNbits, LOCALE */

Vue.component(VueQrcode.name, VueQrcode)

var locationPath = [
  window.location.protocol,
  '//',
  window.location.host,
  window.location.pathname
].join('')

var mapPodcastpod = obj => {
  obj._data = _.clone(obj)
  obj.date = Quasar.utils.date.formatDate(
    new Date(obj.time * 1000),
    'YYYY-MM-DD HH:mm'
  )
  obj.amount = new Intl.NumberFormat(LOCALE).format(obj.amount)
  obj.print_url = [locationPath, 'print/', obj.id].join('')
  obj.Podcast_url = [locationPath, obj.id].join('')
  return obj
}

new Vue({
  el: '#vue',
  mixins: [windowMixin],
  data() {
    return {
      categoryOptions: ['seconds', 'minutes', 'hours'],
      countryOptions: ['seconds', 'minutes', 'hours'],
      languageOptions: ['seconds', 'minutes', 'hours'],
      podcastOptions: ['seconds', 'minutes', 'hours'],
      typeOptions: ['seconds', 'minutes', 'hours'],
      currencies: [],
      fiatRates: {},
      checker: null,
      Podcastpods: [],
      PodcastpodsTable: {
        pagination: {
          rowsPerPage: 10
        }
      },
      nfcTagWriting: false,
      formDialogPodcast: {
        show: false,
        fixedAmount: true,
        data: {explicit: false}
      },
      formDialogEpisode: {
        show: false,
        fixedAmount: true,
        data: {}
      },
      qrCodeDialog: {
        show: false,
        data: null
      }
    }
  },
  methods: {
    imageAdded(file) {
      let blobURL = URL.createObjectURL(file)
      let image = new Image()
      image.src = blobURL
      image.onload = async () => {
        let canvas = document.createElement('canvas')
        canvas.setAttribute('width', 100)
        canvas.setAttribute('height', 100)
        await pica.resize(image, canvas, {
          quality: 0,
          alpha: true,
          unsharpAmount: 95,
          unsharpRadius: 0.9,
          unsharpThreshold: 70
        })
        this.formDialogPodcast.data.image = canvas.toDataURL()
        this.formDialogPodcast = {...this.formDialogPodcast}
      }
    },
    imageCleared() {
      this.formDialogPodcast.data.image = null
      this.formDialogPodcast = {...this.formDialogPodcast}
    },
    fileAdded(file) {
      let blobURL = URL.createObjectURL(file)
      let image = new Image()
      image.src = blobURL
      image.onload = async () => {
        let canvas = document.createElement('canvas')
        canvas.setAttribute('width', 100)
        canvas.setAttribute('height', 100)
        await pica.resize(image, canvas, {
          quality: 0,
          alpha: true,
          unsharpAmount: 95,
          unsharpRadius: 0.9,
          unsharpThreshold: 70
        })
        this.formDialogEpisode.data.image = canvas.toDataURL()
        this.formDialogEpisode = {...this.formDialogEpisode}
      }
    },
    fileCleared() {
      this.formDialogEpisode.data.image = null
      this.formDialogEpisode = {...this.formDialogEpisode}
    },
    getPodcasts() {
      LNbits.api
        .request(
          'GET',
          '/podcast/api/v1/pods?all_wallets=true',
          this.g.user.wallets[0].inkey
        )
        .then(response => {
          this.Podcastpods = response.data.map(mapPodcastpod)
        })
        .catch(err => {
          clearInterval(this.checker)
          LNbits.utils.notifyApiError(err)
        })
    },
    closeFormDialogPodcast() {
      this.resetFormData()
    },
    closeFormDialogEpisode() {
      this.resetFormData()
    },
    openQrCodeDialog(podId) {
      var pod = _.findWhere(this.Podcastpods, {id: podId})
      if (pod.currency) this.updateFiatRate(pod.currency)

      this.qrCodeDialog.data = {
        id: pod.id,
        amount:
          (pod.min === pod.max ? pod.min : `${pod.min} - ${pod.max}`) +
          ' ' +
          (pod.currency || 'sat'),
        currency: pod.currency,
        comments: pod.comment_chars
          ? `${pod.comment_chars} characters`
          : 'no',
        webhook: pod.webhook_url || 'nowhere',
        success:
          pod.success_text || pod.success_url
            ? 'Display message "' +
              pod.success_text +
              '"' +
              (pod.success_url ? ' and URL "' + pod.success_url + '"' : '')
            : 'do nothing',
        lnurl: pod.lnurl,
        Podcast_url: pod.Podcast_url,
        print_url: pod.print_url
      }
      this.qrCodeDialog.show = true
    },
    openUpdateDialog(podId) {
      const pod = _.findWhere(this.Podcastpods, {id: podId})
      if (pod.currency) this.updateFiatRate(pod.currency)

      this.formDialog.data = _.clone(pod._data)
      this.formDialog.show = true
      this.formDialog.fixedAmount =
        this.formDialog.data.min === this.formDialog.data.max
    },
    sendFormData() {
      const wallet = _.findWhere(this.g.user.wallets, {
        id: this.formDialog.data.wallet
      })
      var data = _.omit(this.formDialog.data, 'wallet')

      if (this.formDialog.fixedAmount) data.max = data.min
      if (data.currency === 'satoshis') data.currency = null
      if (isNaN(parseInt(data.comment_chars))) data.comment_chars = 0

      if (data.id) {
        this.updatePodcastpod(wallet, data)
      } else {
        this.createPodcastpod(wallet, data)
      }
    },
    resetFormData() {
      this.formDialog = {
        show: false,
        fixedAmount: true,
        data: {}
      }
    },
    updatePodcast(wallet, data) {
      let values = _.omit(
        _.pick(
          data,
          'description',
          'min',
          'max',
          'webhook_url',
          'success_text',
          'success_url',
          'comment_chars',
          'currency'
        ),
        (value, key) =>
          (key === 'webhook_url' ||
            key === 'success_text' ||
            key === 'success_url') &&
          (value === null || value === '')
      )

      LNbits.api
        .request(
          'PUT',
          '/podcast/api/v1/pods/' + data.id,
          wallet.adminkey,
          values
        )
        .then(response => {
          this.Podcastpods = _.reject(this.Podcastpods, obj => obj.id === data.id)
          this.Podcastpods.push(mapPodcastpod(response.data))
          this.formDialog.show = false
          this.resetFormData()
        })
        .catch(err => {
          LNbits.utils.notifyApiError(err)
        })
    },
    createPodcast(wallet, data) {
      LNbits.api
        .request('POST', '/podcast/api/v1/pods', wallet.adminkey, data)
        .then(response => {
          this.getPodcastpods()
          this.formDialog.show = false
          this.resetFormData()
        })
        .catch(err => {
          LNbits.utils.notifyApiError(err)
        })
    },
    deletePodcast(podId) {
      var pod = _.findWhere(this.Podcastpods, {id: podId})

      LNbits.utils
        .confirmDialog('Are you sure you want to delete this Podcast pod?')
        .onOk(() => {
          LNbits.api
            .request(
              'DELETE',
              '/podcast/api/v1/pods/' + podId,
              _.findWhere(this.g.user.wallets, {id: pod.wallet}).adminkey
            )
            .then(response => {
              this.Podcastpods = _.reject(this.Podcastpods, obj => obj.id === podId)
            })
            .catch(err => {
              LNbits.utils.notifyApiError(err)
            })
        })
    },
    updateFiatRate(currency) {
      LNbits.api
        .request('GET', '/podcast/api/v1/rate/' + currency, null)
        .then(response => {
          let rates = _.clone(this.fiatRates)
          rates[currency] = response.data.rate
          this.fiatRates = rates
        })
        .catch(err => {
          LNbits.utils.notifyApiError(err)
        })
    },
    writeNfcTag: async function (lnurl) {
      try {
        if (typeof NDEFReader == 'undefined') {
          throw {
            toString: function () {
              return 'NFC not supported on this device or browser.'
            }
          }
        }

        const ndef = new NDEFReader()

        this.nfcTagWriting = true
        this.$q.notify({
          message: 'Tap your NFC tag to write the Podcast pod to it.'
        })

        await ndef.write({
          records: [{recordType: 'url', data: 'lightning:' + lnurl, lang: 'en'}]
        })

        this.nfcTagWriting = false
        this.$q.notify({
          type: 'positive',
          message: 'NFC tag written successfully.'
        })
      } catch (error) {
        this.nfcTagWriting = false
        this.$q.notify({
          type: 'negative',
          message: error
            ? error.toString()
            : 'An unexpected error has occurred.'
        })
      }
    }
  },
  created() {
    if (this.g.user.wallets.length) {
      var getPodcasts = this.getPodcasts
      getPodcasts()
      this.checker = setInterval(() => {
        getPodcasts()
      }, 20000)
    }
  }
})
