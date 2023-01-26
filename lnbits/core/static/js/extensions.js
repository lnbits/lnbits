new Vue({
  el: '#vue',
  data: function () {
    return {
      searchTerm: '',
      filteredExtensions: null,
      maxStars: 5,
      user: null
    }
  },
  mounted() {
    this.filteredExtensions = this.g.extensions
  },
  watch: {
    searchTerm(term) {
      // Reset the filter
      this.filteredExtensions = this.g.extensions
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
  created() {
    if (window.user) {
      this.user = LNbits.map.user(window.user)
    }
  },
  mixins: [windowMixin]
})
