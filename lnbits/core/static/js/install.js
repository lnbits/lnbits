new Vue({
  el: '#vue',
  data: function () {
    return {
      searchTerm: '',
      tab: 'all',
      filteredExtensions: null,
      showUninstallDialog: false,
      showUpgradeDialog: false,
      selectedExtension: null,
      selectedExtensionRepos: null,
      maxStars: 5
    }
  },
  watch: {
    searchTerm(term) {
      this.filterExtensions(term, this.tab)
    }
  },
  methods: {
    handleTabChanged: function (tab) {
      this.filterExtensions(this.searchTerm, tab)
    },
    filterExtensions(term, tab) {
      // Filter the extensions list
      function extensionNameContains(searchTerm) {
        return function (extension) {
          return (
            extension.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
            extension.shortDescription
              ?.toLowerCase()
              .includes(searchTerm.toLowerCase())
          )
        }
      }

      this.filteredExtensions = this.extensions
        .filter(e => (tab === 'installed' ? e.isInstalled : true))
        .filter(e => (tab === 'featured' ? e.isFeatured : true))
        .filter(extensionNameContains(term))
    },
    async installExtension(release) {
      const extension = this.selectedExtension
      try {
        extension.inProgress = true
        this.showUpgradeDialog = false
        await LNbits.api.request(
          'POST',
          `/api/v1/extension?usr=${this.g.user.id}`,
          this.g.user.wallets[0].adminkey,
          {
            ext_id: extension.id,
            archive: release.archive,
            source_repo: release.source_repo
          }
        )
        window.location.href = [
          "{{ url_for('install.extensions') }}",
          '?usr=',
          this.g.user.id
        ].join('')
      } catch (error) {
        LNbits.utils.notifyApiError(error)
        extension.inProgress = false
      }
    },
    async uninstallExtension() {
      const extension = this.selectedExtension
      this.showUpgradeDialog = false
      this.showUninstallDialog = false
      try {
        extension.inProgress = true
        await LNbits.api.request(
          'DELETE',
          `/api/v1/extension/${extension.id}?usr=${this.g.user.id}`,
          this.g.user.wallets[0].adminkey
        )
        window.location.href = [
          "{{ url_for('install.extensions') }}",
          '?usr=',
          this.g.user.id
        ].join('')
      } catch (error) {
        LNbits.utils.notifyApiError(error)
        extension.inProgress = false
      }
    },
    toggleExtension: function (extension) {
      const action = extension.isActive ? 'activate' : 'deactivate'
      window.location.href = [
        "{{ url_for('install.extensions') }}",
        '?usr=',
        this.g.user.id,
        `&${action}=`,
        extension.id
      ].join('')
    },

    showUninstall() {
      this.showUpgradeDialog = false
      this.showUninstallDialog = true
    },

    async showUpgrade(extension) {
      this.selectedExtension = extension
      this.showUpgradeDialog = true
      this.selectedExtensionRepos = null
      try {
        const {data} = await LNbits.api.request(
          'GET',
          `/api/v1/extension/${extension.id}/releases?usr=${this.g.user.id}`,
          this.g.user.wallets[0].adminkey
        )

        this.selectedExtensionRepos = data.reduce((repos, release) => {
          repos[release.source_repo] = repos[release.source_repo] || {
            releases: [],
            isInstalled: false
          }
          release.isInstalled = this.isInstalledVersion(
            this.selectedExtension,
            release
          )
          if (release.isInstalled) {
            repos[release.source_repo].isInstalled = true
          }
          repos[release.source_repo].releases.push(release)
          return repos
        }, {})
      } catch (error) {
        LNbits.utils.notifyApiError(error)
        extension.inProgress = false
      }
    },
    hasNewVersion: function (extension) {
      if (extension.installedRelease && extension.latestRelease) {
        return (
          extension.installedRelease.version !== extension.latestRelease.version
        )
      }
    },
    isInstalledVersion: function (extension, release) {
      if (extension.installedRelease) {
        return (
          extension.installedRelease.source_repo === release.source_repo &&
          extension.installedRelease.version === release.version
        )
      }
    }
  },
  created() {
    console.log(window.extensions)
    console.log(window.user)
    this.extensions = JSON.parse(window.extensions).map(e => ({
      ...e,
      inProgress: false
    }))
    this.filteredExtensions = this.extensions.concat([])
  },
  mixins: [windowMixin]
})
