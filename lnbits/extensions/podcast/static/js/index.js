/* globals Quasar, Vue, _, VueQrcode, windowMixin, LNbits, LOCALE */

Vue.component(VueQrcode.name, VueQrcode)

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
  obj.print_url = [locationPath, 'print/', obj.id].join('')
  obj.Podcast_url = [locationPath, obj.id].join('')
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
      podcastOptions: ['seconds', 'minutes', 'hours'],
      typeOptions: ['seconds', 'minutes', 'hours'],
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
          this.Podcasts = response.data.map(mapPodcast)
          for (let i = 0; i < this.Podcasts.length; i++) {
            this.podcastOptions.push(
            {
              label: this.Podcasts[i].title,
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
    openQrCodeDialog(podId) {
      var pod = _.findWhere(this.Podcasts, {id: podId})
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
      const pod = _.findWhere(this.Podcasts, {id: podId})
      if (pod.currency) this.updateFiatRate(pod.currency)

      this.formDialog.data = _.clone(pod._data)
      this.formDialog.show = true
      this.formDialog.fixedAmount =
        this.formDialog.data.min === this.formDialog.data.max
    },
    sendFormDataPodcast() {
      console.log(this.formDialogPodcast.data)

      const wallet = _.findWhere(this.g.user.wallets, {
        id: this.formDialogPodcast.data.wallet
      })

      if (this.formDialogPodcast.data.id) {
        this.updatePodcast(wallet, this.formDialogPodcast.data)
      } else {
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

      if (this.formDialogEpisode.data.id) {
        this.updateEpisode(this.g.user.wallets[0], this.formDialogEpisode.data)
      } else {
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
          this.Podcasts = _.reject(this.Podcasts, obj => obj.id === data.id)
          this.Podcasts.push(mapPodcast(response.data))
          this.formDialog.show = false
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
          this.Podcasts = _.reject(this.Podcasts, obj => obj.id === data.id)
          this.Podcasts.push(mapPodcast(response.data))
          this.formDialog.show = false
          this.resetFormDataEpisode()
        })
        .catch(err => {
          LNbits.utils.notifyApiError(err)
        })
    },
    createEpisode(wallet, data) {
      LNbits.api
        .request('POST', '/podcast/api/v1/pods', wallet.adminkey, data)
        .then(response => {
          this.getEpisodes()
          this.formDialogEpisode.show = false
          this.resetFormDataEpisode()
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
