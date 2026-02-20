window.app.component('lnbits-dialog', {
  template: '#lnbits-dialog',

  props: {
    show: {
      type: Boolean,
      default: false
    },
    title: {
      type: String,
      default: ''
    },
    position: {
      type: String,
      default: 'top'
    },
    persistent: {
      type: Boolean,
      default: true
    },
    showCancel: {
      type: Boolean,
      default: true
    },
    cancelLabel: {
      type: String,
      default: 'Close'
    },
    cancelColor: {
      type: String,
      default: 'grey'
    },
    action: {
      type: Object,
      default: null
    }
  },

  emits: ['update:show', 'hide', 'cancel', 'action'],

  computed: {
    hasAction() {
      return !!(this.action && this.action.label)
    },

    actionProps() {
      const action = this.action || {}
      return {
        label: action.label || 'Action',
        color: action.color || 'primary',
        loading: !!action.loading,
        disable: !!action.disable
      }
    }
  },

  methods: {
    handleModelUpdate(value) {
      this.$emit('update:show', value)
    },

    handleHide() {
      this.handleModelUpdate(false)
      this.$emit('hide')
    },

    handleCancel() {
      this.$emit('cancel')
    },

    async handleAction() {
      try {
        if (this.action && typeof this.action.handler === 'function') {
          await this.action.handler()
        }

        this.$emit('action')

        if (this.action && this.action.closeOnClick) {
          this.handleModelUpdate(false)
        }
      } catch (error) {
        console.error('lnbits-dialog action handler failed', error)
      }
    }
  }
})
