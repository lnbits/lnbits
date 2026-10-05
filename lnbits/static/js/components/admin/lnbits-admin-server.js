window.app.component('lnbits-admin-server', {
  props: ['form-data', 'is-super-user'],
  template: '#lnbits-admin-server',
  data() {
    return {
      onchain: null,
      onchainBusy: false,
      onchainError: '',
      backupDialog: false,
      backupDownloaded: false,
      backupSaved: false,
      backupFingerprint: '',
      restoreFile: null
    }
  },
  watch: {
    isSuperUser: {
      immediate: true,
      handler(isSuperUser) {
        if (isSuperUser) this.loadOnchainStatus()
        else {
          this.onchain = null
          this.backupDialog = false
          this.restoreFile = null
        }
      }
    }
  },
  methods: {
    async onchainRequest(method, path = '', headers = {}) {
      return LNbits.api.request(
        method,
        `/admin/api/v1/onchain/key${path}`,
        this.g.user.wallets[0].adminkey,
        undefined,
        {headers: {'X-Api-Key': this.g.user.wallets[0].adminkey, ...headers}}
      )
    },
    async loadOnchainStatus() {
      try {
        const {data} = await this.onchainRequest('GET')
        this.onchain = data
        this.onchainError = ''
      } catch (error) {
        this.onchainError = 'Could not load onchain settings. Try again.'
      }
    },
    async setupOnchain() {
      if (this.onchainBusy) return
      this.onchainBusy = true
      try {
        const {data} = await this.onchainRequest('POST')
        this.onchain = data
        this.openOnchainBackup()
      } catch (error) {
        LNbits.utils.notifyApiError(error)
      } finally {
        this.onchainBusy = false
      }
    },
    openOnchainBackup() {
      this.backupDownloaded = false
      this.backupSaved = false
      this.backupFingerprint = ''
      this.backupDialog = true
    },
    async downloadOnchainBackup() {
      if (this.onchainBusy) return
      this.onchainBusy = true
      try {
        const {data} = await this.onchainRequest('POST', '/backup')
        const result = Quasar.exportFile(
          'lnbits-onchain-key.json',
          JSON.stringify(data, null, 2),
          'application/json'
        )
        if (result !== true) throw new Error('Download failed')
        this.backupFingerprint = data.fingerprint
        this.backupDownloaded = true
      } catch (error) {
        Quasar.Notify.create({
          type: 'negative',
          message: 'Could not download the encryption key. Try again.'
        })
      } finally {
        this.onchainBusy = false
      }
    },
    async confirmOnchainBackup() {
      if (this.onchainBusy || !this.backupSaved || !this.backupDownloaded)
        return
      this.onchainBusy = true
      try {
        const {data} = await this.onchainRequest('POST', '/confirm', {
          'X-Onchain-Key-Fingerprint': this.backupFingerprint
        })
        this.onchain = data
        this.backupDialog = false
        Quasar.Notify.create({
          type: 'positive',
          message:
            'Key backup confirmed. You can now enable onchain payments and save settings.'
        })
      } catch (error) {
        LNbits.utils.notifyApiError(error)
      } finally {
        this.onchainBusy = false
      }
    },
    async restoreOnchain() {
      if (this.onchainBusy || !this.restoreFile) return
      this.onchainBusy = true
      try {
        if (this.restoreFile.size > 4096) throw new Error('Invalid backup file')
        const backup = JSON.parse(await this.restoreFile.text())
        if (
          backup.version !== 1 ||
          typeof backup.key !== 'string' ||
          !/^[A-Za-z0-9+/]{43}=$/.test(backup.key)
        ) {
          throw new Error('Invalid backup file')
        }
        const {data} = await this.onchainRequest('POST', '', {
          'X-Onchain-Recovery-Key': backup.key
        })
        this.onchain = data
        Quasar.Notify.create({
          type: 'positive',
          message: 'Onchain encryption key restored.'
        })
      } catch (error) {
        Quasar.Notify.create({
          type: 'negative',
          message:
            'Could not restore the key. Use the original backup for this instance and check server configuration.'
        })
      } finally {
        this.restoreFile = null
        this.onchainBusy = false
      }
    }
  },
  computed: {
    lightningAddressBlacklistText: {
      get() {
        const value = this.formData.lnbits_wallet_lightning_address_blacklist
        return Array.isArray(value) ? value.join('\n') : value || ''
      },
      set(value) {
        this.formData.lnbits_wallet_lightning_address_blacklist = value
          .split(/[\n,]/)
          .map(word => word.trim().toLowerCase())
          .filter(word => word.length)
      }
    }
  }
})
