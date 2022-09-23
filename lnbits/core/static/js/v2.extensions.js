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
    }
  },
  async mounted() {
    
    var res = await fetch('http://127.0.0.1:8000/ext/list?skip=0&limit=100');
    if (res.ok) {  
      this.registryExtensions = await res.json();

      this.allExtensions = this.g.extensions.concat(
        this.registryExtensions.map(e => {
            return {
              "code": e.id,
              "isValid": true,
              "isAdminOnly": false,
              "name": e.name,
              "shortDescription": e.description_short,
              "icon": "money",
              "contributors": [ "chill117" ],
              "hidden": false,
              "url": "/bleskomat/",
              "isEnabled": false,
              "isInstalled": false,
            }
        }
      ));

      this.filteredExtensions = this.allExtensions;
      console.log(this.allExtensions);
    } else {
      alert("HTTP-Error: " + res.status);
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
  mixins: [windowMixin]
})
