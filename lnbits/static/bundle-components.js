window.app.component('lnbits-funding-sources', {
  mixins: [window.windowMixin],
  props: ['form-data', 'allowed-funding-sources'],
  methods: {
    getFundingSourceLabel(item) {
      const fundingSource = this.rawFundingSources.find(
        fundingSource => fundingSource[0] === item
      )
      return fundingSource ? fundingSource[1] : item
    }
  },
  computed: {
    fundingSources() {
      let tmp = []
      for (const [key, _, obj] of this.rawFundingSources) {
        const tmpObj = {}
        if (obj !== null) {
          for (let [k, v] of Object.entries(obj)) {
            tmpObj[k] = {label: v, value: null}
          }
        }
        tmp.push([key, tmpObj])
      }
      return new Map(tmp)
    },
    sortedAllowedFundingSources() {
      return this.allowedFundingSources.sort()
    }
  },
  data() {
    return {
      rawFundingSources: [
        ['VoidWallet', 'Void Wallet', null],
        [
          'FakeWallet',
          'Fake Wallet',
          {
            fake_wallet_secret: 'Secret'
          }
        ],
        [
          'CoreLightningWallet',
          'Core Lightning',
          {
            corelightning_rpc: 'Endpoint',
            corelightning_pay_command: 'Custom Pay Command'
          }
        ],
        [
          'CoreLightningRestWallet',
          'Core Lightning Rest',
          {
            corelightning_rest_url: 'Endpoint',
            corelightning_rest_cert: 'Certificate',
            corelightning_rest_macaroon: 'Macaroon'
          }
        ],
        [
          'LndRestWallet',
          'Lightning Network Daemon (LND Rest)',
          {
            lnd_rest_endpoint: 'Endpoint',
            lnd_rest_cert: 'Certificate',
            lnd_rest_macaroon: 'Macaroon',
            lnd_rest_macaroon_encrypted: 'Encrypted Macaroon',
            lnd_rest_route_hints: 'Enable Route Hints'
          }
        ],
        [
          'LndWallet',
          'Lightning Network Daemon (LND)',
          {
            lnd_grpc_endpoint: 'Endpoint',
            lnd_grpc_cert: 'Certificate',
            lnd_grpc_port: 'Port',
            lnd_grpc_admin_macaroon: 'Admin Macaroon',
            lnd_grpc_macaroon_encrypted: 'Encrypted Macaroon'
          }
        ],
        [
          'LnTipsWallet',
          'LN.Tips',
          {
            lntips_api_endpoint: 'Endpoint',
            lntips_api_key: 'API Key'
          }
        ],
        [
          'LNPayWallet',
          'LN Pay',
          {
            lnpay_api_endpoint: 'Endpoint',
            lnpay_api_key: 'API Key',
            lnpay_wallet_key: 'Wallet Key'
          }
        ],
        [
          'EclairWallet',
          'Eclair (ACINQ)',
          {
            eclair_url: 'URL',
            eclair_pass: 'Password'
          }
        ],
        [
          'LNbitsWallet',
          'LNbits',
          {
            lnbits_endpoint: 'Endpoint',
            lnbits_key: 'Admin Key'
          }
        ],
        [
          'BlinkWallet',
          'Blink',
          {
            blink_api_endpoint: 'Endpoint',
            blink_ws_endpoint: 'WebSocket',
            blink_token: 'Key'
          }
        ],
        [
          'AlbyWallet',
          'Alby',
          {
            alby_api_endpoint: 'Endpoint',
            alby_access_token: 'Key'
          }
        ],
        [
          'BoltzWallet',
          'Boltz',
          {
            boltz_client_endpoint: 'Endpoint',
            boltz_client_macaroon: 'Admin Macaroon path or hex',
            boltz_client_cert: 'Certificate path or hex',
            boltz_client_wallet: 'Wallet Name'
          }
        ],
        [
          'ZBDWallet',
          'ZBD',
          {
            zbd_api_endpoint: 'Endpoint',
            zbd_api_key: 'Key'
          }
        ],
        [
          'PhoenixdWallet',
          'Phoenixd',
          {
            phoenixd_api_endpoint: 'Endpoint',
            phoenixd_api_password: 'Key'
          }
        ],
        [
          'OpenNodeWallet',
          'OpenNode',
          {
            opennode_api_endpoint: 'Endpoint',
            opennode_key: 'Key'
          }
        ],
        [
          'ClicheWallet',
          'Cliche (NBD)',
          {
            cliche_endpoint: 'Endpoint'
          }
        ],
        [
          'SparkWallet',
          'Spark',
          {
            spark_url: 'Endpoint',
            spark_token: 'Token'
          }
        ],
        [
          'NWCWallet',
          'Nostr Wallet Connect',
          {
            nwc_pairing_url: 'Pairing URL'
          }
        ],
        [
          'BreezSdkWallet',
          'Breez SDK',
          {
            breez_api_key: 'Breez API Key',
            breez_greenlight_seed: 'Greenlight Seed',
            breez_greenlight_device_key: 'Greenlight Device Key',
            breez_greenlight_device_cert: 'Greenlight Device Cert',
            breez_greenlight_invite_code: 'Greenlight Invite Code'
          }
        ]
      ]
    }
  },
  template: `
    <div class="funding-sources">
        <h6 class="q-mt-xl q-mb-md">Funding Sources</h6>
        <div class="row">
          <div class="col-12">
            <p>Active Funding<small> (Requires server restart)</small></p>
            <q-select
              filled
              v-model="formData.lnbits_backend_wallet_class"
              hint="Select the active funding wallet"
              :options="sortedAllowedFundingSources"
              :option-label="(item) => getFundingSourceLabel(item)"
            ></q-select>
          </div>
        </div>
        <q-list
          class="q-mt-md"
          v-for="(fund, idx) in allowedFundingSources"
          :key="idx"
        >
          <div v-if="fundingSources.get(fund) && fund === formData.lnbits_backend_wallet_class">
            <div class="row"
              v-for="([key, prop], i) in Object.entries(fundingSources.get(fund))"
              :key="i"
            >
              <div class="col-12">
                <q-input
                  filled
                  type="text"
                  class="q-mt-sm"
                  v-model="formData[key]"
                  :label="prop.label"
                  :hint="prop.hint"
                ></q-input>
              </div>
            </div>
          </div>
        </q-list>
    </div>
  `
})

window.app.component('lnbits-extension-settings-form', {
  name: 'lnbits-extension-settings-form',
  props: ['options', 'adminkey', 'endpoint'],
  methods: {
    async updateSettings() {
      if (!this.settings) {
        return this.$q.notify({
          message: 'No settings to update',
          type: 'negative'
        })
      }
      try {
        const {data} = await LNbits.api.request(
          'PUT',
          this.endpoint,
          this.adminkey,
          this.settings
        )
        this.settings = data
      } catch (error) {
        LNbits.utils.notifyApiError(error)
      }
    },
    getSettings: async function () {
      try {
        const {data} = await LNbits.api.request(
          'GET',
          this.endpoint,
          this.adminkey
        )
        this.settings = data
      } catch (error) {
        LNbits.utils.notifyApiError(error)
      }
    },
    resetSettings: async function () {
      LNbits.utils
        .confirmDialog('Are you sure you want to reset the settings?')
        .onOk(async () => {
          try {
            await LNbits.api.request('DELETE', this.endpoint, this.adminkey)
            await this.getSettings()
          } catch (error) {
            LNbits.utils.notifyApiError(error)
          }
        })
    }
  },
  created: async function () {
    await this.getSettings()
  },
  template: `
    <q-form v-if="settings" @submit="updateSettings" class="q-gutter-md">
      <lnbits-dynamic-fields :options="options" v-model="settings"></lnbits-dynamic-fields>
      <div class="row q-mt-lg">
        <q-btn v-close-popup unelevated color="primary" type="submit">Update</q-btn>
        <q-btn v-close-popup unelevated color="danger" @click="resetSettings" >Reset</q-btn>
        <slot name="actions"></slot>
      </div>
    </q-form>
  `,
  data: function () {
    return {
      settings: undefined
    }
  }
})

window.app.component('lnbits-extension-settings-btn-dialog', {
  name: 'lnbits-extension-settings-btn-dialog',
  props: ['options', 'adminkey', 'endpoint'],
  template: `
    <q-btn v-if="options" unelevated @click="show = true" color="primary" icon="settings" class="float-right">
        <q-dialog v-model="show" position="top">
          <q-card class="q-pa-lg q-pt-xl lnbits__dialog-card">
            <lnbits-extension-settings-form :options="options" :adminkey="adminkey" :endpoint="endpoint">
                <template v-slot:actions>
                    <q-btn v-close-popup flat color="grey" class="q-ml-auto">Close</q-btn>
                </template>
            </lnbits-extension-settings-form>
          </q-card>
        </q-dialog>
    </q-btn>
  `,
  data: function () {
    return {
      show: false
    }
  }
})

window.app.component('lnbits-extension-rating', {
  name: 'lnbits-extension-rating',
  props: ['rating'],
  template: `
    <div style="margin-bottom: 3px">
        <q-rating
          v-model="rating"
          size="1.5em"
          :max="5"
          color="primary"
          ><q-tooltip>
            <span v-text="$t('extension_rating_soon')"></span> </q-tooltip
        ></q-rating>
    </div>
  `
})

window.app.component('payment-list', {
  name: 'payment-list',
  props: ['update', 'wallet', 'mobileSimple', 'lazy'],
  mixins: [window.windowMixin],
  data: function () {
    return {
      denomination: LNBITS_DENOMINATION,
      payments: [],
      paymentsTable: {
        columns: [
          {
            name: 'time',
            align: 'left',
            label: this.$t('memo') + '/' + this.$t('date'),
            field: 'date',
            sortable: true
          },
          {
            name: 'amount',
            align: 'right',
            label: this.$t('amount') + ' (' + LNBITS_DENOMINATION + ')',
            field: 'sat',
            sortable: true
          }
        ],
        pagination: {
          rowsPerPage: 10,
          page: 1,
          sortBy: 'time',
          descending: true,
          rowsNumber: 10
        },
        search: null,
        loading: false
      },
      exportTagName: '',
      exportPaymentTagList: [],
      paymentsCSV: {
        columns: [
          {
            name: 'pending',
            align: 'left',
            label: 'Pending',
            field: 'pending'
          },
          {
            name: 'memo',
            align: 'left',
            label: this.$t('memo'),
            field: 'memo'
          },
          {
            name: 'time',
            align: 'left',
            label: this.$t('date'),
            field: 'date',
            sortable: true
          },
          {
            name: 'amount',
            align: 'right',
            label: this.$t('amount') + ' (' + LNBITS_DENOMINATION + ')',
            field: 'sat',
            sortable: true
          },
          {
            name: 'fee',
            align: 'right',
            label: this.$t('fee') + ' (m' + LNBITS_DENOMINATION + ')',
            field: 'fee'
          },
          {
            name: 'tag',
            align: 'right',
            label: this.$t('tag'),
            field: 'tag'
          },
          {
            name: 'payment_hash',
            align: 'right',
            label: this.$t('payment_hash'),
            field: 'payment_hash'
          },
          {
            name: 'payment_proof',
            align: 'right',
            label: this.$t('payment_proof'),
            field: 'payment_proof'
          },
          {
            name: 'webhook',
            align: 'right',
            label: this.$t('webhook'),
            field: 'webhook'
          },
          {
            name: 'fiat_currency',
            align: 'right',
            label: 'Fiat Currency',
            field: row => row.extra.wallet_fiat_currency
          },
          {
            name: 'fiat_amount',
            align: 'right',
            label: 'Fiat Amount',
            field: row => row.extra.wallet_fiat_amount
          }
        ],
        filter: null,
        loading: false
      }
    }
  },
  computed: {
    filteredPayments: function () {
      var q = this.paymentsTable.search
      if (!q || q === '') return this.payments

      return LNbits.utils.search(this.payments, q)
    },
    paymentsOmitter() {
      if (this.$q.screen.lt.md && this.mobileSimple) {
        return this.payments.length > 0 ? [this.payments[0]] : []
      }
      return this.payments
    },
    pendingPaymentsExist: function () {
      return this.payments.findIndex(payment => payment.pending) !== -1
    }
  },
  methods: {
    fetchPayments: function (props) {
      const params = LNbits.utils.prepareFilterQuery(this.paymentsTable, props)
      return LNbits.api
        .getPayments(this.wallet, params)
        .then(response => {
          this.paymentsTable.loading = false
          this.paymentsTable.pagination.rowsNumber = response.data.total
          this.payments = response.data.data.map(obj => {
            return LNbits.map.payment(obj)
          })
        })
        .catch(err => {
          this.paymentsTable.loading = false
          LNbits.utils.notifyApiError(err)
        })
    },
    paymentTableRowKey: function (row) {
      return row.payment_hash + row.amount
    },
    exportCSV(detailed = false) {
      // status is important for export but it is not in paymentsTable
      // because it is manually added with payment detail link and icons
      // and would cause duplication in the list
      const pagination = this.paymentsTable.pagination
      const query = {
        sortby: pagination.sortBy ?? 'time',
        direction: pagination.descending ? 'desc' : 'asc'
      }
      const params = new URLSearchParams(query)
      LNbits.api.getPayments(this.wallet, params).then(response => {
        let payments = response.data.data.map(LNbits.map.payment)
        let columns = this.paymentsCSV.columns

        if (detailed) {
          if (this.exportPaymentTagList.length) {
            payments = payments.filter(p =>
              this.exportPaymentTagList.includes(p.tag)
            )
          }
          const extraColumns = Object.keys(
            payments.reduce((e, p) => ({...e, ...p.details}), {})
          ).map(col => ({
            name: col,
            align: 'right',
            label:
              col.charAt(0).toUpperCase() +
              col.slice(1).replace(/([A-Z])/g, ' $1'),
            field: row => row.details[col],
            format: data =>
              typeof data === 'object' ? JSON.stringify(data) : data
          }))
          columns = this.paymentsCSV.columns.concat(extraColumns)
        }

        LNbits.utils.exportCSV(
          columns,
          payments,
          this.wallet.name + '-payments'
        )
      })
    },
    addFilterTag: function () {
      if (!this.exportTagName) return
      const value = this.exportTagName.trim()
      this.exportPaymentTagList = this.exportPaymentTagList.filter(
        v => v !== value
      )
      this.exportPaymentTagList.push(value)
      this.exportTagName = ''
    },
    removeExportTag: function (value) {
      this.exportPaymentTagList = this.exportPaymentTagList.filter(
        v => v !== value
      )
    },
    formatCurrency: function (amount, currency) {
      try {
        return LNbits.utils.formatCurrency(amount, currency)
      } catch (e) {
        console.error(e)
        return `${amount} ???`
      }
    }
  },
  watch: {
    lazy: function (newVal) {
      if (newVal === true) this.fetchPayments()
    },
    update: function () {
      this.fetchPayments()
    }
  },
  created: function () {
    if (this.lazy === undefined) this.fetchPayments()
  },
  template: `
    <q-card
      :style="$q.screen.lt.md ? {
        background: $q.screen.lt.md ? 'none !important': ''
        , boxShadow: $q.screen.lt.md ? 'none !important': ''
        , marginTop: $q.screen.lt.md ? '0px !important': ''
      } : ''"
    >
      <q-card-section>
        <div class="row items-center no-wrap q-mb-sm">
          <div class="col">
            <h5
              class="text-subtitle1 q-my-none"
              :v-text="$t('transactions')"
            ></h5>
          </div>
          <div class="gt-sm col-auto">
            <q-btn-dropdown
              outline
              persistent
              class="q-mr-sm"
              color="grey"
              :label="$t('export_csv')"
              split
              @click="exportCSV(false)"
            >
              <q-list>
                <q-item>
                  <q-item-section>
                    <q-input
                    @keydown.enter="addFilterTag"
                      filled
                      dense
                      v-model="exportTagName"
                      type="text"
                      label="Payment Tags"
                      class="q-pa-sm"
                    >
                      <q-btn
                        @click="addFilterTag"
                        dense
                        flat
                        icon="add"
                      ></q-btn>
                    </q-input>
                  </q-item-section>
                </q-item>
                <q-item v-if="exportPaymentTagList.length">
                  <q-item-section>
                    <div>
                      <q-chip
                        v-for="tag in exportPaymentTagList"
                        :key="tag"
                        removable
                        @remove="removeExportTag(tag)"
                        color="primary"
                        text-color="white"
                        :label="tag"
                      ></q-chip>
                    </div>
                  </q-item-section>
                </q-item>

                <q-item>
                  <q-item-section>
                    <q-btn v-close-popup outline color="grey" @click="exportCSV(true)" label="Export to CSV with details" ></q-btn>
                  </q-item-section>
                </q-item>
              </q-list>
            </q-btn-dropdown>
            <payment-chart :wallet="wallet" />
          </div>
        </div>
        <q-input
          :style="$q.screen.lt.md ? {
          display: mobileSimple ? 'none !important': ''
        } : ''"
          filled
          dense
          clearable
          v-model="paymentsTable.search"
          debounce="300"
          :placeholder="$t('search_by_tag_memo_amount')"
          class="q-mb-md"
        >
        </q-input>
        <q-table
          dense
          flat
          :rows="paymentsOmitter"
          :row-key="paymentTableRowKey"
          :columns="paymentsTable.columns"
          :pagination.sync="paymentsTable.pagination"
          :no-data-label="$t('no_transactions')"
          :filter="paymentsTable.search"
          :loading="paymentsTable.loading"
          :hide-header="mobileSimple"
          :hide-bottom="mobileSimple"
          @request="fetchPayments"
        >
          <template v-slot:header="props">
            <q-tr :props="props">
              <q-th auto-width></q-th>
              <q-th
                v-for="col in props.cols"
                :key="col.name"
                :props="props"
                v-text="col.label"
              ></q-th>
            </q-tr>
          </template>
          <template v-slot:body="props">
            <q-tr :props="props">
              <q-td auto-width class="text-center">
                <q-icon
                  v-if="props.row.isPaid"
                  size="14px"
                  :name="props.row.isOut ? 'call_made' : 'call_received'"
                  :color="props.row.isOut ? 'pink' : 'green'"
                  @click="props.expand = !props.expand"
                ></q-icon>
                <q-icon
                  v-else-if="props.row.isFailed"
                  name="warning"
                  color="yellow"
                  @click="props.expand = !props.expand"
                >
                  <q-tooltip
                    ><span>failed</span
                  ></q-tooltip>
                </q-icon>
                <q-icon
                  v-else
                  name="settings_ethernet"
                  color="grey"
                  @click="props.expand = !props.expand"
                >
                  <q-tooltip
                    ><span v-text="$t('pending')"></span
                  ></q-tooltip>
                </q-icon>
              </q-td>
              <q-td
                key="time"
                :props="props"
                style="white-space: normal; word-break: break-all"
              >
                <q-badge
                  v-if="props.row.tag"
                  color="yellow"
                  text-color="black"
                >
                  <a
                    v-text="'#'+props.row.tag"
                    class="inherit"
                    :href="['/', props.row.tag].join('')"
                  ></a>
                </q-badge>
                <span v-text="props.row.memo"></span>
                <br />

                <i>
                  <span v-text="props.row.dateFrom"></span>
                  <q-tooltip
                    ><span v-text="props.row.date"></span
                  ></q-tooltip>
                </i>
              </q-td>
              <q-td
                auto-width
                key="amount"
                v-if="denomination != 'sats'"
                :props="props"
                class="col1"
                v-text="parseFloat(String(props.row.fsat).replaceAll(',', '')) / 100"
              >
              </q-td>
              <q-td class="col2" auto-width key="amount" v-else :props="props">
                <span v-text="props.row.fsat"></span>
                <br />
                <i v-if="props.row.extra.wallet_fiat_currency">
                  <span
                    v-text="formatCurrency(props.row.extra.wallet_fiat_amount, props.row.extra.wallet_fiat_currency)"
                  ></span>
                  <br />
                </i>
                <i v-if="props.row.extra.fiat_currency">
                  <span
                    v-text="formatCurrency(props.row.extra.fiat_amount, props.row.extra.fiat_currency)"
                  ></span>
                </i>
              </q-td>

                <q-dialog v-model="props.expand" :props="props" position="top">
                  <q-card class="q-pa-lg q-pt-xl lnbits__dialog-card">
                    <div class="text-center q-mb-lg">
                      <div v-if="props.row.isIn && props.row.isPending">
                        <q-icon name="settings_ethernet" color="grey"></q-icon>
                        <span v-text="$t('invoice_waiting')"></span>
                        <lnbits-payment-details
                          :payment="props.row"
                        ></lnbits-payment-details>
                        <div
                          v-if="props.row.bolt11"
                          class="text-center q-mb-lg"
                        >
                          <a :href="'lightning:' + props.row.bolt11">
                            <q-responsive :ratio="1" class="q-mx-xl">
                              <lnbits-qrcode
                                :value="'lightning:' + props.row.bolt11.toUpperCase()"
                              ></lnbits-qrcode>
                            </q-responsive>
                          </a>
                        </div>
                        <div class="row q-mt-lg">
                          <q-btn
                            outline
                            color="grey"
                            @click="copyText(props.row.bolt11)"
                            :label="$t('copy_invoice')"
                          ></q-btn>
                          <q-btn
                            v-close-popup
                            flat
                            color="grey"
                            class="q-ml-auto"
                            :label="$t('close')"
                          ></q-btn>
                        </div>
                      </div>
                      <div v-else-if="props.row.isOut && props.row.isPending">
                        <q-icon name="settings_ethernet" color="grey"></q-icon>
                        <span v-text="$t('outgoing_payment_pending')"></span>
                        <lnbits-payment-details
                          :payment="props.row"
                        ></lnbits-payment-details>
                      </div>
                      <div v-else-if="props.row.isPaid && props.row.isIn">
                        <q-icon
                          size="18px"
                          :name="'call_received'"
                          :color="'green'"
                        ></q-icon>
                        <span v-text="$t('payment_received')"></span>
                        <lnbits-payment-details
                          :payment="props.row"
                        ></lnbits-payment-details>
                      </div>
                      <div v-else-if="props.row.isPaid && props.row.isOut">
                        <q-icon
                          size="18px"
                          :name="'call_made'"
                          :color="'pink'"
                        ></q-icon>
                        <span v-text="$t('payment_sent')"></span>
                        <lnbits-payment-details
                          :payment="props.row"
                        ></lnbits-payment-details>
                      </div>
                      <div v-else-if="props.row.isFailed">
                        <q-icon name="warning" color="yellow"></q-icon>
                        <span>Payment failed</span>
                        <lnbits-payment-details
                          :payment="props.row"
                        ></lnbits-payment-details>
                      </div>
                    </div>
                  </q-card>
                </q-dialog>
            </q-tr>
          </template>
        </q-table>
      </q-card-section>
    </q-card>
    `
})

function generateChart(canvas, rawData) {
  const data = rawData.reduce(
    (previous, current) => {
      previous.labels.push(current.date)
      previous.income.push(current.income)
      previous.spending.push(current.spending)
      previous.cumulative.push(current.balance)
      return previous
    },
    {
      labels: [],
      income: [],
      spending: [],
      cumulative: []
    }
  )

  return new Chart(canvas.getContext('2d'), {
    type: 'bar',
    data: {
      labels: data.labels,
      datasets: [
        {
          data: data.cumulative,
          type: 'line',
          label: 'balance',
          backgroundColor: '#673ab7', // deep-purple
          borderColor: '#673ab7',
          borderWidth: 4,
          pointRadius: 3,
          fill: false
        },
        {
          data: data.income,
          type: 'bar',
          label: 'in',
          barPercentage: 0.75,
          backgroundColor: window.Color('rgb(76,175,80)').alpha(0.5).rgbString() // green
        },
        {
          data: data.spending,
          type: 'bar',
          label: 'out',
          barPercentage: 0.75,
          backgroundColor: window.Color('rgb(233,30,99)').alpha(0.5).rgbString() // pink
        }
      ]
    },
    options: {
      title: {
        text: 'Chart.js Combo Time Scale'
      },
      tooltips: {
        mode: 'index',
        intersect: false
      },
      scales: {
        xAxes: [
          {
            type: 'time',
            display: true,
            //offset: true,
            time: {
              minUnit: 'hour',
              stepSize: 3
            }
          }
        ]
      },
      // performance tweaks
      animation: {
        duration: 0
      },
      elements: {
        line: {
          tension: 0
        }
      }
    }
  })
}

window.app.component('payment-chart', {
  name: 'payment-chart',
  props: ['wallet'],
  mixins: [window.windowMixin],
  data: function () {
    return {
      paymentsChart: {
        show: false,
        group: {
          value: 'hour',
          label: 'Hour'
        },
        groupOptions: [
          {value: 'hour', label: 'Hour'},
          {value: 'day', label: 'Day'},
          {value: 'week', label: 'Week'},
          {value: 'month', label: 'Month'},
          {value: 'year', label: 'Year'}
        ],
        instance: null
      }
    }
  },
  methods: {
    showChart: function () {
      this.paymentsChart.show = true
      LNbits.api
        .request(
          'GET',
          '/api/v1/payments/history?group=' + this.paymentsChart.group.value,
          this.wallet.adminkey
        )
        .then(response => {
          this.$nextTick(() => {
            if (this.paymentsChart.instance) {
              this.paymentsChart.instance.destroy()
            }
            this.paymentsChart.instance = generateChart(
              this.$refs.canvas,
              response.data
            )
          })
        })
        .catch(err => {
          LNbits.utils.notifyApiError(err)
          this.paymentsChart.show = false
        })
    }
  },
  template: `
    <span id="payment-chart">
        <q-btn dense flat round icon="show_chart" color="grey" @click="showChart" >
            <q-tooltip>
                <span v-text="$t('chart_tooltip')"></span>
            </q-tooltip>
        </q-btn>

        <q-dialog v-model="paymentsChart.show" position="top">
            <q-card class="q-pa-sm" style="width: 800px; max-width: unset">
                <q-card-section>
                    <div class="row q-gutter-sm justify-between">
                        <div class="text-h6">Payments Chart</div>
                        <q-select label="Group" filled dense v-model="paymentsChart.group"
                        style="min-width: 120px"
                        :options="paymentsChart.groupOptions"
                        >
                        </q-select>
                    </div>
                    <canvas ref="canvas" width="600" height="400"></canvas>
                </q-card-section>
            </q-card>
        </q-dialog>
    </span>
    `
})

window.app.component(QrcodeVue)

window.app.component('lnbits-fsat', {
  props: {
    amount: {
      type: Number,
      default: 0
    }
  },
  template: '<span>{{ fsat }}</span>',
  computed: {
    fsat: function () {
      return LNbits.utils.formatSat(this.amount)
    }
  }
})

window.app.component('lnbits-wallet-list', {
  props: ['balance'],
  data: function () {
    return {
      user: null,
      activeWallet: null,
      balance: 0,
      showForm: false,
      walletName: '',
      LNBITS_DENOMINATION: LNBITS_DENOMINATION
    }
  },
  template: `
    <q-list v-if="user && user.wallets.length" dense class="lnbits-drawer__q-list">
      <q-item-label header v-text="$t('wallets')"></q-item-label>
      <q-item v-for="wallet in wallets" :key="wallet.id"
        clickable
        :active="activeWallet && activeWallet.id === wallet.id"
        tag="a" :href="wallet.url">
        <q-item-section side>
          <q-avatar size="md"
            :color="(activeWallet && activeWallet.id === wallet.id)
              ? (($q.dark.isActive) ? 'primary' : 'primary')
              : 'grey-5'">
            <q-icon name="flash_on" :size="($q.dark.isActive) ? '21px' : '20px'"
              :color="($q.dark.isActive) ? 'blue-grey-10' : 'grey-3'"></q-icon>
          </q-avatar>
        </q-item-section>
        <q-item-section>
          <q-item-label lines="1">{{ wallet.name }}</q-item-label>
          <q-item-label v-if="LNBITS_DENOMINATION != 'sats'" caption>{{ parseFloat(String(wallet.live_fsat).replaceAll(",", "")) / 100  }} {{ LNBITS_DENOMINATION }}</q-item-label>
          <q-item-label v-else caption>{{ wallet.live_fsat }} {{ LNBITS_DENOMINATION }}</q-item-label>
        </q-item-section>
        <q-item-section side v-show="activeWallet && activeWallet.id === wallet.id">
          <q-icon name="chevron_right" color="grey-5" size="md"></q-icon>
        </q-item-section>
      </q-item>
      <q-item clickable @click="showForm = !showForm">
        <q-item-section side>
          <q-icon :name="(showForm) ? 'remove' : 'add'" color="grey-5" size="md"></q-icon>
        </q-item-section>
        <q-item-section>
          <q-item-label lines="1" class="text-caption" v-text="$t('add_wallet')"></q-item-label>
        </q-item-section>
      </q-item>
      <q-item v-if="showForm">
        <q-item-section>
          <q-form @submit="createWallet">
            <q-input filled dense v-model="walletName" label="Name wallet *">
              <template v-slot:append>
                <q-btn round dense flat icon="send" size="sm" @click="createWallet" :disable="walletName === ''"></q-btn>
              </template>
            </q-input>
          </q-form>
        </q-item-section>
      </q-item>
    </q-list>
  `,
  computed: {
    wallets: function () {
      var bal = this.balance
      return this.user.wallets.map(function (obj) {
        obj.live_fsat =
          bal.length && bal[0] === obj.id
            ? LNbits.utils.formatSat(bal[1])
            : obj.fsat
        return obj
      })
    }
  },
  methods: {
    createWallet: function () {
      LNbits.api.createWallet(this.user.wallets[0], this.walletName)
    }
  },
  created: function () {
    if (window.user) {
      this.user = LNbits.map.user(window.user)
    }
    if (window.wallet) {
      this.activeWallet = LNbits.map.wallet(window.wallet)
    }
    document.addEventListener('updateWalletBalance', this.updateWalletBalance)
  }
})

window.app.component('lnbits-extension-list', {
  data: function () {
    return {
      extensions: [],
      user: null
    }
  },
  template: `
    <q-list v-if="user && userExtensions.length > 0" dense class="lnbits-drawer__q-list">
      <q-item-label header v-text="$t('extensions')"></q-item-label>
      <q-item v-for="extension in userExtensions" :key="extension.code"
        clickable
        :active="extension.isActive"
        tag="a" :href="extension.url">
        <q-item-section side>
          <q-avatar size="md">
            <q-img
              :src="extension.tile"
              style="max-width:20px"
            ></q-img>
          </q-avatar>
        </q-item-section>
        <q-item-section>
          <q-item-label lines="1">{{ extension.name }} </q-item-label>
        </q-item-section>
        <q-item-section side v-show="extension.isActive">
          <q-icon name="chevron_right" color="grey-5" size="md"></q-icon>
        </q-item-section>
      </q-item>
      <div class="lt-md q-mt-xl q-mb-xl"></div>
    </q-list>
  `,
  computed: {
    userExtensions: function () {
      if (!this.user) return []

      var path = window.location.pathname
      var userExtensions = this.user.extensions

      return this.extensions
        .filter(function (obj) {
          return userExtensions.indexOf(obj.code) !== -1
        })
        .map(function (obj) {
          obj.isActive = path.startsWith(obj.url)
          return obj
        })
    }
  },
  created: function () {
    if (window.extensions) {
      this.extensions = window.extensions
        .map(function (data) {
          return LNbits.map.extension(data)
        })
        .sort(function (a, b) {
          return a.name.localeCompare(b.name)
        })
    }

    if (window.user) {
      this.user = LNbits.map.user(window.user)
    }
  }
})

window.app.component('lnbits-manage', {
  props: ['showAdmin', 'showNode', 'showExtensions', 'showUsers'],
  methods: {
    isActive: function (path) {
      return window.location.pathname === path
    }
  },
  data: function () {
    return {
      extensions: [],
      user: null
    }
  },
  template: `
    <q-list v-if="user" dense class="lnbits-drawer__q-list">
      <q-item-label header v-text="$t('manage')"></q-item-label>
      <div v-if="user.admin">
        <q-item v-if='showAdmin' clickable tag="a" href="/admin" :active="isActive('/admin')">
          <q-item-section side>
            <q-icon name="admin_panel_settings" :color="isActive('/admin') ? 'primary' : 'grey-5'" size="md"></q-icon>
          </q-item-section>
          <q-item-section>
            <q-item-label lines="1" v-text="$t('server')"></q-item-label>
          </q-item-section>
        </q-item>
        <q-item v-if='showNode' clickable tag="a" href="/node" :active="isActive('/node')">
          <q-item-section side>
            <q-icon name="developer_board" :color="isActive('/node') ? 'primary' : 'grey-5'" size="md"></q-icon>
          </q-item-section>
          <q-item-section>
            <q-item-label lines="1" v-text="$t('node')"></q-item-label>
          </q-item-section>
        </q-item>
        <q-item v-if="showUsers" clickable tag="a" href="/users" :active="isActive('/users')">
          <q-item-section side>
            <q-icon name="groups" :color="isActive('/users') ? 'primary' : 'grey-5'" size="md"></q-icon>
          </q-item-section>
          <q-item-section>
            <q-item-label lines="1" v-text="$t('users')"></q-item-label>
          </q-item-section>
        </q-item>
      </div>
      <q-item v-if="showExtensions" clickable tag="a" href="/extensions" :active="isActive('/extensions')">
        <q-item-section side>
          <q-icon name="extension" :color="isActive('/extensions') ? 'primary' : 'grey-5'" size="md"></q-icon>
        </q-item-section>
        <q-item-section>
          <q-item-label lines="1" v-text="$t('extensions')"></q-item-label>
        </q-item-section>
      </q-item>
    </q-list>
  `,

  created: function () {
    if (window.user) {
      this.user = LNbits.map.user(window.user)
    }
  }
})

window.app.component('lnbits-payment-details', {
  props: ['payment'],
  mixins: [window.windowMixin],
  data: function () {
    return {
      LNBITS_DENOMINATION: LNBITS_DENOMINATION
    }
  },
  template: `
  <div class="q-py-md" style="text-align: left">

  <div v-if="payment.tag" class="row justify-center q-mb-md">
    <q-badge v-if="hasTag" color="yellow" text-color="black">
      #{{ payment.tag }}
    </q-badge>
  </div>

  <div class="row">
    <b v-text="$t('created')"></b>:
    {{ payment.date }} ({{ payment.dateFrom }})
  </div>

  <div class="row" v-if="hasExpiry">
   <b v-text="$t('expiry')"></b>:
   {{ payment.expirydate }} ({{ payment.expirydateFrom }})
  </div>

  <div class="row">
   <b v-text="$t('amount')"></b>:
    {{ (payment.amount / 1000).toFixed(3) }} {{LNBITS_DENOMINATION}}
  </div>

  <div class="row">
    <b v-text="$t('fee')"></b>:
    {{ (payment.fee / 1000).toFixed(3) }} {{LNBITS_DENOMINATION}}
  </div>

  <div class="text-wrap">
    <b style="white-space: nowrap;" v-text="$t('payment_hash')"></b>:&nbsp;{{ payment.payment_hash }}
        <q-icon name="content_copy" @click="copyText(payment.payment_hash)" size="1em" color="grey" class="q-mb-xs cursor-pointer" />
  </div>

  <div class="text-wrap">
    <b style="white-space: nowrap;" v-text="$t('memo')"></b>:&nbsp;{{ payment.memo }}
  </div>

  <div class="text-wrap" v-if="payment.webhook">
    <b style="white-space: nowrap;" v-text="$t('webhook')"></b>:&nbsp;{{ payment.webhook }}:&nbsp;<q-badge :color="webhookStatusColor" text-color="white">
      {{ webhookStatusText }}
    </q-badge>
  </div>

  <div class="text-wrap" v-if="hasPreimage">
    <b style="white-space: nowrap;" v-text="$t('payment_proof')"></b>:&nbsp;{{ payment.preimage }}
  </div>

  <div class="row" v-for="entry in extras">
    <q-badge v-if="hasTag" color="secondary" text-color="white">
      extra
    </q-badge>
    <b>{{ entry.key }}</b>:
    {{ entry.value }}
  </div>

  <div class="row" v-if="hasSuccessAction">
    <b>Success action</b>:
      <lnbits-lnurlpay-success-action
        :payment="payment"
        :success_action="payment.extra.success_action"
      ></lnbits-lnurlpay-success-action>
  </div>

</div>
  `,
  computed: {
    hasPreimage() {
      return (
        this.payment.preimage &&
        this.payment.preimage !==
          '0000000000000000000000000000000000000000000000000000000000000000'
      )
    },
    hasExpiry() {
      return !!this.payment.expiry
    },
    hasSuccessAction() {
      return (
        this.hasPreimage &&
        this.payment.extra &&
        this.payment.extra.success_action
      )
    },
    webhookStatusColor() {
      return this.payment.webhook_status >= 300 ||
        this.payment.webhook_status < 0
        ? 'red-10'
        : !this.payment.webhook_status
          ? 'cyan-7'
          : 'green-10'
    },
    webhookStatusText() {
      return this.payment.webhook_status
        ? this.payment.webhook_status
        : 'not sent yet'
    },
    hasTag() {
      return this.payment.extra && !!this.payment.extra.tag
    },
    extras() {
      if (!this.payment.extra) return []
      let extras = _.omit(this.payment.extra, ['tag', 'success_action'])
      return Object.keys(extras).map(key => ({key, value: extras[key]}))
    }
  }
})

window.app.component('lnbits-lnurlpay-success-action', {
  props: ['payment', 'success_action'],
  data() {
    return {
      decryptedValue: this.success_action.ciphertext
    }
  },
  template: `
    <div>
      <p class="q-mb-sm">{{ success_action.message || success_action.description }}</p>
      <code v-if="decryptedValue" class="text-h6 q-mt-sm q-mb-none">
        {{ decryptedValue }}
      </code>
      <p v-else-if="success_action.url" class="text-h6 q-mt-sm q-mb-none">
        <a target="_blank" style="color: inherit;" :href="success_action.url">{{ success_action.url }}</a>
      </p>
    </div>
  `,
  mounted: function () {
    if (this.success_action.tag !== 'aes') return null

    decryptLnurlPayAES(this.success_action, this.payment.preimage).then(
      value => {
        this.decryptedValue = value
      }
    )
  }
})

window.app.component('lnbits-qrcode', {
  mixins: [window.windowMixin],
  components: {
    QrcodeVue
  },
  props: ['value'],
  data() {
    return {
      logo: LNBITS_QR_LOGO
    }
  },
  template: `
  <div class="qrcode__wrapper">
    <qrcode-vue :value="value" size="350" class="rounded-borders"></qrcode-vue>
    <img class="qrcode__image" :src="logo" alt="..." />
  </div>
  `
})

window.app.component('lnbits-notifications-btn', {
  mixins: [window.windowMixin],
  props: ['pubkey'],
  data() {
    return {
      isSupported: false,
      isSubscribed: false,
      isPermissionGranted: false,
      isPermissionDenied: false
    }
  },
  template: `
    <q-btn
      v-if="g.user.wallets"
      :disabled="!this.isSupported"
      dense
      flat
      round
      @click="toggleNotifications()"
      :icon="this.isSubscribed ? 'notifications_active' : 'notifications_off'"
      size="sm"
      type="a"
    >
      <q-tooltip v-if="this.isSupported && !this.isSubscribed">Subscribe to notifications</q-tooltip>
      <q-tooltip v-if="this.isSupported && this.isSubscribed">Unsubscribe from notifications</q-tooltip>
      <q-tooltip v-if="this.isSupported && this.isPermissionDenied">
          Notifications are disabled,<br/>please enable or reset permissions
      </q-tooltip>
      <q-tooltip v-if="!this.isSupported">Notifications are not supported</q-tooltip>
    </q-btn>
  `,
  methods: {
    // converts base64 to Array buffer
    urlB64ToUint8Array(base64String) {
      const padding = '='.repeat((4 - (base64String.length % 4)) % 4)
      const base64 = (base64String + padding)
        .replace(/\-/g, '+')
        .replace(/_/g, '/')
      const rawData = atob(base64)
      const outputArray = new Uint8Array(rawData.length)

      for (let i = 0; i < rawData.length; ++i) {
        outputArray[i] = rawData.charCodeAt(i)
      }

      return outputArray
    },
    toggleNotifications() {
      this.isSubscribed ? this.unsubscribe() : this.subscribe()
    },
    saveUserSubscribed(user) {
      let subscribedUsers =
        JSON.parse(
          this.$q.localStorage.getItem('lnbits.webpush.subscribedUsers')
        ) || []
      if (!subscribedUsers.includes(user)) subscribedUsers.push(user)
      this.$q.localStorage.set(
        'lnbits.webpush.subscribedUsers',
        JSON.stringify(subscribedUsers)
      )
    },
    removeUserSubscribed(user) {
      let subscribedUsers =
        JSON.parse(
          this.$q.localStorage.getItem('lnbits.webpush.subscribedUsers')
        ) || []
      subscribedUsers = subscribedUsers.filter(arr => arr !== user)
      this.$q.localStorage.set(
        'lnbits.webpush.subscribedUsers',
        JSON.stringify(subscribedUsers)
      )
    },
    isUserSubscribed(user) {
      let subscribedUsers =
        JSON.parse(
          this.$q.localStorage.getItem('lnbits.webpush.subscribedUsers')
        ) || []
      return subscribedUsers.includes(user)
    },
    subscribe() {
      var self = this

      // catch clicks from disabled type='a' button (https://github.com/quasarframework/quasar/issues/9258)
      if (!this.isSupported || this.isPermissionDenied) {
        return
      }

      // ask for notification permission
      Notification.requestPermission()
        .then(permission => {
          this.isPermissionGranted = permission === 'granted'
          this.isPermissionDenied = permission === 'denied'
        })
        .catch(function (e) {
          console.log(e)
        })

      // create push subscription
      navigator.serviceWorker.ready.then(registration => {
        navigator.serviceWorker.getRegistration().then(registration => {
          registration.pushManager
            .getSubscription()
            .then(function (subscription) {
              if (
                subscription === null ||
                !self.isUserSubscribed(self.g.user.id)
              ) {
                const applicationServerKey = self.urlB64ToUint8Array(
                  self.pubkey
                )
                const options = {applicationServerKey, userVisibleOnly: true}

                registration.pushManager
                  .subscribe(options)
                  .then(function (subscription) {
                    LNbits.api
                      .request(
                        'POST',
                        '/api/v1/webpush',
                        self.g.user.wallets[0].adminkey,
                        {
                          subscription: JSON.stringify(subscription)
                        }
                      )
                      .then(function (response) {
                        self.saveUserSubscribed(response.data.user)
                        self.isSubscribed = true
                      })
                      .catch(function (error) {
                        LNbits.utils.notifyApiError(error)
                      })
                  })
              }
            })
            .catch(function (e) {
              console.log(e)
            })
        })
      })
    },
    unsubscribe() {
      var self = this

      navigator.serviceWorker.ready
        .then(registration => {
          registration.pushManager.getSubscription().then(subscription => {
            if (subscription) {
              LNbits.api
                .request(
                  'DELETE',
                  '/api/v1/webpush?endpoint=' + btoa(subscription.endpoint),
                  self.g.user.wallets[0].adminkey
                )
                .then(function () {
                  self.removeUserSubscribed(self.g.user.id)
                  self.isSubscribed = false
                })
                .catch(function (error) {
                  LNbits.utils.notifyApiError(error)
                })
            }
          })
        })
        .catch(function (e) {
          console.log(e)
        })
    },
    checkSupported: function () {
      let https = window.location.protocol === 'https:'
      let serviceWorkerApi = 'serviceWorker' in navigator
      let notificationApi = 'Notification' in window
      let pushApi = 'PushManager' in window

      this.isSupported = https && serviceWorkerApi && notificationApi && pushApi

      if (!this.isSupported) {
        console.log(
          'Notifications disabled because requirements are not met:',
          {
            HTTPS: https,
            'Service Worker API': serviceWorkerApi,
            'Notification API': notificationApi,
            'Push API': pushApi
          }
        )
      }

      return this.isSupported
    },
    updateSubscriptionStatus: async function () {
      var self = this

      await navigator.serviceWorker.ready
        .then(registration => {
          registration.pushManager.getSubscription().then(subscription => {
            self.isSubscribed =
              !!subscription && self.isUserSubscribed(self.g.user.id)
          })
        })
        .catch(function (e) {
          console.log(e)
        })
    }
  },
  created: function () {
    this.isPermissionDenied = Notification.permission === 'denied'

    if (this.checkSupported()) {
      this.updateSubscriptionStatus()
    }
  }
})

window.app.component('lnbits-dynamic-fields', {
  mixins: [window.windowMixin],
  props: ['options', 'value'],
  data() {
    return {
      formData: null,
      rules: [val => !!val || 'Field is required']
    }
  },

  template: `
    <div v-if="formData">
      <div class="row q-mb-lg" v-for="o in options">
        <div class="col auto-width">
          <p v-if=o.options?.length class="q-ml-xl">
            <span v-text="o.label || o.name"></span> <small v-if="o.description"> (<span v-text="o.description"></span>)</small>
          </p>
          <lnbits-dynamic-fields v-if="o.options?.length" :options="o.options" v-model="formData[o.name]"
            @input="handleValueChanged" class="q-ml-xl">
          </lnbits-dynamic-fields>
          <div v-else>
            <q-input
              v-if="o.type === 'number'"
              type="number"
              v-model="formData[o.name]"
              @input="handleValueChanged"
              :label="o.label || o.name"
              :hint="o.description"
              :rules="applyRules(o.required)"
              filled
              dense
            ></q-input>
            <q-input
              v-else-if="o.type === 'text'"
              type="textarea"
              rows="5"
              v-model="formData[o.name]"
              @input="handleValueChanged"
              :label="o.label || o.name"
              :hint="o.description"
              :rules="applyRules(o.required)"
              filled
              dense
            ></q-input>
            <q-input
              v-else-if="o.type === 'password'"
              v-model="formData[o.name]"
              @input="handleValueChanged"
              type="password"
              :label="o.label || o.name"
              :hint="o.description"
              :rules="applyRules(o.required)"
              filled
              dense
            ></q-input>
            <q-select
              v-else-if="o.type === 'select'"
              v-model="formData[o.name]"
              @input="handleValueChanged"
              :label="o.label || o.name"
              :hint="o.description"
              :options="o.values"
              :rules="applyRules(o.required)"
            ></q-select>
            <q-select
              v-else-if="o.isList"
              v-model.trim="formData[o.name]"
              @input="handleValueChanged"
              input-debounce="0"
              new-value-mode="add-unique"
              :label="o.label || o.name"
              :hint="o.description"
              :rules="applyRules(o.required)"
              filled
              multiple
              dense
              use-input
              use-chips
              multiple
              hide-dropdown-icon
            ></q-select>
            <div v-else-if="o.type === 'bool'">
              <q-item tag="label" v-ripple>
                <q-item-section avatar top>
                  <q-checkbox v-model="formData[o.name]" @input="handleValueChanged" />
                </q-item-section>
                <q-item-section>
                  <q-item-label><span v-text="o.label || o.name"></span></q-item-label>
                  <q-item-label caption> <span v-text="o.description"></span> </q-item-label>
                </q-item-section>
              </q-item>
            </div>
            <q-input
              v-else-if="o.type === 'hidden'"
              v-model="formData[o.name]"
              type="text"
              style="display: none"
              :rules="applyRules(o.required)"
            ></q-input>
            <q-input
              v-else
              v-model="formData[o.name]"
              @input="handleValueChanged"
              :hint="o.description"
              :label="o.label || o.name"
              :rules="applyRules(o.required)"
              filled
              dense
            ></q-input>
          </div>
        </div>
      </div>
    </div>
  `,
  methods: {
    applyRules(required) {
      return required ? this.rules : []
    },
    buildData(options, data = {}) {
      return options.reduce((d, option) => {
        if (option.options?.length) {
          d[option.name] = this.buildData(option.options, data[option.name])
        } else {
          d[option.name] = data[option.name] ?? option.default
        }
        return d
      }, {})
    },
    handleValueChanged() {
      this.$emit('input', this.formData)
    }
  },
  created: function () {
    this.formData = this.buildData(this.options, this.value)
  }
})

window.app.component('lnbits-update-balance', {
  mixins: [window.windowMixin],
  props: ['wallet_id', 'callback'],
  computed: {
    denomination() {
      return LNBITS_DENOMINATION
    },
    admin() {
      return this.g.user.admin
    }
  },
  data: function () {
    return {
      credit: 0
    }
  },
  methods: {
    updateBalance: function (credit) {
      LNbits.api
        .updateBalance(credit, this.wallet_id)
        .then(res => {
          if (res.data.status !== 'Success') {
            throw new Error(res.data)
          }
          this.callback({
            success: true,
            credit: parseInt(credit),
            wallet_id: this.wallet_id
          })
        })
        .then(_ => {
          credit = parseInt(credit)
          this.$q.notify({
            type: 'positive',
            message: this.$t('wallet_topup_ok', {
              amount: credit
            }),
            icon: null
          })
          return credit
        })
        .catch(function (error) {
          LNbits.utils.notifyApiError(error)
        })
    }
  },
  template: `
      <q-btn
        v-if="admin"
        round
        color="primary"
        icon="add"
        size="sm"
      >
        <q-popup-edit
          class="bg-accent text-white"
          v-slot="scope"
          v-model="credit"
        >
          <q-input
            filled
            :label='$t("credit_label", { denomination: denomination })'
            :hint="$t('credit_hint')"
            v-model="scope.value"
            dense
            autofocus
            @keyup.enter="updateBalance(scope.value)"
          >
            <template v-slot:append>
              <q-icon name="edit" />
            </template>
          </q-input>
        </q-popup-edit>
        <q-tooltip>Topup Wallet</q-tooltip>
      </q-btn>
    `
})

window.app.use(VueQrcodeReader)
window.app.use(Quasar)
window.app.use(window.i18n)
window.app.mount('#vue')
