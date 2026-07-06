const seedBackupChallengeWordCount = 4
const seedBackupSources = {
  BoltzWallet: {
    label: 'Boltz',
    seedField: 'boltz_mnemonic',
    confirmField: 'boltz_mnemonic_backup_confirmed'
  },
  SparkL2Wallet: {
    label: 'Spark L2',
    seedField: 'spark_l2_mnemonic',
    confirmField: 'spark_l2_mnemonic_backup_confirmed'
  }
}

window.app.component('lnbits-admin-funding', {
  props: ['active', 'is-super-user', 'form-data', 'settings'],
  template: '#lnbits-admin-funding',
  data() {
    return {
      auditData: [],
      seedBackupDialog: {
        show: false,
        step: 1,
        sourceLabel: '',
        seed: '',
        visible: false,
        challenge: [],
        answers: {},
        error: '',
        confirmField: ''
      }
    }
  },
  watch: {
    active(isActive) {
      if (isActive) {
        this.openSeedBackupDialogIfRequired()
      }
    },
    'formData.lnbits_backend_wallet_class'(walletClass, previousWalletClass) {
      this.resetSeedBackupConfirmationOnSourceChange(
        walletClass,
        previousWalletClass
      )
      this.openSeedBackupDialogIfRequired()
    },
    'formData.boltz_mnemonic'() {
      this.syncSeedBackupConfirmation('boltz_mnemonic')
      this.openSeedBackupDialogIfRequired()
    },
    'formData.spark_l2_mnemonic'() {
      this.syncSeedBackupConfirmation('spark_l2_mnemonic')
      this.openSeedBackupDialogIfRequired()
    }
  },
  computed: {
    seedBackupWords() {
      return this.seedBackupDialog.seed
        .split(/\s+/)
        .filter(Boolean)
        .map((word, index) => ({index, word}))
    }
  },
  created() {
    this.getAudit()
    this.openSeedBackupDialogIfRequired()
  },
  methods: {
    seedBackupSource() {
      return seedBackupSources[this.formData.lnbits_backend_wallet_class]
    },
    resetSeedBackupConfirmationOnSourceChange(
      walletClass,
      previousWalletClass
    ) {
      if (!previousWalletClass || walletClass === previousWalletClass) return

      const source = seedBackupSources[walletClass]
      if (!source || !this.formData[source.seedField]) return

      this.formData[source.confirmField] = false
    },
    syncSeedBackupConfirmation(seedField) {
      const source = Object.values(seedBackupSources).find(
        source => source.seedField === seedField
      )
      if (!source) return

      this.formData[source.confirmField] =
        this.formData[source.seedField] === this.settings[source.seedField]
          ? this.settings[source.confirmField]
          : false
    },
    openSeedBackupDialogIfRequired() {
      if (!this.active || !this.isSuperUser) return

      const source = this.seedBackupSource()
      if (!source) return

      const seed = (this.formData[source.seedField] || '').trim()
      const confirmed = this.formData[source.confirmField]
      if (!seed || confirmed || this.seedBackupDialog.show) return

      this.seedBackupDialog = {
        show: true,
        step: 1,
        sourceLabel: source.label,
        seed,
        visible: false,
        challenge: [],
        answers: {},
        error: '',
        confirmField: source.confirmField
      }
    },
    prepareSeedBackupChallenge() {
      const words = this.seedBackupDialog.seed.split(/\s+/).filter(Boolean)
      const count = Math.min(seedBackupChallengeWordCount, words.length)
      const indexes = _.shuffle([...Array(words.length).keys()]).slice(0, count)
      this.seedBackupDialog.challenge = indexes
        .sort((a, b) => a - b)
        .map(index => ({index, word: words[index]}))
      this.seedBackupDialog.answers = {}
      this.seedBackupDialog.error = ''
      this.seedBackupDialog.step = 2
    },
    submitSeedBackupChallenge() {
      const isValid = this.seedBackupDialog.challenge.every(({index, word}) => {
        const answer = this.seedBackupDialog.answers[index] || ''
        return answer.trim().toLowerCase() === word.toLowerCase()
      })
      if (!isValid) {
        this.seedBackupDialog.error =
          'One or more words are incorrect. Check your backup and try again.'
        return
      }

      const field = this.seedBackupDialog.confirmField
      const data = {[field]: true}
      LNbits.api
        .request(
          'PATCH',
          '/admin/api/v1/settings',
          this.g.user.wallets[0].adminkey,
          data
        )
        .then(() => {
          this.formData[field] = true
          this.settings[field] = true
          this.seedBackupDialog.show = false
          Quasar.Notify.create({
            type: 'positive',
            message: 'Seed backup confirmed',
            icon: 'check'
          })
        })
        .catch(LNbits.utils.notifyApiError)
    },
    getAudit() {
      LNbits.api
        // TODO: should not use admin key here
        .request('GET', '/admin/api/v1/audit', this.g.user.wallets[0].adminkey)
        .then(response => {
          this.auditData = response.data
        })
        .catch(LNbits.utils.notifyApiError)
    }
  }
})
