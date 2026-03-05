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
      default: false
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
    },
    secondaryAction: {
      type: Object,
      default: null
    }
  },

  emits: ['update:show', 'hide', 'cancel', 'action', 'secondary-action'],

  computed: {
    hasAction() {
      return !!(this.action && this.action.label)
    },
    hasSecondaryAction() {
      return !!(this.secondaryAction && this.secondaryAction.label)
    },

    actionProps() {
      const action = this.action || {}
      const obj = {
        label: action.label || 'Action',
        color: action.color || 'primary',
        loading: !!action.loading,
        disable: !!action.disable,
        closePopup: !!action.closePopup
      }
      if (action.icon) {
        obj.icon = action.icon
      }
      return obj
    },
    secondaryActionProps() {
      const action = this.secondaryAction || {}
      const obj = {
        label: action.label || 'Secondary',
        color: action.color || 'secondary',
        loading: !!action.loading,
        disable: !!action.disable,
        closePopup: !!action.closePopup
      }
      if (action.icon) {
        obj.icon = action.icon
      }
      return obj
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
    },
    async handleSecondaryAction() {
      try {
        if (
          this.secondaryAction &&
          typeof this.secondaryAction.handler === 'function'
        ) {
          await this.secondaryAction.handler()
        }
        this.$emit('secondary-action')
        if (this.secondaryAction && this.secondaryAction.closeOnClick) {
          this.handleModelUpdate(false)
        }
      } catch (error) {
        console.error('lnbits-dialog secondary action handler failed', error)
      }
    }
  }
})
