new Vue({
  el: '#vue',
  mixins: [windowMixin],
  data: function () {
    return {
      user: null
    }
  },
  created: async function () {
    const {data} = await LNbits.api.getAuthenticatedUser()
    this.user = data
    console.log('### user', user)
  },

  methods: {}
})
