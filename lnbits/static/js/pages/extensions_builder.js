window.PageExtensionBuilder = {
  template: '#page-extension-builder',
  mixins: [windowMixin],
  data() {
    return {
      step: 1,
      previewStepNames: {
        2: 'settings',
        3: 'owner_data',
        4: 'client_data',
        5: 'public_page'
      },
      extensionDataCleanString: '',
      extensionData: {
        id: '',
        name: '',
        stub_version: '',
        short_description: '',
        description: '',
        public_page: {
          has_public_page: true,
          owner_data_fields: {
            name: '',
            description: ''
          },
          client_data_fields: {
            public_inputs: []
          },
          action_fields: {
            generate_action: true,
            generate_payment_logic: false,
            wallet_id: '',
            currency: '',
            amount: '',
            paid_flag: ''
          }
        },
        preview_action: {
          is_preview_mode: false,
          is_settings_preview: false,
          is_owner_data_preview: false,
          is_client_data_preview: false,
          is_public_page_preview: false
        },
        settings_data: {
          name: 'Settings',
          enabled: true,
          type: 'user',
          fields: []
        },
        owner_data: {
          name: 'OwnerData',
          fields: []
        },
        client_data: {
          enabled: true,
          name: 'ClientData',
          fields: []
        }
      },
      sampleField: {
        name: 'name',
        type: 'str',
        label: 'Name',
        hint: '',
        optional: true,
        editable: true,
        searchable: true,
        sortable: true
      },

      settingsTypes: [
        {label: 'User Settings', value: 'user'},
        {label: 'Admin Settings', value: 'admin'}
      ],
      amountSource: [
        {label: 'Client Data', value: 'client_data'},
        {label: 'Owner Data', value: 'owner_data'}
      ],
      extensionStubVersions: []
    }
  },
  watch: {
    'extensionData.public_page.action_fields.amount_source': function (
      newVal,
      oldVal
    ) {
      if (oldVal && newVal !== oldVal) {
        this.extensionData.public_page.action_fields.amount = ''
      }
    }
  },
  computed: {
    paymentActionAmountFields() {
      const amount_source =
        this.extensionData.public_page.action_fields.amount_source
      if (!amount_source) return ['']

      if (amount_source === 'owner_data') {
        return [''].concat(
          this.extensionData.owner_data.fields
            .filter(f => f.type === 'int' || f.type === 'float')
            .map(f => f.name)
        )
      }
      if (amount_source === 'client_data') {
        return [''].concat(
          this.extensionData.client_data.fields
            .filter(f => f.type === 'int' || f.type === 'float')
            .map(f => f.name)
        )
      }
    }
  },
  methods: {
    saveState() {
      this.$q.localStorage.set(
        'lnbits.extension.builder.data',
        JSON.stringify(this.extensionData)
      )
      this.$q.localStorage.set('lnbits.extension.builder.step', this.step)
    },
    nextStep() {
      this.saveState()
      this.$refs.stepper.next()
      this.refreshPreview()
    },
    previousStep() {
      this.saveState()
      this.$refs.stepper.previous()
      this.refreshPreview()
    },
    onStepChange() {
      this.saveState()
      this.refreshPreview()
    },
    clearAllData() {
      LNbits.utils
        .confirmDialog(
          'Are you sure you want to clear all data? This action cannot be undone.'
        )
        .onOk(() => {
          this.extensionData = JSON.parse(this.extensionDataCleanString)
          this.$q.localStorage.remove('lnbits.extension.builder.data')
          this.$refs.stepper.set(1)
        })
    },
    exportJsonData() {
      const status = Quasar.exportFile(
        `${this.extensionData.id || 'data-export'}.json`,
        JSON.stringify(this.extensionData, null, 2),
        'text/json'
      )
      if (status !== true) {
        Quasar.Notify.create({
          message: 'Browser denied file download...',
          color: 'negative',
          icon: null
        })
      } else {
        Quasar.Notify.create({
          message: 'File downloaded!',
          color: 'positive',
          icon: 'file_download'
        })
      }
    },
    onJsonDataInput(event) {
      const file = event.target.files[0]
      const reader = new FileReader()
      reader.onload = e => {
        this.extensionData = {
          ...this.extensionData,
          ...JSON.parse(e.target.result)
        }
        this.$refs.extensionDataInput.value = null
        Quasar.Notify.create({
          message: 'File loaded!',
          color: 'positive',
          icon: 'file_upload'
        })
      }
      reader.readAsText(file)
    },
    async buildExtension() {
      try {
        const options = {responseType: 'blob'}
        const response = await LNbits.api.request(
          'POST',
          '/api/v1/extension/builder/zip',
          null,
          this.extensionData,
          options
        )

        // download the zip file
        const url = window.URL.createObjectURL(new Blob([response.data]))
        const a = document.createElement('a')
        a.href = url
        a.download = `${this.extensionData.id || 'lnbits-extension'}.zip`
        document.body.appendChild(a)
        a.click()
        a.remove()
        window.URL.revokeObjectURL(url)
      } catch (error) {
        LNbits.utils.notifyApiError(error)
      }
    },
    async buildExtensionAndDeploy() {
      try {
        const {data} = await LNbits.api.request(
          'POST',
          '/api/v1/extension/builder/deploy',
          null,
          this.extensionData
        )

        Quasar.Notify.create({
          message: data.message || 'Extension deployed!',
          color: 'positive'
        })
      } catch (error) {
        LNbits.utils.notifyApiError(error)
      }
    },
    async cleanCacheData() {
      LNbits.utils
        .confirmDialog(
          'Are you sure you want to clean the cache data? This action cannot be undone.',
          'Clean Cache Data'
        )
        .onOk(async () => {
          try {
            const {data} = await LNbits.api.request(
              'DELETE',
              '/api/v1/extension/builder',
              null,
              {}
            )

            Quasar.Notify.create({
              message: data.message || 'Cache data cleaned!',
              color: 'positive'
            })
          } catch (error) {
            LNbits.utils.notifyApiError(error)
          }
        })
    },
    async previewExtension(previewPageName) {
      this.saveState()
      try {
        await LNbits.api.request(
          'POST',
          '/api/v1/extension/builder/preview',
          null,
          {
            ...this.extensionData,
            ...{
              preview_action: {
                is_preview_mode: !!previewPageName,
                is_settings_preview: previewPageName === 'settings',
                is_owner_data_preview: previewPageName === 'owner_data',
                is_client_data_preview: previewPageName === 'client_data',
                is_public_page_preview: previewPageName === 'public_page'
              }
            }
          }
        )

        this.refreshIframe(previewPageName)
      } catch (error) {
        LNbits.utils.notifyApiError(error)
      }
    },
    async refreshPreview() {
      setTimeout(() => {
        const stepName = this.previewStepNames[`${this.step}`] || ''
        if (!stepName) return
        this.previewExtension(stepName)
      }, 100)
    },
    async getStubExtensionReleases() {
      try {
        const stub_ext_id = 'extension_builder_stub'
        const {data} = await LNbits.api.request(
          'GET',
          `/api/v1/extension/${stub_ext_id}/releases`
        )

        this.extensionStubVersions = data.sort((a, b) =>
          a.version < b.version ? 1 : -1
        )
        this.extensionData.stub_version = this.extensionStubVersions[0]
          ? this.extensionStubVersions[0].version
          : ''
      } catch (error) {
        LNbits.utils.notifyApiError(error)
      }
    },
    refreshIframe(previewPageName = '') {
      const iframe = this.$refs[`iframeStep${this.step}`]
      if (!iframe) {
        console.warn('Extension Builder Preview iframe not loaded yet.')
        return
      }
      iframe.onload = () => {
        const iframeDoc =
          iframe.contentDocument || iframe.contentWindow.document

        iframeDoc.body.style.transform = 'scale(0.8)'
        iframeDoc.body.style.transformOrigin = 'center top'
      }
      iframe.src = `/extensions/builder/preview/${this.extensionData.id}?page_name=${previewPageName}`
    },
    initBasicData() {
      this.extensionData.owner_data.fields = [
        JSON.parse(JSON.stringify(this.sampleField))
      ]
      this.extensionData.client_data.fields = [
        JSON.parse(JSON.stringify(this.sampleField))
      ]
      this.extensionData.settings_data.fields = [
        JSON.parse(JSON.stringify(this.sampleField))
      ]
      this.extensionDataCleanString = JSON.stringify(this.extensionData)
    }
  },
  created() {
    this.initBasicData()

    const extensionData = this.$q.localStorage.getItem(
      'lnbits.extension.builder.data'
    )
    if (extensionData) {
      this.extensionData = {...this.extensionData, ...JSON.parse(extensionData)}
    }
    const step = +this.$q.localStorage.getItem('lnbits.extension.builder.step')
    if (step) {
      this.step = step
    }
    if (this.g.user.admin) {
      this.getStubExtensionReleases()
    }

    setTimeout(() => {
      this.refreshIframe()
    }, 1000)
  }
}
