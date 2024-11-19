window.app = Vue.createApp({
  el: '#vue',
  mixins: [window.windowMixin],
  data: function () {
    return {}
  },

  created() {
    console.log('### audit entries')
  },

  methods: {}
})
