Vue.component('payment-list', {
  name: 'payment-list',
  props: ['update', 'wallet', 'mobileSimple', 'lazy'],
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
    exportCSV: function () {
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
        const payments = response.data.data.map(LNbits.map.payment)
        LNbits.utils.exportCSV(
          this.paymentsCSV.columns,
          payments,
          this.wallet.name + '-payments'
        )
      })
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
            <q-btn flat color="grey" @click="exportCSV" :label="$t('export_csv')" ></q-btn>
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
          :data="paymentsOmitter"
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
                      <div v-if="props.row.isIn && props.row.pending">
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
                      <div v-else-if="props.row.isOut && props.row.pending">
                        <q-icon name="settings_ethernet" color="grey"></q-icon>
                        <span v-text="$t('outgoing_payment_pending')"></span>
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
