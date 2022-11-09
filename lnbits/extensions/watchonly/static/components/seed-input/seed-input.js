async function seedInput(path) {
  const template = await loadTemplateAsync(path)
  Vue.component('seed-input', {
    name: 'seed-input',
    template,

    computed: {
      actualPosition: function () {
        return this.words[this.currentPosition].position
      }
    },

    data: function () {
      return {
        wordCountOptions: ['12', '15', '18', '21', '24'],
        wordCount: 24,
        words: [],
        currentPosition: 0,
        stringOptions: [],
        options: [],
        currentWord: '',
        done: false
      }
    },

    methods: {
      filterFn(val, update, abort) {
        update(() => {
          const needle = val.toLocaleLowerCase()
          this.options = this.stringOptions
            .filter(v => v.toLocaleLowerCase().indexOf(needle) != -1)
            .sort((a, b) => {
              if (a.startsWith(needle)) {
                if (b.startsWith(needle)) {
                  return a - b
                }
                return -1
              } else {
                if (b.startsWith(needle)) {
                  return 1
                }
                return a - b
              }
            })
        })
      },
      initWords() {
        const words = []
        for (let i = 1; i <= this.wordCount; i++) {
          words.push({
            position: i,
            value: ''
          })
        }
        this.currentPosition = 0
        this.words = _.shuffle(words)
      },
      setModel(val) {
        this.currentWord = val
        this.words[this.currentPosition].value = this.currentWord
      },
      nextPosition() {
        if (this.currentPosition < this.wordCount - 1) {
          this.currentPosition++
        }
        this.currentWord = this.words[this.currentPosition].value
      },
      previousPosition() {
        if (this.currentPosition > 0) {
          this.currentPosition--
        }
        this.currentWord = this.words[this.currentPosition].value
      },
      seedInputDone() {
        const badWordPositions = this.words
          .filter(w => !w.value || !this.stringOptions.includes(w.value))
          .map(w => w.position)
        if (badWordPositions.length) {
          this.$q.notify({
            timeout: 10000,
            type: 'warning',
            message:
              'The seed has incorrect words. Please check at these positions: ',
            caption: 'Position: ' + badWordPositions.join(', ')
          })
          return
        }
        const mnemonic = this.words
          .sort((a, b) => a.position - b.position)
          .map(w => w.value)
          .join(' ')
        this.$emit('on-seed-input-done', mnemonic)
        this.done = true
      }
    },

    created: async function () {
      this.stringOptions = bip39WordList
      this.initWords()
    }
  })
}
