window.app.component('lnbits-dialog', {
  template: '#lnbits-dialog',

  props: {
    show: {
      type: Boolean,
      required: true
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
    showConfirm: {
      type: Boolean,
      default: false
    },
    confirmLabel: {
      type: String,
      default: 'Confirm'
    },
    confirmColor: {
      type: String,
      default: 'primary'
    },
    confirmOutline: {
      type: Boolean,
      default: false
    },
    confirmFlat: {
      type: Boolean,
      default: false
    },
    confirmLoading: {
      type: Boolean,
      default: false
    },
    confirmDisable: {
      type: Boolean,
      default: false
    }
  },

  emits: ['update:show', 'hide', 'cancel', 'confirm'],

  computed: {
    hasActionsSlot() {
      return !!this.$slots.actions
    }
  },

  methods: {
    handleHide() {
      this.$emit('update:show', false)
      this.$emit('hide')
    },

    handleCancel() {
      this.$emit('cancel')
    },

    handleConfirm() {
      this.$emit('confirm')
    }
  }
})
