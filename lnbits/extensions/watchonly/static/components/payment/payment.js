async function payment(path) {
  const template = await loadTemplateAsync(path)
  Vue.component('payment', {
    name: 'payment',
    template,

    props: ['mempool_endpoint', 'sats_denominated'],

    data: function () {
      return {}
    },

    methods: {
      satBtc(val, showUnit = true) {
        return satOrBtc(val, showUnit, this['sats_denominated'])
      }
    },

    created: async function () {}
  })
}
