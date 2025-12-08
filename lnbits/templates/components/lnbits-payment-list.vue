<template id="lnbits-payment-list">
  <div class="row items-center no-wrap">
    <div class="col" v-if="!g.mobileSimple || $q.screen.gt.sm">
      <q-input
        :label="$t('search_by_tag_memo_amount')"
        dense
        class="q-pr-xl"
        v-model="paymentsTable.search"
      >
        <template v-slot:before>
          <q-icon name="search"> </q-icon>
        </template>
        <template v-slot:append>
          <q-icon
            v-if="paymentsTable.search !== ''"
            name="close"
            @click="paymentsTable.search = ''"
            class="cursor-pointer"
          >
          </q-icon>
        </template>
      </q-input>
    </div>
    <div class="gt-sm col-auto">
      <q-btn icon="event" flat color="grey" class="q-pa-sm">
        <q-badge
          v-if="searchDate?.to || searchDate?.from"
          color="primary"
          floating
        ></q-badge>
        <q-popup-proxy cover transition-show="scale" transition-hide="scale">
          <q-date v-model="searchDate" mask="YYYY-MM-DD" range />
          <div class="row">
            <div class="col-6">
              <q-btn
                label="Search"
                @click="searchByDate()"
                color="primary"
                flat
                class="float-left"
                v-close-popup
              />
            </div>
            <div class="col-6">
              <q-btn
                v-close-popup
                @click="clearDateSeach()"
                label="Clear"
                class="float-right"
                color="grey"
                flat
              />
            </div>
          </div>
        </q-popup-proxy>

        <q-tooltip>
          <span v-text="$t('filter_date')"></span>
        </q-tooltip>
      </q-btn>
      <q-btn icon="local_offer" class="q-pa-sm" flat color="grey">
        <q-badge
          v-if="filterLabels.length"
          color="primary"
          size="xs"
          floating
          v-text="filterLabels.length"
        ></q-badge>
        <q-tooltip>
          <span v-text="$t('label_filter')"></span>
        </q-tooltip>
        <q-popup-edit class="text-white q-pa-none">
          <lnbits-label-selector
            :labels="filterLabels"
            @update:labels="searchByLabels"
          ></lnbits-label-selector>
        </q-popup-edit>
      </q-btn>
      <q-btn color="grey" icon="filter_alt" class="q-pa-sm" flat>
        <q-menu>
          <q-item dense>
            <q-checkbox
              v-model="searchStatus.success"
              @click="handleFilterChanged"
              label="Success Payments"
            ></q-checkbox>
          </q-item>
          <q-item dense>
            <q-checkbox
              v-model="searchStatus.pending"
              @click="handleFilterChanged"
              label="Pending Payments"
            ></q-checkbox>
          </q-item>
          <q-item dense>
            <q-checkbox
              v-model="searchStatus.failed"
              @click="handleFilterChanged"
              label="Failed Payments"
            ></q-checkbox>
          </q-item>
          <q-separator></q-separator>
          <q-item dense>
            <q-checkbox
              v-model="searchStatus.incoming"
              @click="handleFilterChanged"
              label="Incoming Payments"
            ></q-checkbox>
          </q-item>
          <q-item dense>
            <q-checkbox
              v-model="searchStatus.outgoing"
              @click="handleFilterChanged"
              label="Outgoing Payments"
            ></q-checkbox>
          </q-item>
        </q-menu>
        <q-tooltip>
          <span v-text="$t('filter_payments')"></span>
        </q-tooltip>
      </q-btn>
      <q-btn color="grey" icon="sort" class="q-pa-sm" flat>
        <q-menu>
          <q-list>
            <template
              class="full-width"
              v-for="column in paymentsTable.sortFields"
              :key="column.name"
            >
              <q-item
                @click="sortByColumn(column.name)"
                clickable
                v-ripple
                v-close-popup
                dense
              >
                <q-item-section>
                  <q-item-label lines="1" class="full-width"
                    ><span v-text="column.label"></span
                  ></q-item-label>
                </q-item-section>
                <q-item-section side>
                  <template
                    v-if="paymentsTable.pagination.sortBy === column.name"
                  >
                    <q-icon
                      v-if="paymentsTable.pagination.descending"
                      name="arrow_downward"
                    ></q-icon>
                    <q-icon v-else name="arrow_upward"></q-icon>
                  </template>
                </q-item-section>
              </q-item>
            </template>
          </q-list>
        </q-menu>
        <q-tooltip>
          <span v-text="$t('filter_payments')"></span>
        </q-tooltip>
      </q-btn>

      <q-btn-dropdown
        dense
        outline
        persistent
        icon="archive"
        split
        class="q-mr-sm q-pa-sm"
        color="grey"
        @click="exportCSV(false)"
      >
        <q-tooltip>
          <span v-text="$t('export_csv')"></span>
        </q-tooltip>
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
                <q-btn @click="addFilterTag" dense flat icon="add"></q-btn>
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
              <q-btn
                v-close-popup
                outline
                color="grey"
                @click="exportCSV(true)"
                :label="$t('export_csv_details')"
              ></q-btn>
            </q-item-section>
          </q-item>
        </q-list>
      </q-btn-dropdown>
    </div>
  </div>
  <div class="row q-my-md"></div>
  <q-table
    dense
    flat
    :rows="paymentsOmitter"
    :row-key="paymentTableRowKey"
    :columns="paymentsTable.columns"
    :no-data-label="$t('no_transactions')"
    :filter="paymentFilter"
    :loading="paymentsTable.loading"
    :hide-header="g.mobileSimple && $q.screen.lt.md"
    :hide-bottom="g.mobileSimple && $q.screen.lt.md"
    v-model:pagination="paymentsTable.pagination"
    :rows-per-page-options="$q.config.table.rowsPerPageOptions"
    @request="fetchPayments"
  >
    <template v-slot:header="props">
      <q-tr :props="props" class="text-grey-5">
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
        <q-td auto-width class="text-center cursor-pointer">
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
            <q-tooltip><span>failed</span></q-tooltip>
          </q-icon>
          <q-icon
            v-else
            name="downloading"
            color="grey"
            :style="
              props.row.isOut
                ? 'transform: rotate(225deg)'
                : 'transform: scaleX(-1) rotate(315deg)'
            "
            @click="props.expand = !props.expand"
          >
            <q-tooltip><span v-text="$t('pending')"></span></q-tooltip>
          </q-icon>
        </q-td>
        <q-td
          key="time"
          :props="props"
          style="white-space: normal; word-break: break-all"
        >
          <q-icon
            v-if="
              props.row.isIn &&
              props.row.isPending &&
              props.row.extra.hold_invoice
            "
            name="pause_presentation"
            color="grey"
            class="cursor-pointer q-mr-sm"
            @click="showHoldInvoiceDialog(props.row)"
          >
            <q-tooltip><span v-text="$t('hold_invoice')"></span></q-tooltip>
          </q-icon>
          <q-badge
            v-if="props.row.tag"
            color="yellow"
            text-color="black"
            class="q-mr-sm"
          >
            <a
              v-text="'#' + props.row.tag"
              class="inherit"
              :href="['/', props.row.tag].join('')"
            ></a>
          </q-badge>
          <span v-text="props.row.memo"></span>
          <span
            class="text-grey-5 q-ml-sm ellipsis"
            v-if="props.row.extra.internal_memo"
            v-text="`(${props.row.extra.internal_memo})`"
          ></span>
          <br />

          <i>
            <span class="text-grey-5" v-text="props.row.dateFrom"></span>
            <q-tooltip><span v-text="props.row.date"></span></q-tooltip>
          </i>
          <q-icon
            @click="selectedPayment = props.row"
            name="local_offer"
            color="grey"
            class="q-ml-sm cursor-pointer"
            size="xs"
          >
            <q-tooltip>
              <span v-text="$t('add_remove_labels')"></span>
            </q-tooltip>
            <q-popup-edit class="text-white q-pa-none">
              <lnbits-label-selector
                :labels="props.row.labels"
                @update:labels="savePaymentLabels"
              ></lnbits-label-selector>
            </q-popup-edit>
          </q-icon>
          <template v-for="label in g.user.extra.labels" :key="label.name">
            <q-badge
              v-if="props.row.labels.includes(label.name)"
              @click="searchByLabels([label.name])"
              :style="{
                backgroundColor: label.color,
                color: isLightColor(label.color) ? 'black' : 'white'
              }"
              class="q-ml-sm cursor-pointer"
              size="xs"
              dense
              rounded
            >
              <span v-text="label.name"></span>
              <q-tooltip>
                <span v-text="label.description || label.name"></span>
              </q-tooltip>
            </q-badge>
          </template>
        </q-td>
        <q-td
          v-if="!g.isSatsDenomination"
          auto-width
          key="amount"
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
              v-text="
                formatCurrency(
                  props.row.extra.wallet_fiat_amount,
                  props.row.extra.wallet_fiat_currency
                )
              "
            ></span>
            <br />
          </i>
          <i v-if="props.row.extra.fiat_currency">
            <span
              v-text="
                formatCurrency(
                  props.row.extra.fiat_amount,
                  props.row.extra.fiat_currency
                )
              "
            ></span>
          </i>
        </q-td>
        <q-dialog v-model="props.expand" :props="props" position="top">
          <q-card class="q-pa-sm q-pt-xl lnbits__dialog-card">
            <q-card-section>
              <q-list bordered separator>
                <q-expansion-item
                  expand-separator
                  :default-opened="!(props.row.isIn && props.row.isPending)"
                >
                  <template v-slot:header>
                    <q-item-section avatar>
                      <q-icon
                        :color="
                          props.row.isPaid && props.row.isIn
                            ? 'green'
                            : props.row.isPaid && props.row.isOut
                              ? 'pink'
                              : props.row.isFailed
                                ? 'yellow'
                                : 'grey'
                        "
                        :name="
                          props.row.isPaid && props.row.isIn
                            ? 'call_received'
                            : props.row.isPaid && props.row.isOut
                              ? 'call_made'
                              : props.row.isFailed
                                ? 'warning'
                                : 'settings_ethernet'
                        "
                      />
                    </q-item-section>

                    <q-item-section>
                      <q-item-label
                        v-text="
                          props.row.isIn && props.row.isPending
                            ? $t('invoice_waiting')
                            : props.row.isOut && props.row.isPending
                              ? $t('outgoing_payment_pending')
                              : props.row.isPaid && props.row.isIn
                                ? $t('payment_received')
                                : props.row.isPaid && props.row.isOut
                                  ? $t('payment_sent')
                                  : props.row.isFailed
                                    ? $t('payment_failed')
                                    : ''
                        "
                      ></q-item-label>
                    </q-item-section>
                    <q-item-section v-if="props.row.tag" side>
                      <q-badge
                        v-if="props.row.extra && !!props.row.extra.tag"
                        color="yellow"
                        text-color="black"
                      >
                        #<span v-text="props.row.tag"></span>
                      </q-badge>
                    </q-item-section>
                  </template>
                  <q-separator></q-separator>
                  <lnbits-payment-details
                    :payment="props.row"
                  ></lnbits-payment-details>
                </q-expansion-item>
              </q-list>

              <div
                v-if="props.row.isIn && props.row.isPending && props.row.bolt11"
              >
                <div v-if="props.row.extra.fiat_payment_request">
                  <lnbits-qrcode
                    :value="props.row.extra.fiat_payment_request"
                    :href="props.row.extra.fiat_payment_request"
                    :show-buttons="false"
                  ></lnbits-qrcode>
                </div>
                <div v-else>
                  <lnbits-qrcode
                    :value="'lightning:' + props.row.bolt11.toUpperCase()"
                    :href="'lightning:' + props.row.bolt11"
                  ></lnbits-qrcode>
                </div>
              </div>
              <div class="row q-mt-md">
                <q-btn
                  outline
                  color="grey"
                  @click="checkPayment(props.row.payment_hash)"
                  icon="refresh"
                  :label="$t('payment_check')"
                ></q-btn>
                <q-btn
                  v-close-popup
                  flat
                  color="grey"
                  class="q-ml-auto"
                  :label="$t('close')"
                ></q-btn>
              </div>
            </q-card-section>
          </q-card>
        </q-dialog>
        <q-dialog v-model="hodlInvoice.show" position="top">
          <q-card class="q-pa-sm q-pt-xl lnbits__dialog-card">
            <q-card-section>
              <q-item-label class="text-h6">
                <span v-text="$t('hold_invoice')"></span>
              </q-item-label>
              <q-item-label class="text-subtitle2">
                <span v-text="$t('hold_invoice_description')"></span>
              </q-item-label>
            </q-card-section>
            <q-card-section>
              <q-input
                filled
                :label="$t('preimage')"
                :hint="$t('preimage_hint')"
                v-model="hodlInvoice.preimage"
                dense
                autofocus
                @keyup.enter="settleHoldInvoice(hodlInvoice.preimage)"
              >
              </q-input>
            </q-card-section>
            <q-card-section class="row q-gutter-x-sm">
              <q-btn
                @click="settleHoldInvoice(hodlInvoice.preimage)"
                outline
                v-close-popup
                color="grey"
                :label="$t('settle_invoice')"
              >
              </q-btn>
              <q-btn
                v-close-popup
                outline
                color="grey"
                class="q-ml-sm"
                @click="cancelHoldInvoice(hodlInvoice.payment.payment_hash)"
                :label="$t('cancel_invoice')"
              ></q-btn>
              <q-btn
                v-close-popup
                flat
                color="grey"
                class="q-ml-auto"
                :label="$t('close')"
              ></q-btn>
            </q-card-section>
          </q-card>
        </q-dialog>
      </q-tr>
    </template>
  </q-table>
</template>
