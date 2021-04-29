/* globals Quasar, Vue, _, VueQrcode, windowMixin, LNbits, LOCALE */

Vue.component(VueQrcode.name, VueQrcode)

const pica = window.pica()



new Vue({
  el: '#vue',
  mixins: [windowMixin],
  data() {
    return {
      isPwd: true,
      tokenFetched: true,
      devices: [],
      jukebox: {},
      playlists: [],
      step: 1,
      locationcbPath: "",
      locationcb: "",
      jukeboxDialog: {
        show: false,
        data: {}
      },
      spotifyDialog: false
    }
  },
  computed: {
    printItems() {
      return this.jukebox.items.filter(({enabled}) => enabled)
    }
  },
  methods: {
    closeFormDialog() {
      this.jukeboxDialog.data = {}
      this.jukeboxDialog.show = false
      this.step = 1
    },
    submitSpotify() {

      self = this
      console.log(self.jukeboxDialog.data)
      self.requestAuthorization()
        this.$q.notify({
          spinner: true,
          message: 'Fetching token',
          timeout: 4000
        })
        LNbits.api.request(
          'POST',
          '/jukebox/api/v1/jukebox/',
          self.g.user.wallets[0].adminkey,
          self.jukeboxDialog.data
        )
        .then(response => {
         if(response.data){
          var timerId = setInterval(function(){ 
            console.log(response.data)
            if(!self.jukeboxDialog.data.sp_user){
              clearInterval(timerId);
            }
            self.jukeboxDialog.data.sp_id = response.data.id
            LNbits.api
            .request('GET', '/jukebox/api/v1/jukebox/spotify/' + self.jukeboxDialog.data.sp_id, self.g.user.wallets[0].inkey)
            .then(response => {
             if(response.data.sp_access_token){
               self.jukeboxDialog.data.sp_access_token = response.data.sp_access_token
               self.step = 3
               self.fetchAccessToken()
               
               clearInterval(timerId)
               
              // self.refreshPlaylists(response.data.sp_token)
//               self.$q.notify({
//                message: 'Success! App is now linked!',
//                timeout: 3000
//              })
               //set devices, playlists
             }
            })
            .catch(err => {
             LNbits.utils.notifyApiError(err)
            })
           }, 3000)
         }
        })
        .catch(err => {
         LNbits.utils.notifyApiError(err)
        })
    },
    requestAuthorization(){
      self = this
      var url = 'https://accounts.spotify.com/authorize'
      url += '?client_id=' + self.jukeboxDialog.data.sp_user
      url += '&response_type=code'
      url += '&redirect_uri=' +  encodeURI(self.locationcbPath) + self.jukeboxDialog.data.sp_user
      url += "&show_dialog=true"
      url += '&scope=user-read-private user-read-email user-modify-playback-state user-read-playback-position user-library-read streaming user-read-playback-state user-read-recently-played playlist-read-private'
      console.log(url)
      window.open(url)
    },
    openNewDialog() {
      this.jukeboxDialog.show = true
      this.jukeboxDialog.data = {}
    },
    openUpdateDialog(itemId) {
      this.jukeboxDialog.show = true
      let item = this.jukebox.items.find(item => item.id === itemId)
      this.jukeboxDialog.data = item
    },
    createJukebox(){
      self = this

        LNbits.api.request(
          'PUT',
          '/jukebox/api/v1/jukebox/' + this.jukeboxDialog.data.sp_id,
          self.g.user.wallets[0].adminkey,
          self.jukeboxDialog.data
        )
        .then(response => {
          console.log(response.data)
          
        })
        .catch(err => {
         LNbits.utils.notifyApiError(err)
        })
    },

    playlistApi(method, url, body){
      self = this
      let xhr = new XMLHttpRequest()
      xhr.open(method, url, true)
      xhr.setRequestHeader('Content-Type', 'application/json')
      xhr.setRequestHeader('Authorization', 'Bearer ' + this.jukeboxDialog.data.sp_access_token)
      xhr.send(body)
      xhr.onload = function() {
        let responseObj = JSON.parse(xhr.response)
        self.playlists = []
        var i;
        for (i = 0; i < responseObj.items.length; i++) {
          self.playlists.push(responseObj.items[i].name + "-" + responseObj.items[i].id)
        }
      }
    },
    refreshPlaylists(){
      self = this
      self.playlistApi( "GET", "https://api.spotify.com/v1/me/playlists", null)
    },
    deviceApi(method, url, body){
      self = this
      let xhr = new XMLHttpRequest()
      xhr.open(method, url, true)
      xhr.setRequestHeader('Content-Type', 'application/json')
      xhr.setRequestHeader('Authorization', 'Bearer ' + this.jukeboxDialog.data.sp_access_token)
      xhr.send(body)
      xhr.onload = function() {
        let responseObj = JSON.parse(xhr.response)
        console.log(responseObj.devices[0])
        self.devices = []
        var i;
        for (i = 0; i < responseObj.devices.length; i++) {
          self.devices.push(responseObj.devices[i].name + "-" + responseObj.devices[i].id)
          console.log(responseObj.devices[i].name)
        }
        
      }
    },
    refreshDevices(){
      self = this
      self.deviceApi( "GET", "https://api.spotify.com/v1/me/player/devices", null)
    },
    fetchAccessToken( ){
      self = this
      let body = "grant_type=authorization_code"
      body += "&code=" + self.jukeboxDialog.data.sp_access_token
      body += '&redirect_uri=' +  encodeURI(self.locationcbPath) + self.jukeboxDialog.data.sp_user
      this.callAuthorizationApi(body)
    },
    refreshAccessToken(){
      self = this
      let body = "grant_type=refresh_token"
      body += "&refresh_token=" + self.jukeboxDialog.data.sp_refresh_token
      body += "&client_id=" + self.jukeboxDialog.data.sp_user
      this.callAuthorizationApi(body)
    },
    callAuthorizationApi(body){
      self = this
      let xhr = new XMLHttpRequest()
      xhr.open("POST", "https://accounts.spotify.com/api/token", true)
      xhr.setRequestHeader('Content-Type', 'application/x-www-form-urlencoded')
      xhr.setRequestHeader('Authorization', 'Basic ' + btoa(this.jukeboxDialog.data.sp_user + ":" + this.jukeboxDialog.data.sp_secret))
      xhr.send(body)
      console.log(('Authorization', 'Basic ' + btoa(this.jukeboxDialog.data.sp_user + ":" + this.jukeboxDialog.data.sp_secret)))
      xhr.onload = function() {
        let responseObj = JSON.parse(xhr.response)
        alert(responseObj.access_token)
        alert(responseObj.refresh_token)
        self.jukeboxDialog.data.sp_access_token = responseObj.access_token
        self.jukeboxDialog.data.sp_refresh_token = responseObj.refresh_token
        console.log(self.jukeboxDialog.data)
        self.refreshPlaylists()
        self.refreshDevices()
      }
    },
  },
  created() {
    this.selectedWallet = this.g.user.wallets[0]
    this.locationcbPath = String([
      window.location.protocol,
      '//',
      window.location.host,
      '/jukebox/api/v1/jukebox/spotify/cb/'
    ].join(''))
    console.log(this.locationcbPath)
    this.locationcb = this.locationcbPath
  }
})
