window.ExtensionsPageLogic = {
  data: function () {
    return {
      slide: 0,
      fullscreen: false,
      autoplay: true,
      searchTerm: '',
      tab: 'all',
      manageExtensionTab: 'releases',
      filteredExtensions: null,
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
      paylinkWebsocket: null,
      user: null
    }
  },

  methods: {},
  created: function () {},
  mixins: [windowMixin]
}
