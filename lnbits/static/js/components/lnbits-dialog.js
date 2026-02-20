window.app.component('lnbits-dialog', {
  template: '#lnbits-dialog',

  props: {
    show: {
      type: Boolean,
      default: undefined
    },
    modelValue: {
      type: Boolean,
      default: undefined
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

  emits: ['update:show', 'update:model-value', 'hide', 'cancel', 'action'],

  computed: {
    hasAction() {
      return !!(this.action && this.action.label)
    },

    actionProps() {
      const action = this.action || {}
      return {
        label: action.label || 'Action',
        color: action.color || 'primary',
        outline: !!action.outline,
        flat: !!action.flat,
        unelevated: !!action.unelevated,
        noCaps: !!action.noCaps,
        icon: action.icon || undefined,
        loading: !!action.loading,
        disable: !!action.disable
      }
    },

    dialogShow() {
      if (typeof this.show === 'boolean') return this.show
      if (typeof this.modelValue === 'boolean') return this.modelValue
      return false
    }
  },

  methods: {
    handleModelUpdate(value) {
      this.$emit('update:show', value)
      this.$emit('update:model-value', value)
    },

    handleHide() {
      this.handleModelUpdate(false)
      this.$emit('hide')
    },

    handleCancel() {
      this.$emit('cancel')
    },

    handleAction() {
      if (this.action && typeof this.action.handler === 'function') {
        this.action.handler()
      }

      this.$emit('action')

      if (this.action && this.action.closeOnClick) {
        this.handleModelUpdate(false)
      }
    }
  }
})
