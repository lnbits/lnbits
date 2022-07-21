new Vue({
    el: '#vue',
    data: function () {
        console.log(this)
        return {
            searchTerm: '',
            filteredExtensions: null
        }
    },
    mounted() {
        this.filteredExtensions = this.g.extensions
    },
    watch: {
        searchTerm(term) {
            // Reset the filter
            this.filteredExtensions = this.g.extensions
            if(term !== "") { // Filter the extensions list
                function extensionNameContains(searchTerm) {
                    console.log('wordToCompare', searchTerm)
                    return function (extension) {
                        if(
                            extension.name.toLowerCase().indexOf(searchTerm.toLowerCase()) > -1
                            ||
                            extension.shortDescription.toLowerCase().indexOf(searchTerm.toLowerCase()) > -1
                        ) {
                            return true
                        }
                        return false
                    }
                }

                this.filteredExtensions = this.filteredExtensions
                    .filter(extensionNameContains(term));
            }
        }
    },
    mixins: [windowMixin]
})