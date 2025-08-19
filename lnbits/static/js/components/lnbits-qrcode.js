window.app.component('lnbits-qrcode', {
  mixins: [window.windowMixin],
  template: '#lnbits-qrcode',
  components: {
    QrcodeVue
  },
  props: {
    value: {
      type: String,
      required: true
    },
    options: Object
  },
  data() {
    return {
      custom: {
        margin: 3,
        width: 350,
        size: 350,
        logo: LNBITS_QR_LOGO
      }
    }
  },
  created() {
    this.custom = {...this.custom, ...this.options}
  }
})
