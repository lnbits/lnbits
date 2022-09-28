new Vue({
  el: '#vue',
  data: function () {
    return {
      searchTerm: '',
      filteredExtensions: null,
      registryExtensions: null,
      allExtensions: null,
      showInstalled: true,
      showAvailable: true,
      installingExtension: false,
      installingExtensionName: null
    }
  },
  async mounted() {
    var res = await fetch('http://127.0.0.1:8000/ext/list?skip=0&limit=100')
    if (res.ok) {
      this.registryExtensions = await res.json()
      this.allExtensions = this.g.extensions.concat(
        this.registryExtensions.map(e => {
          isInstalled = false
          if (this.g.extensions.find(e2 => e2.name == e.name)) {
            isInstalled = true
          }

          return {
            code: e.id,
            isValid: true,
            isAdminOnly: false,
            name: e.name,
            shortDescription: e.description_short,
            icon: 'money',
            contributors: ['chill117'],
            hidden: false,
            url: '/bleskomat/',
            isEnabled: false,
            isInstalled: isInstalled,
            latestVersion:
              e.versions[e.versions.length - 1].semver.split('_')[1],
            requiresRestart: false
          }
        })
      )

      // remove duplicates
      this.filteredExtensions = [
        ...new Map(this.allExtensions.map(m => [m.name, m])).values()
      ]
    } else {
      alert('HTTP-Error: ' + res.status)
    }
  },
  watch: {
    searchTerm(term) {
      // Reset the filter
      this.filteredExtensions = this.allExtensions
      if (term !== '') {
        // Filter the extensions list
        function extensionNameContains(searchTerm) {
          return function (extension) {
            return (
              extension.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
              extension.shortDescription
                .toLowerCase()
                .includes(searchTerm.toLowerCase())
            )
          }
        }

        this.filteredExtensions = this.filteredExtensions.filter(
          extensionNameContains(term)
        )
      }
    }
  },
  mixins: [windowMixin],
  methods: {
    async installExtension(extension, user_id) {
      this.installingExtension = true
      this.installingExtensionCode = extension.code

      // await new Promise(resolve => setTimeout(resolve, 2000))

      const url = `http://localhost:5000/api/v1/extensions/install/${extension.code}?usr=${user_id}`
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          Accept: 'application/json',
          'Content-Type': 'application/json'
        }
      })

      const data = await response.json()
      if (data['success']) {
        this.filteredExtensions.find(
          e => e.code == extension.code
        ).requiresRestart = true
      }

      this.installingExtension = false
      this.installingExtensionCode = null
    }
  }
})
