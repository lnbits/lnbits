new Vue({
  el: '#vue',
  mixins: [windowMixin],
  methods: {
    notify: function () {
      this.$q.notify({
        timeout: 0,
        message: 'Processing...',
        icon: null
      });
    }
  }
});
