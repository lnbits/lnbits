/* globals Quasar, Vue, _, VueQrcode, windowMixin, LNbits, LOCALE */

Vue.component(VueQrcode.name, VueQrcode)

const pica = window.pica()

var locationPath = [
  window.location.protocol,
  '//',
  window.location.host,
  window.location.pathname
].join('')

var mapPodcast = obj => {
  obj._data = _.clone(obj)
  obj.date = Quasar.utils.date.formatDate(
    new Date(obj.time * 1000),
    'YYYY-MM-DD HH:mm'
  )
  obj.amount = new Intl.NumberFormat(LOCALE).format(obj.amount)
  obj.pod_page = [locationPath, 'player/', obj.id].join('')
  obj.rss_feed = [locationPath, 'rss/', obj.id].join('')
  return obj
}

new Vue({
  el: '#vue',
  mixins: [windowMixin],
  data() {
    return {
      categoryOptions: [
        "Arts",
        "Books",
        "Design",
      "Fashion & Beauty",
      "Food",
      "Performing Arts",
      "Visual Arts",
      "Business",
      "Careers",
      "Entrepreneurship",
      "Investing",
      "Management",
      "Marketing",
      "Non-Profit",
      "Comedy",
      "Comedy Interviews",
      "Improv",
      "Stand-Up",
      "Education",
      "Courses",
      "How To",
      "Language Learning",
      "Self-Improvement",
      "Fiction",
      "Comedy Fiction",
      "Drama",
      "Science Fiction",
      "Government",
      "History",
      "Health & Fitness",
      "Alternative Health",
      "Fitness",
      "Medicine",
      "Mental Health",
      "Nutrition",
      "Sexuality",
      "Kids & Family",
      "Education for Kids",
      "Parenting",
      "Pets & Animals",
      "Stories for Kids",
      "Leisure",
      "Animation & Manga",
      "Automotive",
      "Aviation",
      "Crafts",
      "Games",
      "Hobbies",
      "Home & Garden",
      "Video Games",
      "Music",
      "Music Commentary",
      "Music History",
      "Music Interviews",
      "News",
      "Business News",
      "Daily News",
      "Entertainment News",
      "News Commentary",
      "Politics",
      "Sports News",
      "Tech News",
      "Religion & Spirituality",
      "Buddhism",
      "Christianity",
      "Hinduism",
      "Islam",
      "Judaism",
      "Religion",
      "Spirituality",
      "Science",
      "Astronomy",
      "Chemistry",
      "Earth Sciences",
      "Life Sciences",
      "Mathematics",
      "Natural Sciences",
      "Nature",
      "Physics",
      "Social Sciences",
      "Society & Culture",
      "Documentary",
      "Personal Journals",
      "Philosophy",
      "Places & Travel",
      "Relationships",
      "Sports",
      "Baseball",
      "Basketball",
      "Cricket",
      "Fantasy Sports",
      "Football",
      "Golf",
      "Hockey",
      "Rugby",
      "Running",
      "Soccer",
      "Swimming",
      "Tennis",
      "Volleyball",
      "Wilderness",
      "Wrestling",
      "Technology",
      "True Crime",
      "TV & Film",
      "After Shows",
      "Film History",
      "Film Interviews",
      "Film Reviews",
      "TV Reviews"],
      countryOptions: ["Afghanistan",
      "Albania",
      "Algeria",
      "Andorra",
      "Angola",
      "Antigua & Deps",
      "Argentina",
      "Armenia",
      "Australia",
      "Austria",
      "Azerbaijan",
      "Bahamas",
      "Bahrain",
      "Bangladesh",
      "Barbados",
      "Belarus",
      "Belgium",
      "Belize",
      "Benin",
      "Bhutan",
      "Bolivia",
      "Bosnia Herzegovina",
      "Botswana",
      "Brazil",
      "Brunei",
      "Bulgaria",
      "Burkina",
      "Burundi",
      "Cambodia",
      "Cameroon",
      "Canada",
      "Cape Verde",
      "Central African Rep",
      "Chad",
      "Chile",
      "China",
      "Colombia",
      "Comoros",
      "Congo",
      "Congo {Democratic Rep}",
      "Costa Rica",
      "Croatia",
      "Cuba",
      "Cyprus",
      "Czech Republic",
      "Denmark",
      "Djibouti",
      "Dominica",
      "Dominican Republic",
      "East Timor",
      "Ecuador",
      "Egypt",
      "El Salvador",
      "Equatorial Guinea",
      "Eritrea",
      "Estonia",
      "Ethiopia",
      "Fiji",
      "Finland",
      "France",
      "Gabon",
      "Gambia",
      "Georgia",
      "Germany",
      "Ghana",
      "Greece",
      "Grenada",
      "Guatemala",
      "Guinea",
      "Guinea-Bissau",
      "Guyana",
      "Haiti",
      "Honduras",
      "Hungary",
      "Iceland",
      "India",
      "Indonesia",
      "Iran",
      "Iraq",
      "Ireland {Republic}",
      "Israel",
      "Italy",
      "Ivory Coast",
      "Jamaica",
      "Japan",
      "Jordan",
      "Kazakhstan",
      "Kenya",
      "Kiribati",
      "Korea North",
      "Korea South",
      "Kosovo",
      "Kuwait",
      "Kyrgyzstan",
      "Laos",
      "Latvia",
      "Lebanon",
      "Lesotho",
      "Liberia",
      "Libya",
      "Liechtenstein",
      "Lithuania",
      "Luxembourg",
      "Macedonia",
      "Madagascar",
      "Malawi",
      "Malaysia",
      "Maldives",
      "Mali",
      "Malta",
      "Marshall Islands",
      "Mauritania",
      "Mauritius",
      "Mexico",
      "Micronesia",
      "Moldova",
      "Monaco",
      "Mongolia",
      "Montenegro",
      "Morocco",
      "Mozambique",
      "Myanmar, {Burma}",
      "Namibia",
      "Nauru",
      "Nepal",
      "Netherlands",
      "New Zealand",
      "Nicaragua",
      "Niger",
      "Nigeria",
      "Norway",
      "Oman",
      "Pakistan",
      "Palau",
      "Panama",
      "Papua New Guinea",
      "Paraguay",
      "Peru",
      "Philippines",
      "Poland",
      "Portugal",
      "Qatar",
      "Romania",
      "Russian Federation",
      "Rwanda",
      "St Kitts & Nevis",
      "St Lucia",
      "Saint Vincent & the Grenadines",
      "Samoa",
      "San Marino",
      "Sao Tome & Principe",
      "Saudi Arabia",
      "Senegal",
      "Serbia",
      "Seychelles",
      "Sierra Leone",
      "Singapore",
      "Slovakia",
      "Slovenia",
      "Solomon Islands",
      "Somalia",
      "South Africa",
      "South Sudan",
      "Spain",
      "Sri Lanka",
      "Sudan",
      "Suriname",
      "Swaziland",
      "Sweden",
      "Switzerland",
      "Syria",
      "Taiwan",
      "Tajikistan",
      "Tanzania",
      "Thailand",
      "Togo",
      "Tonga",
      "Trinidad & Tobago",
      "Tunisia",
      "Turkey",
      "Turkmenistan",
      "Tuvalu",
      "Uganda",
      "Ukraine",
      "United Arab Emirates",
      "United Kingdom",
      "United States",
      "Uruguay",
      "Uzbekistan",
      "Vanuatu",
      "Vatican City",
      "Venezuela",
      "Vietnam",
      "Yemen",
      "Zambia",
      "Zimbabwe"],
      languageOptions: ["Afrikaans",
      "Arabic",
      "Bengali",
      "Bulgarian",
      "Catalan",
      "Cantonese",
      "Croatian",
      "Czech",
      "Danish",
      "Dutch",
      "Lithuanian",
      "Malay",
      "Malayalam",
      "Panjabi",
      "Tamil",
      "English",
      "Finnish",
      "French",
      "German",
      "Greek",
      "Hebrew",
      "Hindi",
      "Hungarian",
      "Indonesian",
      "Italian",
      "Japanese",
      "Javanese",
      "Korean",
      "Norwegian",
      "Polish",
      "Portuguese",
      "Romanian",
      "Russian",
      "Serbian",
      "Slovak",
      "Slovene",
      "Spanish",
      "Swedish",
      "Telugu",
      "Thai",
      "Turkish",
      "Ukrainian",
      "Vietnamese",
      "Welsh",
      "Sign language",
      "Algerian",
      "Aramaic",
      "Armenian",
      "Berber",
      "Burmese",
      "Bosnian",
      "Brazilian",
      "Bulgarian",
      "Cypriot",
      "Corsica",
      "Creole",
      "Scottish",
      "Egyptian",
      "Esperanto",
      "Estonian",
      "Finn",
      "Flemish",
      "Georgian",
      "Hawaiian",
      "Indonesian",
      "Inuit",
      "Irish",
      "Icelandic",
      "Latin",
      "Mandarin",
      "Nepalese",
      "Sanskrit",
      "Tagalog",
      "Tahitian",
      "Tibetan",
      "Gypsy",
      "Wu"],
      podcastOptions: [],
      typeOptions: [{label:'Episodic (to be played in any order)', value:'Episodic'}, {label:'Serial (to be played in sequence)', value:'Serial'}],
      currencies: [],
      fiatRates: {},
      checker: null,
      Podcasts: [],
      Episodes: [],
      PodcastsTable: {
        pagination: {
          rowsPerPage: 10
        }
      },
      EpisodesTable: {
        pagination: {
          rowsPerPage: 10
        }
      },
      nfcTagWriting: false,
      formDialogPodcast: {
        show: false,
        fixedAmount: true,
        data: {explicit: false,
              copyright: "@2022"}
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
    imageAddedPodcast(file) {
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
        this.formDialogPodcast.data.cover_image = canvas.toDataURL()
        this.formDialogPodcast = {...this.formDialogPodcast}
      }
    },
    imageClearedPodcast() {
      this.formDialogPodcast.data.cover_image = null
      this.formDialogPodcast = {...this.formDialogPodcast}
    },
    imageAddedEpisode(file) {
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
        this.formDialogEpisode.data.episode_image = canvas.toDataURL()
        this.formDialogEpisode = {...this.formDialogEpisode}
      }
    },
    imageClearedEpisode() {
      this.formDialogEpisode.data.episode_image = null
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
          this.Podcasts = response.data.map(mapPodcast)
          this.podcastOptions = []
          for (let i = 0; i < this.Podcasts.length; i++) {
            this.podcastOptions.push(
            {
              label: [this.Podcasts[i].podcast_title, " - ", this.Podcasts[i].id].join(""),
              value: this.Podcasts[i].id
            })
          }
        })
        .catch(err => {
          clearInterval(this.checker)
          LNbits.utils.notifyApiError(err)
        })
    },
    closeFormDialogPodcast() {
      this.resetFormDataPodcast()
    },
    closeFormDialogEpisode() {
      this.resetFormDataEpisode()
    },
    openUpdateDialogPodcast(podId) {
      const pod = _.findWhere(this.Podcasts, {id: podId})
      if (pod.currency) this.updateFiatRate(pod.currency)

      this.formDialogPodcast.data = _.clone(pod._data)
      this.formDialogPodcast.show = true
    },
    openUpdateDialogEpisode(epsId) {
      const eps = _.findWhere(this.Episodes, {id: epsId})

      this.formDialogEpisode.data = _.clone(eps._data)
      this.formDialogEpisode.show = true
    },
    sendFormDataPodcast() {
      console.log(this.formDialogPodcast.data)

      const wallet = _.findWhere(this.g.user.wallets, {
        id: this.formDialogPodcast.data.wallet
      })
      
      if (this.formDialogPodcast.data.id) {
        this.updatePodcast(wallet, this.formDialogPodcast.data)
      } else {
        this.formDialogPodcast.data.categories = this.formDialogPodcast.data.categories.join()
        this.createPodcast(wallet, this.formDialogPodcast.data)
      }
    },
    resetFormDataPodcast() {
      this.formDialogPodcast = {
        show: false,
        fixedAmount: true,
        data: {}
      }
    },
    sendFormDataEpisode() {
      const wallet = _.findWhere(this.g.user.wallets, {
        id: this.formDialogEpisode.data.wallet
      })
      if(!this.formDialogEpisode.data.episode_image){
        var pod = _.findWhere(this.Podcasts, {id: this.formDialogEpisode.data.podcast})
        this.formDialogEpisode.data.episode_image = pod.cover_image
      }
      
      if (this.formDialogEpisode.data.id) {
        this.updateEpisode(this.g.user.wallets[0], this.formDialogEpisode.data)
      } else {
        this.formDialogEpisode.data.keywords = this.formDialogEpisode.data.keywords.join()
        this.createEpisode(this.g.user.wallets[0], this.formDialogEpisode.data)
      }
    },
    resetFormDataEpisode() {
      this.formDialogEpisode = {
        show: false,
        fixedAmount: true,
        data: {}
      }
    },
    updatePodcast(wallet, data) {

      LNbits.api
        .request(
          'POST',
          '/podcast/api/v1/pods/' + data.id,
          wallet.adminkey,
          data
        )
        .then(response => {
          this.getPodcasts()
          this.formDialogPodcast.show = false
          this.resetFormDataPodcast()
        })
        .catch(err => {
          LNbits.utils.notifyApiError(err)
        })
    },
    createPodcast(wallet, data) {
      LNbits.api
        .request('POST', '/podcast/api/v1/pods', wallet.adminkey, data)
        .then(response => {
          this.getPodcasts()
          this.formDialogPodcast.show = false
          this.resetFormDataPodcast()
        })
        .catch(err => {
          LNbits.utils.notifyApiError(err)
        })
    },
    deletePodcast(podId) {
      var pod = _.findWhere(this.Podcasts, {id: podId})

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
              this.Podcasts = _.reject(this.Podcasts, obj => obj.id === podId)
            })
            .catch(err => {
              LNbits.utils.notifyApiError(err)
            })
        })
    },
    updateEpisode(wallet, data) {
      LNbits.api
        .request(
          'POST',
          '/podcast/api/v1/eps/' + data.id,
          wallet.adminkey,
          data
        )
        .then(response => {
          this.getEpisodes()
          this.formDialogEpisode.show = false
          this.resetFormDataEpisode()
        })
        .catch(err => {
          LNbits.utils.notifyApiError(err)
        })
    },
    createEpisode(wallet, data) {
      podcast = data.media_file
      _.omit(data, 'media_file')
      LNbits.api
        .request('POST', '/podcast/api/v1/eps', wallet.adminkey, data)
        .then(response => {
          LNbits.api
            .request('POST', '/podcast/api/v1/files/', {"file": podcast, "episodename": response.id})
            .then(response => {
              this.getEpisodes()
              this.formDialogEpisode.show = false
              this.resetFormDataEpisode()
          })
          .catch(err => {
            this.deleteEpisode(response.id)
            LNbits.utils.notifyApiError(err)
          })
        })
        .catch(err => {
          LNbits.utils.notifyApiError(err)
        })
    },
    deleteEpisode(podId) {
      var pod = _.findWhere(this.Podcasts, {id: podId})

      LNbits.utils
        .confirmDialog('Are you sure you want to delete this Podcast pod?')
        .onOk(() => {
          LNbits.api
            .request(
              'DELETE',
              '/podcast/api/v1/eps/' + podId,
              _.findWhere(this.g.user.wallets, {id: pod.wallet}).adminkey
            )
            .then(response => {
              this.Podcasts = _.reject(this.Podcasts, obj => obj.id === podId)
            })
            .catch(err => {
              LNbits.utils.notifyApiError(err)
            })
        })
    },
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
