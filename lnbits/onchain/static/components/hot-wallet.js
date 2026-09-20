window.app.component('onchain-hot-wallet', {
  template: '#onchain-hot-wallet',
  props: ['adminkey', 'network'],
  emits: ['wallet-created', 'backup-done'],
  data() {
    return {
      show: false,
      busy: false,
      available: null,
      mode: 'create',
      title: '',
      mnemonic: '',
      wallet: null,
      phrase: '',
      backupStep: 1,
      wordsVisible: false,
      challenge: [],
      answers: {},
      backupSession: 0,
      error: ''
    }
  },
  computed: {
    seedWords() {
      const words = this.phrase
        ? this.phrase.trim().split(/\s+/)
        : Array(24).fill('')
      return words.map((word, index) => ({index, word}))
    }
  },
  methods: {
    resetSecrets() {
      this.mnemonic = ''
      this.phrase = ''
      this.backupStep = 1
      this.wordsVisible = false
      this.challenge = []
      this.answers = {}
      this.backupSession++
      this.error = ''
    },
    async openCreate() {
      this.resetSecrets()
      this.wallet = null
      this.title = ''
      this.mode = 'create'
      this.available = null
      this.show = true
      try {
        const {data} = await LNbits.api.request(
          'GET',
          '/onchain/api/v1/hot-wallet/status',
          this.adminkey
        )
        this.available = data.available
      } catch (_) {
        this.error =
          'Could not check server wallet availability. Close and try again.'
      }
    },
    async createWallet() {
      if (this.busy || !this.title.trim()) return
      this.busy = true
      this.error = ''
      try {
        const {data} = await LNbits.api.request(
          'POST',
          '/onchain/api/v1/hot-wallet',
          this.adminkey,
          {
            title: this.title.trim(),
            network: this.network
          },
          this.mode === 'restore'
            ? {
                headers: {
                  'X-Api-Key': this.adminkey,
                  'X-Onchain-Recovery-Phrase': this.mnemonic
                    .trim()
                    .replace(/\s+/g, ' ')
                }
              }
            : {}
        )
        this.mnemonic = ''
        this.wallet = data
        this.$emit('wallet-created', data)
        this.mode = 'backup'
      } catch (_) {
        this.error =
          'Could not create the wallet. Check the recovery phrase, server availability, and whether this wallet already exists.'
      } finally {
        this.busy = false
      }
    },
    openBackup(wallet) {
      this.resetSecrets()
      this.wallet = wallet
      this.mode = 'backup'
      this.show = true
    },
    async revealBackup() {
      if (this.busy) return
      if (this.wordsVisible) {
        this.wordsVisible = false
        return
      }
      if (this.phrase) {
        this.wordsVisible = true
        return
      }
      const session = this.backupSession
      this.busy = true
      this.error = ''
      try {
        const {data} = await LNbits.api.request(
          'POST',
          `/onchain/api/v1/hot-wallet/${this.wallet.id}/backup`,
          this.adminkey
        )
        if (this.show && !document.hidden && session === this.backupSession) {
          this.phrase = data.mnemonic
          this.wordsVisible = true
        }
      } catch (_) {
        this.error =
          'Could not unlock the backup. Ask the server administrator to check the wallet encryption key.'
      } finally {
        this.busy = false
      }
    },
    prepareChallenge() {
      if (this.busy || !this.phrase) return
      this.challenge = _.shuffle(this.seedWords.map(({index}) => index))
        .slice(0, 4)
        .sort((a, b) => a - b)
      this.answers = {}
      this.error = ''
      this.wordsVisible = false
      this.backupStep = 2
    },
    backToWords() {
      this.backupStep = 1
      this.wordsVisible = false
      this.answers = {}
      this.challenge = []
      this.error = ''
    },
    async confirmBackup() {
      if (
        this.busy ||
        this.backupStep !== 2 ||
        !this.phrase ||
        this.challenge.length !== 4
      )
        return
      const valid = this.challenge.every(
        index =>
          (this.answers[index] || '').trim().toLowerCase() ===
          this.seedWords[index].word.toLowerCase()
      )
      if (!valid) {
        this.error =
          'One or more words are incorrect. Check your backup and try again.'
        return
      }
      this.error = ''
      this.busy = true
      try {
        await LNbits.api.request(
          'POST',
          `/onchain/api/v1/hot-wallet/${this.wallet.id}/backup/confirm`,
          this.adminkey
        )
        this.resetSecrets()
        this.show = false
        this.$emit('backup-done')
      } catch (_) {
        this.error = 'Could not save backup confirmation. Please try again.'
      } finally {
        this.busy = false
      }
    },
    hideSecrets() {
      if (document.hidden) this.resetSecrets()
    }
  },
  mounted() {
    document.addEventListener('visibilitychange', this.hideSecrets)
  },
  beforeUnmount() {
    this.show = false
    document.removeEventListener('visibilitychange', this.hideSecrets)
    this.resetSecrets()
  }
})
