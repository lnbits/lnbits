function shortenNodeId(nodeId) {
  return nodeId
    ? nodeId.substring(0, 5) + '...' + nodeId.substring(nodeId.length - 5)
    : '...'
}

Vue.component('lnbits-node-ranks', {
  props: ['ranks'],
  data: function () {
    return {
      user: {},
      stats: [
        {label: 'Capacity', key: 'capacity'},
        {label: 'Channels', key: 'channelcount'},
        {label: 'Age', key: 'age'},
        {label: 'Growth', key: 'growth'},
        {label: 'Availability', key: 'availability'}
      ]
    }
  },
  template: `
    <q-card class='q-my-none'>
    <div class='column q-ma-md'>
      <h5 class='text-subtitle1 text-bold q-my-none'>1ml Node Rank</h5>
      <div v-for='stat in stats' class='q-gutter-sm'>
        <div class='row items-center'>
          <div class='col-9'>{{ stat.label }}</div>
          <div class='col-3 text-subtitle1 text-bold'>
            {{ (ranks && ranks[stat.key]) ?? '-' }}
          </div>
        </div>
      </div>
    </div>
    </q-card>
  `
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
    <div class='column q-ma-md'>
      <h5 class='text-subtitle1 text-bold q-my-none'>Channels</h5>
      <div v-for='state in states' class='q-gutter-sm'>
        <div class='row'>
          <div class='col-9'>
            <q-badge rounded size='md' :color='state.color'>{{ state.label }}</q-badge>
          </div>
          <div class='col-3 text-subtitle1 text-bold'>
            {{ (stats?.counts && stats.counts[state.value]) ?? "-" }}
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

Vue.component('lnbits-stat', {
  props: ['title', 'amount', 'msat', 'btc'],
  computed: {
    value: function () {
      return (
        this.amount ??
        (this.btc
          ? LNbits.utils.formatSat(this.btc)
          : LNbits.utils.formatMsat(this.msat))
      )
    }
  },
  template: `
    <q-card>
    <q-card-section>
      <div class='text-overline text-primary'>
        {{ title }}
      </div>
      <div>
        <span class='text-h4 text-bold q-my-none'>{{ value }}</span>
        <span class='text-h5' v-if='msat != undefined'>sats</span>
        <span class='text-h5' v-if='btc != undefined'>BTC</span>
      </div>
    </q-card-section>
    </q-card>
  `
})

Vue.component('lnbits-node-qrcode', {
  props: ['info'],
  mixins: [windowMixin],
  template: `
    <q-card class="my-card">
      <q-card-section>
        <div class="text-h6">
          <div style="text-align: center">
            <qrcode
              :value="info.addresses[0]"
              :options="{width: 250}"
              v-if='info.addresses[0]'
              class="rounded-borders"
            ></qrcode>
            <div v-else class='text-subtitle1'>
              No addresses available
            </div>
          </div>
        </div>
      </q-card-section>
      <q-card-actions vertical>
        <q-btn
          dense
          unelevated
          size="md"
          @click="copyText(info.id)"
        >Public Key<q-tooltip> Click to copy </q-tooltip>
        </q-btn>
      </q-card-actions>
    </q-card>
  `
})

Vue.component('lnbits-node-info', {
  props: ['info'],
  data() {
    return {
      showDialog: false
    }
  },
  mixins: [windowMixin],
  methods: {
    shortenNodeId
  },
  template: `
    <div class='row items-baseline q-gutter-x-sm'>
    <div class='text-h4 text-bold'>{{ this.info.alias }}</div>
    <div class='row items-center q-gutter-sm'>
      <div class='text-subtitle1 text-light'>{{ this.info.backend_name }}</div>
      <q-badge
        :style='\`background-color: #\${this.info.color}\`'
        class='text-bold'
      >
        #{{ this.info.color }}
      </q-badge>
      <div class='text-bold'>{{ shortenNodeId(this.info.id) }}</div>
      <q-btn
        size='xs'
        flat
        dense
        icon='content_paste'
        @click='copyText(info.id)'
      ></q-btn>
      <q-btn
        size='xs'
        flat
        dense
        icon='qr_code'
        @click='showDialog = true'
      ></q-btn>
    </div>
      <q-dialog v-model="showDialog">
        <lnbits-node-qrcode :info='info'></lnbits-node-qrcode>
      </q-dialog>
    </div>
  `
})

Vue.component('lnbits-stat', {
  props: ['title', 'amount', 'msat', 'btc'],
  computed: {
    value: function () {
      return (
        this.amount ??
        (this.btc
          ? LNbits.utils.formatSat(this.btc)
          : LNbits.utils.formatMsat(this.msat))
      )
    }
  },
  template: `
        <q-card>
        <q-card-section>
          <div class='text-overline text-primary'>
            {{ title }}
          </div>
          <div>
            <span class='text-h4 text-bold q-my-none'>{{ value }}</span>
            <span class='text-h5' v-if='msat != undefined'>sats</span>
            <span class='text-h5' v-if='btc != undefined'>BTC</span>
          </div>
        </q-card-section>
        </q-card>
      `
})

Vue.component('lnbits-channel-balance', {
  props: ['balance', 'color'],
  methods: {
    formatMsat: function (msat) {
      return LNbits.utils.formatMsat(msat)
    }
  },
  template: `
    <div>
        <div class="row items-center justify-between">
          <span class="text-weight-thin">
            Local: {{ formatMsat(balance.local_msat) }}
            sats
          </span>
          <span class="text-weight-thin">
            Remote: {{ formatMsat(balance.remote_msat) }}
            sats
          </span>
        </div>

        <q-linear-progress
          rounded
          size="25px"
          :value="balance.local_msat / balance.total_msat"
          :color="color"
          :style="\`color: #\${this.color}\`"
        >
          <div class="absolute-full flex flex-center">
            <q-badge
              color="white"
              text-color="accent"
              :label="formatMsat(balance.total_msat) + ' sats'"
            >
              {{ balance.alias }}
            </q-badge>
          </div>
       </q-linear-progress>
    </div>
  `
})

Vue.component('lnbits-date', {
  props: ['ts'],
  computed: {
    date: function () {
      return Quasar.utils.date.formatDate(
        new Date(this.ts * 1000),
        'YYYY-MM-DD HH:mm'
      )
    },
    dateFrom: function () {
      return moment(this.date).fromNow()
    }
  },
  template: `
    <div>
      <q-tooltip>{{ this.date }}</q-tooltip>
      {{ this.dateFrom }}
    </div>
  `
})
