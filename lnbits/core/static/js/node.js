Vue.component('lnbits-node-ranks', {
  props: ['node'],
  data: function () {
    return {
      ranks: {},
      user: {},
      stats: [
        {label: 'Capacity', key: 'capacity'},
        {label: 'Channel Count', key: 'channelcount'},
        {label: 'Age', key: 'age'},
        {label: 'Growth', key: 'growth'},
        {label: 'Availability', key: 'availability'}
      ]
    }
  },
  template: `
    <q-card class="q-my-none">
      <div class="column q-mx-md q-mt-md">
        <h5 class="text-subtitle1 text-bold q-my-none">1ml Node Rank</h5>
        <div v-for='stat in stats' class="q-gutter-sm">
          <div class="row items-center">
            <div class="col-9">{{ stat.label }}</div>
            <div class="col-3 text-subtitle1 text-bold">
              {{ (this.ranks && this.ranks[stat.key]) ?? '-' }}
            </div>
          </div>
        </div>
      </div>
    </q-card>
  `,
  methods: {
    get1MLStats: function () {
      return LNbits.api
        .request('GET', '/node/api/v1/rank?usr=' + this.user.id, {})
        .then(response => {
          this.ranks = response.data
        })
    }
  },
  created: function () {
    if (window.user) {
      this.user = LNbits.map.user(window.user)
    }
    this.get1MLStats()
  }
})

Vue.component('lnbits-channel-stats', {
  props: ['stats'],
  data: function () {
    return {
      states: [
        {label: 'Active', value: 'active', color: 'green'},
        {label: 'Pending', value: 'pending', color: 'orange'},
        {label: 'Inactive', value: 'inactive', color: 'grey'},
        {label: 'Closed', value: 'closed', color: 'red'}
      ]
    }
  },
  template: `
      <q-card>
          <div class="column q-ma-md">
            <h5 class="text-subtitle1 text-bold q-my-none">Channels</h5>
            <div v-for="state in states" class="q-gutter-sm">
              <div class="row">
                <div class="col-9">
                  <q-badge rounded size="md" :color="state.color">{{ state.label }}</q-badge>
                </div>
                <div class="col-3 text-subtitle1 text-bold">
                  {{ stats.counts[state.value] ?? "-" }}
                </div>
              </div>
            </div>
          </div>
        </q-card>
  `,
  created: function () {
    if (window.user) {
      this.user = LNbits.map.user(window.user)
    }
  }
})
