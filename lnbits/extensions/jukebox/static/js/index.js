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
      device: [],
      jukebox: {},
      playlists: [],
      step: 1,
      locationcbPath: "",
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
            if(!self.jukeboxDialog.data.sp_user){
              clearInterval(timerId);
            }
            LNbits.api
            .request('GET', '/jukebox/api/v1/jukebox/spotify/' + self.jukeboxDialog.data.sp_user, self.g.user.wallets[0].inkey)
            .then(response => {
             if(response.data.sp_token){
               console.log(response.data.sp_token)

               self.step = 3
               clearInterval(timerId);
               self.refreshPlaylists()
               self.$q.notify({
                message: 'Success! App is now linked!',
                timeout: 3000
              })
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
      let url = 'https://accounts.spotify.com/authorize'
      url += '?scope=user-modify-playback-state%20user-read-playback-position'
      url += '%20user-library-read%20streaming%20user-read-playback-state'
      url += '%20user-read-recently-played%20playlist-read-private&response_type=code'
      url += '&redirect_uri=' +  encodeURIComponent(self.locationcbPath) + self.jukeboxDialog.data.sp_user
      url += '&client_id=' + self.jukeboxDialog.data.sp_user 
      url += '&show_dialog=true'
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

    callApi(method, url, body, callback){
      let xhr = new XMLHttpRequest()
      xhr.open(method, url, true)
      xhr.setRequestHeader('Content-Type', 'application/json')
      xhr.setRequestHeader('Authorization', 'Bearer ' + self.jukeboxDialog.data.sp_token)
      xhr.send(body)
      xhr.onload = callback
    },
    refreshPlaylists(){
      console.log("sdfvasdv")
      callApi( "GET", "https://api.spotify.com/v1/me/playlists", null, handlePlaylistsResponse )
    },
    handlePlaylistsResponse(){
      console.log("data")
      if ( this.status == 200 ){
        var data = JSON.parse(this.responseText)
        console.log(data)
      }
      else if ( this.status == 401 ){
        refreshAccessToken()
      }
      else {
        console.log(this.responseText)
        alert(this.responseText)
      }
    },
    refreshAccessToken(){
      refresh_token = localStorage.getItem("refresh_token")
      let body = "grant_type=refresh_token"
      body += "&refresh_token=" + self.jukeboxDialog.data.sp_token
      body += "&client_id=" + self.jukeboxDialog.data.sp_user
      callAuthorizationApi(body)
    },
    callAuthorizationApi(body){
      let xhr = new XMLHttpRequest()
      xhr.open("POST", TOKEN, true)
      xhr.setRequestHeader('Content-Type', 'application/x-www-form-urlencoded')
      xhr.setRequestHeader('Authorization', 'Basic ' + btoa(self.jukeboxDialog.data.sp_user + ":" + self.jukeboxDialog.data.sp_secret))
      xhr.send(body)
      xhr.onload = handleAuthorizationResponse
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
  }
})
