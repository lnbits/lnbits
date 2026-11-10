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
      scriptType: 'p2wpkh',
      useCustomPath: false,
      customPath: '',
      addressTypes: [
        {label: 'Legacy', value: 'p2pkh', purpose: 44},
        {label: 'Wrapped SegWit', value: 'p2sh', purpose: 49},
        {label: 'Native SegWit', value: 'p2wpkh', purpose: 84},
        {label: 'Taproot', value: 'p2tr', purpose: 86}
      ],
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
    standardAccountPath() {
      const purpose = this.addressTypes.find(
        t => t.value === this.scriptType
      ).purpose
      const coin = this.network === 'Mainnet' ? 0 : 1
      return `m/${purpose}'/${coin}'/0'`
    },
    accountPath() {
      return this.useCustomPath
        ? this.customPath.trim()
        : this.standardAccountPath
    },
    backupAddressType() {
      const type = this.wallet?.onchain_meta?.script_type
      return this.addressTypes.find(t => t.value === type)?.label || type
    },
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
      this.mode = 'create'
      this.scriptType = 'p2wpkh'
      this.useCustomPath = false
      this.customPath = ''
      this.available = null
      this.show = true
      try {
        const {data} = await LNbits.api.request(
          'GET',
          '/api/v1/onchain/hot-wallet/status',
          this.adminkey
        )
        this.available = data.available
      } catch (_) {
        this.error =
          'Could not check hot wallet availability. Close and try again.'
      }
    },
    async createWallet() {
      if (this.busy) return
      const pathError = this.validateAccountPath(this.accountPath)
      if (pathError !== true) {
        this.error = pathError
        return
      }
      this.busy = true
      this.error = ''
      try {
        const {data} = await LNbits.api.request(
          'POST',
          '/api/v1/onchain/hot-wallet',
          this.adminkey,
          {
            title: this.g.wallet.name,
            network: this.network,
            script_type: this.scriptType,
            account_path: this.accountPath
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
    validateAccountPath(value) {
      const path = value.trim().replace(/[hH]/g, "'")
      if (!/^m(?:\/[0-9]{1,10}'?)+$/.test(path))
        return "Enter a BIP32 account path, such as m/84'/0'/0'"
      const parts = path.split('/').slice(1)
      if (
        path.length > 3037 ||
        parts.length > 253 ||
        parts.some(p => Number(p.replace("'", '')) >= 0x80000000)
      )
        return 'Derivation path depth or index is out of range'
      if (!path.endsWith("'"))
        return 'The account path must end in a hardened index. Do not include receiving/change branches or address indexes.'
      return true
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
          `/api/v1/onchain/hot-wallet/${this.wallet.id}/backup`,
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
          `/api/v1/onchain/hot-wallet/${this.wallet.id}/backup/confirm`,
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
