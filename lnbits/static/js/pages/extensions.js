window.PageExtensions = {
  template: '#page-extensions',
  mixins: [window.windowMixin],
  data() {
    return {
      extbuilderEnabled: false,
      slide: 0,
      fullscreen: false,
      autoplay: true,
      searchTerm: '',
      tab: 'installed',
      manageExtensionTab: 'releases',
      filteredExtensions: [],
      updatableExtensions: [],
      showUninstallDialog: false,
      showManageExtensionDialog: false,
      showExtensionDetailsDialog: false,
      showDropDbDialog: false,
      showPayToEnableDialog: false,
      showUpdateAllDialog: false,
      dropDbExtensionId: '',
      selectedExtension: null,
      selectedImage: null,
      selectedExtensionDetails: null,
      selectedExtensionRepos: null,
      selectedRelease: null,
      uninstallAndDropDb: false,
      maxStars: 5,
      paylinkWebsocket: null
    }
  },
  watch: {
    searchTerm(term) {
      this.filterExtensions(term, this.tab)
    },
    tab(val) {
      this.filterExtensions(this.searchTerm, val)
    }
  },
  methods: {
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
        .filter(e => (tab === 'all' ? !e.isInstalled : true))
        .filter(e => (tab === 'installed' ? e.isInstalled : true))
        .filter(e =>
          tab === 'installed' ? (e.isActive ? true : !!this.g.user.admin) : true
        )
        .filter(e => (tab === 'featured' ? e.isFeatured : true))
        .filter(extensionNameContains(term))
        .map(e => ({
          ...e,
          details_link:
            e.installedRelease?.details_link || e.latestRelease?.details_link
        }))
    },

    async installExtension(release) {
      // no longer required to check if the invoice was paid
      // the install logic has been triggered one way or another
      this.unsubscribeFromPaylinkWs()

      const extension = this.selectedExtension
      this.selectedExtension.inProgress = true
      this.showManageExtensionDialog = false
      release.payment_hash =
        release.payment_hash || this.getPaylinkHash(release.pay_link)

      LNbits.api
        .request('POST', `/api/v1/extension`, this.g.user.wallets[0].adminkey, {
          ext_id: this.selectedExtension.id,
          archive: release.archive,
          source_repo: release.source_repo,
          payment_hash: release.payment_hash,
          version: release.version
        })
        .then(response => {
          this.selectedExtension.inProgress = false
          const extension = this.extensions.find(
            ext => ext.id === this.selectedExtension.id
          )
          extension.isAvailable = true
          extension.isInstalled = true
          extension.installedRelease = release
          this.toggleExtension(extension)
          extension.inProgress = false
          this.selectedExtension = extension
          this.extensions = this.extensions.concat([])
          this.tab = 'installed'
        })
        .catch(err => {
          console.warn(err)
          this.selectedExtension.inProgress = false
          LNbits.utils.notifyApiError(err)
        })
    },
    async uninstallExtension() {
      this.showManageExtensionDialog = false
      this.showUninstallDialog = false
      this.selectedExtension.inProgress = true
      LNbits.api
        .request(
          'DELETE',
          `/api/v1/extension/${this.selectedExtension.id}`,
          this.g.user.wallets[0].adminkey
        )
        .then(response => {
          const extension = this.extensions.find(
            ext => ext.id === this.selectedExtension.id
          )
          extension.isAvailable = false
          extension.isInstalled = false
          extension.inProgress = false
          extension.installedRelease = null
          this.filteredExtensions = this.filteredExtensions.filter(
            ext => ext.id !== extension.id
          )
          Quasar.Notify.create({
            type: 'positive',
            message: 'Extension uninstalled!'
          })
          if (this.uninstallAndDropDb) {
            this.showDropDb()
          }
        })
        .catch(err => {
          LNbits.utils.notifyApiError(err)
          extension.inProgress = false
        })
    },
    async dropExtensionDb() {
      const extension = this.selectedExtension
      this.showManageExtensionDialog = false
      this.showDropDbDialog = false
      this.dropDbExtensionId = ''
      extension.inProgress = true
      LNbits.api
        .request(
          'DELETE',
          `/api/v1/extension/${extension.id}/db`,
          this.g.user.wallets[0].adminkey
        )
        .then(response => {
          extension.installedRelease = null
          extension.inProgress = false
          extension.hasDatabaseTables = false
          Quasar.Notify.create({
            type: 'positive',
            message: 'Extension DB deleted!'
          })
        })
        .catch(err => {
          LNbits.utils.notifyApiError(err)
          extension.inProgress = false
        })
    },
    toggleExtension(extension) {
      const action = extension.isActive ? 'activate' : 'deactivate'
      LNbits.api
        .request(
          'PUT',
          `/api/v1/extension/${extension.id}/${action}`,
          this.g.user.wallets[0].adminkey
        )
        .then(response => {
          Quasar.Notify.create({
            timeout: 2000,
            type: 'positive',
            message: `Extension '${extension.id}' ${action}d!`
          })
        })
        .catch(err => {
          LNbits.utils.notifyApiError(err)
          extension.isActive = false
          extension.inProgress = false
        })
    },
    async enableExtensionForUser(extension) {
      if (extension.isPaymentRequired) {
        this.showPayToEnable(extension)
        return
      }
      this.enableExtension(extension)
    },
    async enableExtension(extension) {
      LNbits.api
        .request(
          'PUT',
          `/api/v1/extension/${extension.id}/enable`,
          this.g.user.wallets[0].adminkey
        )
        .then(response => {
          this.g.user.extensions = this.g.user.extensions.concat([extension.id])
          Quasar.Notify.create({
            type: 'positive',
            message: 'Extension enabled!'
          })
        })
        .catch(err => {
          console.warn(err)
          LNbits.utils.notifyApiError(err)
        })
    },
    disableExtension(extension) {
      LNbits.api
        .request(
          'PUT',
          `/api/v1/extension/${extension.id}/disable`,
          this.g.user.wallets[0].adminkey
        )
        .then(response => {
          this.g.user.extensions = this.g.user.extensions.filter(
            ext => ext !== extension.id
          )
          Quasar.Notify.create({
            type: 'positive',
            message: 'Extension disabled!'
          })
        })
        .catch(err => {
          console.warn(error)
          LNbits.utils.notifyApiError(err)
        })
    },
    showPayToEnable(extension) {
      this.selectedExtension = extension
      this.selectedExtension.payToEnable.paidAmount =
        extension.payToEnable.amount
      this.selectedExtension.payToEnable.showQRCode = false
      this.showPayToEnableDialog = true
    },
    updatePayToInstallData(extension) {
      LNbits.api
        .request(
          'PUT',
          `/api/v1/extension/${extension.id}/sell`,
          this.g.user.wallets[0].adminkey,
          {
            required: extension.payToEnable.required,
            amount: extension.payToEnable.amount,
            wallet: extension.payToEnable.wallet
          }
        )
        .then(response => {
          Quasar.Notify.create({
            type: 'positive',
            message: 'Payment info updated!'
          })
          this.showManageExtensionDialog = false
        })
        .catch(err => {
          LNbits.utils.notifyApiError(err)
          extension.inProgress = false
        })
    },

    showUninstall() {
      this.showManageExtensionDialog = false
      this.showUninstallDialog = true
      this.uninstallAndDropDb = false
    },

    showDropDb() {
      this.showDropDbDialog = true
    },

    async showManageExtension(extension) {
      this.selectedExtension = extension
      this.selectedRelease = null
      this.selectedExtensionRepos = null
      this.manageExtensionTab = 'releases'
      this.showManageExtensionDialog = true

      try {
        const {data} = await LNbits.api.request(
          'GET',
          `/api/v1/extension/${extension.id}/releases`,
          this.g.user.wallets[0].adminkey
        )

        this.selectedExtensionRepos = data.reduce((repos, release) => {
          repos[release.source_repo] = repos[release.source_repo] || {
            releases: [],
            isInstalled: false,
            repo: release.repo
          }
          release.inProgress = false
          release.error = null
          release.loaded = false
          release.isInstalled = this.isInstalledVersion(
            this.selectedExtension,
            release
          )
          if (release.isInstalled) {
            repos[release.source_repo].isInstalled = true
          }
          if (release.pay_link) {
            release.requiresPayment = true
            release.paidAmount = release.cost_sats
            release.payment_hash = this.getPaylinkHash(release.pay_link)
          }

          repos[release.source_repo].releases.push(release)
          return repos
        }, {})
      } catch (error) {
        LNbits.utils.notifyApiError(error)
        extension.inProgress = false
      }
    },

    async showExtensionDetails(extId, detailsLink) {
      if (!detailsLink) {
        return
      }
      this.selectedExtensionDetails = null
      this.showExtensionDetailsDialog = true
      this.slide = 0
      this.fullscreen = false

      try {
        const {data} = await LNbits.api.request(
          'GET',
          `/api/v1/extension/${extId}/details?details_link=${detailsLink}`,
          this.g.user.wallets[0].inkey
        )

        this.selectedExtensionDetails = data
        this.selectedExtensionDetails.description_md =
          LNbits.utils.convertMarkdown(data.description_md)
      } catch (error) {
        console.warn(error)
      }
    },
    async payAndInstall(release) {
      try {
        this.selectedExtension.inProgress = true
        this.showManageExtensionDialog = false
        const paymentInfo = await this.requestPaymentForInstall(
          this.selectedExtension.id,
          release
        )
        this.rememberPaylinkHash(release.pay_link, paymentInfo.payment_hash)
        const wallet = this.g.user.wallets.find(w => w.id === release.wallet)
        const {data} = await LNbits.api.payInvoice(
          wallet,
          paymentInfo.payment_request
        )

        release.payment_hash = data.payment_hash

        await this.installExtension(release)
      } catch (err) {
        console.warn(err)
        LNbits.utils.notifyApiError(err)
      } finally {
        this.selectedExtension.inProgress = false
      }
    },
    async payAndEnable(extension) {
      try {
        const paymentInfo = await this.requestPaymentForEnable(
          extension.id,
          extension.payToEnable.paidAmount
        )

        const wallet = this.g.user.wallets.find(
          w => w.id === extension.payToEnable.paymentWallet
        )
        const {data} = await LNbits.api.payInvoice(
          wallet,
          paymentInfo.payment_request
        )
        this.enableExtension(extension)
        this.showPayToEnableDialog = false
      } catch (err) {
        console.warn(err)
        LNbits.utils.notifyApiError(err)
      }
    },
    async showInstallQRCode(release) {
      this.selectedRelease = release

      try {
        const data = await this.requestPaymentForInstall(
          this.selectedExtension.id,
          release
        )

        this.selectedRelease.paymentRequest = data.payment_request
        this.selectedRelease.payment_hash = data.payment_hash
        this.selectedRelease = _.clone(this.selectedRelease)
        this.rememberPaylinkHash(
          this.selectedRelease.pay_link,
          this.selectedRelease.payment_hash
        )

        this.subscribeToPaylinkWs(
          this.selectedRelease.pay_link,
          data.payment_hash
        )
      } catch (err) {
        console.warn(err)
        LNbits.utils.notifyApiError(err)
      }
    },

    async showEnableQRCode(extension) {
      try {
        extension.payToEnable.showQRCode = true
        this.selectedExtension = _.clone(extension)

        const data = await this.requestPaymentForEnable(
          extension.id,
          extension.payToEnable.paidAmount
        )
        extension.payToEnable.paymentRequest = data.payment_request
        this.selectedExtension = _.clone(extension)

        const url = new URL(window.location)
        url.protocol = url.protocol === 'https:' ? 'wss' : 'ws'
        url.pathname = `/api/v1/ws/${data.payment_hash}`
        const ws = new WebSocket(url)
        ws.addEventListener('message', async ({data}) => {
          const payment = JSON.parse(data)
          if (payment.pending === false) {
            Quasar.Notify.create({
              type: 'positive',
              message: 'Invoice Paid!'
            })

            this.enableExtension(extension)
            ws.close()
          }
        })
      } catch (err) {
        console.warn(err)
        LNbits.utils.notifyApiError(err)
      }
    },

    async requestPaymentForInstall(extId, release) {
      const {data} = await LNbits.api.request(
        'PUT',
        `/api/v1/extension/${extId}/invoice/install`,
        this.g.user.wallets[0].adminkey,
        {
          ext_id: extId,
          archive: release.archive,
          source_repo: release.source_repo,
          cost_sats: release.paidAmount,
          version: release.version
        }
      )
      return data
    },

    async requestPaymentForEnable(extId, amount) {
      const {data} = await LNbits.api.request(
        'PUT',
        `/api/v1/extension/${extId}/invoice/enable`,
        this.g.user.wallets[0].adminkey,
        {
          amount
        }
      )
      return data
    },

    clearHangingInvoice(release) {
      this.forgetPaylinkHash(release.pay_link)
      release.payment_hash = null
    },

    rememberPaylinkHash(pay_link, payment_hash) {
      this.$q.localStorage.set(
        `lnbits.extensions.paylink.${pay_link}`,
        payment_hash
      )
    },
    getPaylinkHash(pay_link) {
      return this.$q.localStorage.getItem(
        `lnbits.extensions.paylink.${pay_link}`
      )
    },
    forgetPaylinkHash(pay_link) {
      this.$q.localStorage.remove(`lnbits.extensions.paylink.${pay_link}`)
    },
    subscribeToPaylinkWs(pay_link, payment_hash) {
      const url = new URL(`${pay_link}/${payment_hash}`)
      url.protocol = url.protocol === 'https:' ? 'wss' : 'ws'
      this.paylinkWebsocket = new WebSocket(url)
      this.paylinkWebsocket.addEventListener('message', async ({data}) => {
        const resp = JSON.parse(data)
        if (resp.paid) {
          Quasar.Notify.create({
            type: 'positive',
            message: 'Invoice Paid!'
          })
          this.installExtension(this.selectedRelease)
        } else {
          Quasar.Notify.create({
            type: 'warning',
            message: 'Invoice tracking lost!'
          })
        }
      })
    },
    unsubscribeFromPaylinkWs() {
      try {
        this.paylinkWebsocket && this.paylinkWebsocket.close()
      } catch (error) {
        console.warn(error)
      }
    },

    hasNewVersion(extension) {
      if (extension.installedRelease && extension.latestRelease) {
        return (
          extension.installedRelease.version !== extension.latestRelease.version
        )
      }
    },
    isInstalledVersion(extension, release) {
      if (extension.installedRelease) {
        return (
          extension.installedRelease.source_repo === release.source_repo &&
          extension.installedRelease.version === release.version
        )
      }
    },
    getReleaseIcon(release) {
      if (!release.is_version_compatible) return 'block'
      if (release.isInstalled) return 'download_done'

      return 'download'
    },
    getReleaseIconColor(release) {
      if (!release.is_version_compatible) return 'text-red'
      if (release.isInstalled) return 'text-green'

      return ''
    },
    async getGitHubReleaseDetails(release) {
      if (!release.is_github_release || release.loaded) {
        return
      }
      const [org, repo] = release.source_repo.split('/')
      release.inProgress = true
      try {
        const {data} = await LNbits.api.request(
          'GET',
          `/api/v1/extension/release/${org}/${repo}/${release.version}`,
          this.g.user.wallets[0].adminkey
        )
        release.loaded = true
        release.is_version_compatible = data.is_version_compatible
        release.min_lnbits_version = data.min_lnbits_version
        release.warning = data.warning
      } catch (error) {
        console.warn(error)
        release.error = error
        LNbits.utils.notifyApiError(error)
      } finally {
        release.inProgress = false
      }
    },
    async selectAllUpdatableExtensionss() {
      this.updatableExtensions.forEach(e => (e.selectedForUpdate = true))
    },
    async updateSelectedExtensions() {
      let count = 0
      for (const ext of this.updatableExtensions) {
        try {
          if (!ext.selectedForUpdate) {
            continue
          }
          ext.inProgress = true
          await LNbits.api.request(
            'POST',
            `/api/v1/extension`,
            this.g.user.wallets[0].adminkey,
            {
              ext_id: ext.id,
              archive: ext.latestRelease.archive,
              source_repo: ext.latestRelease.source_repo,
              payment_hash: ext.latestRelease.payment_hash,
              version: ext.latestRelease.version
            }
          )
          count++
          ext.isAvailable = true
          ext.isInstalled = true
          ext.isUpgraded = true
          ext.inProgress = false
          ext.installedRelease = ext.latestRelease
          ext.isActive = true
          this.toggleExtension(ext)
        } catch (err) {
          console.warn(err)
          Quasar.Notify.create({
            type: 'negative',
            message: `Failed to update ${ext.id}!`
          })
        } finally {
          ext.inProgress = false
        }
      }
      Quasar.Notify.create({
        type: count ? 'positive' : 'warning',
        message: `${count ? count : 'No'} extensions updated!`
      })
      this.showUpdateAllDialog = false
    },
    async fetchAllExtensions() {
      try {
        const {data} = await LNbits.api.request('GET', `/api/v1/extension/all`)
        return data
      } catch (error) {
        console.warn(error)
        LNbits.utils.notifyApiError(error)
        return []
      }
    }
  },
  async created() {
    this.extensions = await this.fetchAllExtensions()
    this.extbuilderEnabled = this.g.user.admin || this.LNBITS_EXT_BUILDER

    if (this.g.user.extensions.length === 0) {
      this.tab = 'all'
    }

    const extId = window.location.hash.replace('#', '')
    const ext = this.extensions.find(ext => ext.id === extId)

    if (ext) {
      this.searchTerm = ext.id
      if (ext.isInstalled) this.tab = 'installed'
    }
    this.updatableExtensions = this.extensions.filter(ext =>
      this.hasNewVersion(ext)
    )

    this.filterExtensions(this.searchTerm, this.tab)
  }
}
