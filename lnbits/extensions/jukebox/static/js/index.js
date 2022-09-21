/* globals Quasar, Vue, _, VueQrcode, windowMixin, LNbits, LOCALE */

Vue.component(VueQrcode.name, VueQrcode)

var mapJukebox = obj => {
  if (obj.sp_device) {
    obj._data = _.clone(obj)

    obj.sp_id = obj._data.id
    obj.device = obj._data.sp_device.split('-')[0]
    playlists = obj._data.sp_playlists.split(',')
    var i
    playlistsar = []
    for (i = 0; i < playlists.length; i++) {
      playlistsar.push(playlists[i].split('-')[0])
    }
    obj.playlist = playlistsar.join()
    console.log(obj)
    return obj
  } else {
    return
  }
}

new Vue({
  el: '#vue',
  mixins: [windowMixin],
  data() {
    return {
      JukeboxTable: {
        columns: [
          {
            name: 'title',
            align: 'left',
            label: 'Title',
            field: 'title'
          },
          {
            name: 'device',
            align: 'left',
            label: 'Device',
            field: 'device'
          },
          {
            name: 'playlist',
            align: 'left',
            label: 'Playlist',
            field: 'playlist'
          },
          {
            name: 'price',
            align: 'left',
            label: 'Price',
            field: 'price'
          }
        ],
        pagination: {
          rowsPerPage: 10
        }
      },
      isPwd: true,
      tokenFetched: true,
      devices: [],
      filter: '',
      jukebox: {},
      playlists: [],
      JukeboxLinks: [],
      step: 1,
      locationcbPath: '',
      locationcb: '',
      jukeboxDialog: {
        show: false,
        data: {}
      },
      spotifyDialog: false,
      qrCodeDialog: {
        show: false,
        data: null
      }
    }
  },
  computed: {},
  methods: {
    openQrCodeDialog: function (linkId) {
      var link = _.findWhere(this.JukeboxLinks, {id: linkId})

      this.qrCodeDialog.data = _.clone(link)

      this.qrCodeDialog.data.url =
        window.location.protocol + '//' + window.location.host
      this.qrCodeDialog.show = true
    },
    getJukeboxes() {
      self = this

      LNbits.api
        .request(
          'GET',
          '/jukebox/api/v1/jukebox',
          self.g.user.wallets[0].adminkey
        )
        .then(function (response) {
          self.JukeboxLinks = response.data.map(function (obj) {
            return mapJukebox(obj)
          })
          console.log(self.JukeboxLinks)
        })
    },
    deleteJukebox(juke_id) {
      self = this
      LNbits.utils
        .confirmDialog('Are you sure you want to delete this Jukebox?')
        .onOk(function () {
          LNbits.api
            .request(
              'DELETE',
              '/jukebox/api/v1/jukebox/' + juke_id,
              self.g.user.wallets[0].adminkey
            )
            .then(function (response) {
              self.JukeboxLinks = _.reject(self.JukeboxLinks, function (obj) {
                return obj.id === juke_id
              })
            })

            .catch(err => {
              LNbits.utils.notifyApiError(err)
            })
        })
    },
    updateJukebox: function (linkId) {
      self = this
      var link = _.findWhere(self.JukeboxLinks, {id: linkId})
      self.jukeboxDialog.data = _.clone(link._data)

      self.refreshDevices()
      self.refreshPlaylists()

      self.step = 4
      self.jukeboxDialog.data.sp_device = []
      self.jukeboxDialog.data.sp_playlists = []
      self.jukeboxDialog.data.sp_id = self.jukeboxDialog.data.id
      self.jukeboxDialog.data.price = String(self.jukeboxDialog.data.price)
      self.jukeboxDialog.show = true
    },
    closeFormDialog() {
      this.jukeboxDialog.data = {}
      this.jukeboxDialog.show = false
      this.step = 1
    },
    submitSpotifyKeys() {
      self = this
      self.jukeboxDialog.data.user = self.g.user.id

      LNbits.api
        .request(
          'POST',
          '/jukebox/api/v1/jukebox/',
          self.g.user.wallets[0].adminkey,
          self.jukeboxDialog.data
        )
        .then(response => {
          if (response.data) {
            self.jukeboxDialog.data.sp_id = response.data.id
            self.step = 3
          }
        })
        .catch(err => {
          LNbits.utils.notifyApiError(err)
        })
    },
    authAccess() {
      self = this
      self.requestAuthorization()
      self.getSpotifyTokens()
      self.$q.notify({
        spinner: true,
        message: 'Processing',
        timeout: 10000
      })
    },
    getSpotifyTokens() {
      self = this
      var counter = 0
      var timerId = setInterval(function () {
        counter++
        if (!self.jukeboxDialog.data.sp_user) {
          clearInterval(timerId)
        }
        LNbits.api
          .request(
            'GET',
            '/jukebox/api/v1/jukebox/' + self.jukeboxDialog.data.sp_id,
            self.g.user.wallets[0].adminkey
          )
          .then(response => {
            if (response.data.sp_access_token) {
              self.fetchAccessToken(response.data.sp_access_token)
              if (self.jukeboxDialog.data.sp_access_token) {
                self.refreshPlaylists()
                self.refreshDevices()
                setTimeout(function () {
                  if (self.devices.length < 1 || self.playlists.length < 1) {
                    self.$q.notify({
                      spinner: true,
                      color: 'red',
                      message:
                        'Error! Make sure Spotify is open on the device you wish to use, has playlists, and is playing something',
                      timeout: 10000
                    })
                    LNbits.api
                      .request(
                        'DELETE',
                        '/jukebox/api/v1/jukebox/' + response.data.id,
                        self.g.user.wallets[0].adminkey
                      )
                      .then(function (response) {
                        self.getJukeboxes()
                      })
                      .catch(err => {
                        LNbits.utils.notifyApiError(err)
                      })
                    clearInterval(timerId)
                    self.closeFormDialog()
                  } else {
                    self.step = 4
                    clearInterval(timerId)
                  }
                }, 2000)
              }
            }
          })
          .catch(err => {
            LNbits.utils.notifyApiError(err)
          })
      }, 3000)
    },
    requestAuthorization() {
      self = this
      var url = 'https://accounts.spotify.com/authorize'
      url += '?client_id=' + self.jukeboxDialog.data.sp_user
      url += '&response_type=code'
      url +=
        '&redirect_uri=' +
        encodeURI(self.locationcbPath + self.jukeboxDialog.data.sp_id)
      url += '&show_dialog=true'
      url +=
        '&scope=user-read-private user-read-email user-modify-playback-state user-read-playback-position user-library-read streaming user-read-playback-state user-read-recently-played playlist-read-private'

      window.open(url)
    },
    openNewDialog() {
      this.jukeboxDialog.show = true
      this.jukeboxDialog.data = {}
    },
    createJukebox() {
      self = this
      self.jukeboxDialog.data.sp_playlists = self.jukeboxDialog.data.sp_playlists.join()
      self.updateDB()
      self.jukeboxDialog.show = false
      self.getJukeboxes()
    },
    updateDB() {
      self = this
      LNbits.api
        .request(
          'PUT',
          '/jukebox/api/v1/jukebox/' + self.jukeboxDialog.data.sp_id,
          self.g.user.wallets[0].adminkey,
          self.jukeboxDialog.data
        )
        .then(function (response) {
          if (
            self.jukeboxDialog.data.sp_playlists &&
            self.jukeboxDialog.data.sp_devices
          ) {
            self.getJukeboxes()
            // self.JukeboxLinks.push(mapJukebox(response.data))
          }
        })
    },
    playlistApi(method, url, body) {
      self = this
      let xhr = new XMLHttpRequest()
      xhr.open(method, url, true)
      xhr.setRequestHeader('Content-Type', 'application/json')
      xhr.setRequestHeader(
        'Authorization',
        'Bearer ' + this.jukeboxDialog.data.sp_access_token
      )
      xhr.send(body)
      xhr.onload = function () {
        if (xhr.status == 401) {
          self.refreshAccessToken()
          self.playlistApi(
            'GET',
            'https://api.spotify.com/v1/me/playlists',
            null
          )
        }
        let responseObj = JSON.parse(xhr.response)
        self.jukeboxDialog.data.playlists = null
        self.playlists = []
        self.jukeboxDialog.data.playlists = []
        var i
        for (i = 0; i < responseObj.items.length; i++) {
          self.playlists.push(
            responseObj.items[i].name + '-' + responseObj.items[i].id
          )
        }
      }
    },
    refreshPlaylists() {
      self = this
      self.playlistApi('GET', 'https://api.spotify.com/v1/me/playlists', null)
    },
    deviceApi(method, url, body) {
      self = this
      let xhr = new XMLHttpRequest()
      xhr.open(method, url, true)
      xhr.setRequestHeader('Content-Type', 'application/json')
      xhr.setRequestHeader(
        'Authorization',
        'Bearer ' + this.jukeboxDialog.data.sp_access_token
      )
      xhr.send(body)
      xhr.onload = function () {
        if (xhr.status == 401) {
          self.refreshAccessToken()
          self.deviceApi(
            'GET',
            'https://api.spotify.com/v1/me/player/devices',
            null
          )
        }
        let responseObj = JSON.parse(xhr.response)
        self.jukeboxDialog.data.devices = []

        self.devices = []
        var i
        for (i = 0; i < responseObj.devices.length; i++) {
          self.devices.push(
            responseObj.devices[i].name + '-' + responseObj.devices[i].id
          )
        }
      }
    },
    refreshDevices() {
      self = this
      self.deviceApi(
        'GET',
        'https://api.spotify.com/v1/me/player/devices',
        null
      )
    },
    fetchAccessToken(code) {
      self = this
      let body = 'grant_type=authorization_code'
      body += '&code=' + code
      body +=
        '&redirect_uri=' +
        encodeURI(self.locationcbPath + self.jukeboxDialog.data.sp_id)

      self.callAuthorizationApi(body)
    },
    refreshAccessToken() {
      self = this
      let body = 'grant_type=refresh_token'
      body += '&refresh_token=' + self.jukeboxDialog.data.sp_refresh_token
      body += '&client_id=' + self.jukeboxDialog.data.sp_user
      self.callAuthorizationApi(body)
    },
    callAuthorizationApi(body) {
      self = this
      let xhr = new XMLHttpRequest()
      xhr.open('POST', 'https://accounts.spotify.com/api/token', true)
      xhr.setRequestHeader('Content-Type', 'application/x-www-form-urlencoded')
      xhr.setRequestHeader(
        'Authorization',
        'Basic ' +
          btoa(
            self.jukeboxDialog.data.sp_user +
              ':' +
              self.jukeboxDialog.data.sp_secret
          )
      )
      xhr.send(body)
      xhr.onload = function () {
        let responseObj = JSON.parse(xhr.response)
        if (responseObj.access_token) {
          self.jukeboxDialog.data.sp_access_token = responseObj.access_token
          self.jukeboxDialog.data.sp_refresh_token = responseObj.refresh_token
          self.updateDB()
        }
      }
    }
  },
  created() {
    var getJukeboxes = this.getJukeboxes
    getJukeboxes()
    this.selectedWallet = this.g.user.wallets[0]
    this.locationcbPath = String(
      [
        window.location.protocol,
        '//',
        window.location.host,
        '/jukebox/api/v1/jukebox/spotify/cb/'
      ].join('')
    )
    this.locationcb = this.locationcbPath
  }
})
