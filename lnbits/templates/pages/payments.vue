<template id="page-payments">
  <div class="row q-col-gutter-md q-mb-md">
    <div class="col-12">
      <q-card>
        <div class="q-pa-sm q-pl-lg">
          <div class="row items-center justify-between q-gutter-xs">
            <div class="col"></div>
            <div class="float-left">
              <q-checkbox
                dense
                @click="saveChartsPreferences"
                v-model="chartData.showPaymentStatus"
                :label="$t('payments_status_chart')"
              >
              </q-checkbox>
            </div>
            <q-separator vertical class="q-ma-sm"></q-separator>
            <div class="float-left">
              <q-checkbox
                dense
                @click="saveChartsPreferences"
                v-model="chartData.showPaymentTags"
                :label="$t('payments_tag_chart')"
              >
              </q-checkbox>
            </div>
            <q-separator vertical class="q-ma-sm"></q-separator>
            <div class="float-left">
              <q-checkbox
                dense
                @click="saveChartsPreferences"
                v-model="chartData.showBalance"
                :label="$t('payments_balance_chart')"
              >
              </q-checkbox>
            </div>
            <q-separator vertical class="q-ma-sm"></q-separator>
            <div class="float-left">
              <q-checkbox
                dense
                @click="saveChartsPreferences"
                v-model="chartData.showWalletsSize"
                :label="$t('payments_wallets_chart')"
              >
              </q-checkbox>
            </div>

            <q-separator vertical class="q-ma-sm"></q-separator>
            <div class="float-left">
              <q-checkbox
                dense
                @click="saveChartsPreferences"
                v-model="chartData.showBalanceInOut"
                :label="$t('payments_balance_in_out_chart')"
              >
              </q-checkbox>
            </div>
            <q-separator vertical class="q-ma-sm"></q-separator>
            <div class="float-left">
              <q-checkbox
                dense
                @click="saveChartsPreferences"
                v-model="chartData.showPaymentCountInOut"
                :label="$t('payments_count_in_out_chart')"
              >
              </q-checkbox>
            </div>
            <q-separator vertical class="q-ma-sm"></q-separator>
            <q-btn icon="event" outline flat>
              <q-popup-proxy
                cover
                transition-show="scale"
                transition-hide="scale"
              >
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
              <q-badge
                v-if="searchDate?.to || searchDate?.from"
                class="q-mt-lg q-mr-md"
                color="primary"
                rounded
                floating
                style="border-radius: 6px"
              />
            </q-btn>
            <q-separator vertical class="q-ma-sm"></q-separator>
            <div>
              <q-btn
                v-if="g.user.admin"
                flat
                round
                icon="settings"
                to="/admin#server"
              >
                <q-tooltip v-text="$t('admin_settings')"></q-tooltip>
              </q-btn>
            </div>
          </div>
        </div>
      </q-card>
    </div>
  </div>
  <div v-show="!showDetails">
    <div class="row q-col-gutter-md justify-center q-mb-md">
      <div
        v-show="chartData.showPaymentStatus"
        class="col-lg-3 col-md-6 col-sm-12 text-center"
      >
        <q-card class="q-pt-sm">
          <strong v-text="$t('payment_chart_status')"></strong>
          <div style="height: 300px" class="q-pa-sm">
            <canvas v-if="chartsReady" ref="paymentsStatusChart"></canvas>
          </div>
        </q-card>
      </div>
      <div
        v-show="chartData.showPaymentStatus"
        class="col-lg-3 col-md-6 col-sm-12 text-center"
      >
        <q-card class="q-pt-sm">
          <strong v-text="$t('payment_chart_tags')"></strong>
          <div style="height: 300px" class="q-pa-sm">
            <canvas v-if="chartsReady" ref="paymentsTagsChart"></canvas>
          </div>
        </q-card>
      </div>
      <div
        v-show="chartData.showBalance"
        class="col-lg-6 col-md-12 col-sm-12 text-center"
      >
        <q-card class="q-pt-sm">
          <strong
            v-text="
              $t('lnbits_balance', {
                balance: (lnbitsBalance || 0).toLocaleString()
              })
            "
          ></strong>
          <div style="height: 300px" class="q-pa-sm">
            <canvas v-if="chartsReady" ref="paymentsDailyChart"></canvas>
          </div>
        </q-card>
      </div>
      <div
        v-show="chartData.showWalletsSize"
        class="col-lg-6 col-md-12 col-sm-12 text-center"
      >
        <q-card class="q-pt-sm">
          <strong v-text="$t('payment_chart_tx_per_wallet')"></strong>
          <div style="height: 300px" class="q-pa-sm">
            <canvas v-if="chartsReady" ref="paymentsWalletsChart"></canvas>
          </div>
        </q-card>
      </div>

      <div
        v-show="chartData.showBalanceInOut"
        class="col-lg-6 col-md-12 col-sm-12 text-center"
      >
        <q-card class="q-pt-sm">
          <strong v-text="$t('payments_balance_in_out')"></strong>
          <div style="height: 300px" class="q-pa-sm">
            <canvas v-if="chartsReady" ref="paymentsBalanceInOutChart"></canvas>
          </div>
        </q-card>
      </div>
      <div
        v-show="chartData.showPaymentCountInOut"
        class="col-lg-6 col-md-12 col-sm-12 text-center"
      >
        <q-card class="q-pt-sm">
          <strong v-text="$t('payments_count_in_out')"></strong>
          <div style="height: 300px" class="q-pa-sm">
            <canvas v-if="chartsReady" ref="paymentsCountInOutChart"></canvas>
          </div>
        </q-card>
      </div>
    </div>

    <div class="row q-col-gutter-md justify-center">
      <div class="col">
        <q-card class="q-pa-md">
          <q-table
            row-key="payment_hash"
            :rows="payments"
            :columns="paymentsTable.columns"
            v-model:pagination="paymentsTable.pagination"
            :filter="paymentsTable.search"
            @request="fetchPayments"
          >
            <template v-slot:header="props">
              <q-tr :props="props">
                <q-th v-for="col in props.cols" :key="col.name" :props="props">
                  <q-input
                    v-if="
                      ['wallet_id', 'payment_hash', 'memo'].includes(col.name)
                    "
                    v-model="searchData[col.name]"
                    @keydown.enter="searchPaymentsBy()"
                    @update:model-value="searchPaymentsBy()"
                    dense
                    type="text"
                    filled
                    clearable
                    :label="col.label"
                  >
                    <template v-slot:append>
                      <q-icon
                        name="search"
                        @click="searchPaymentsBy()"
                        class="cursor-pointer"
                      />
                    </template>
                  </q-input>
                  <q-btn
                    v-else-if="['status'].includes(col.name)"
                    flat
                    dense
                    :label="$q.screen.gt.md ? 'Status' : null"
                    icon="filter_alt"
                    color="grey"
                    class="text-capitalize"
                  >
                    <q-menu anchor="top right" self="top start">
                      <q-item dense>
                        <q-checkbox
                          v-model="statusFilters.success"
                          @click="handleFilterChanged"
                          label="Success Payments"
                        ></q-checkbox>
                      </q-item>
                      <q-item dense>
                        <q-checkbox
                          v-model="statusFilters.pending"
                          @click="handleFilterChanged"
                          label="Pending Payments"
                        ></q-checkbox>
                      </q-item>
                      <q-item dense>
                        <q-checkbox
                          v-model="statusFilters.failed"
                          @click="handleFilterChanged"
                          label="Failed Payments"
                        ></q-checkbox>
                      </q-item>
                      <q-separator></q-separator>
                      <q-item dense>
                        <q-checkbox
                          v-model="statusFilters.incoming"
                          @click="handleFilterChanged"
                          label="Incoming Payments"
                        ></q-checkbox>
                      </q-item>
                      <q-item dense>
                        <q-checkbox
                          v-model="statusFilters.outgoing"
                          @click="handleFilterChanged"
                          label="Outgoing Payments"
                        ></q-checkbox>
                      </q-item>
                    </q-menu>
                    <q-tooltip>
                      <span v-text="$t('filter_payments')"></span>
                    </q-tooltip>
                  </q-btn>
                  <q-select
                    v-else-if="['tag'].includes(col.name)"
                    v-model="searchData[col.name]"
                    :options="searchOptions[col.name]"
                    @update:model-value="searchPaymentsBy()"
                    :label="col.label"
                    clearable
                    style="width: 100px"
                  ></q-select>
                  <span v-else v-text="col.label"></span>
                </q-th>
              </q-tr>
            </template>
            <template v-slot:body="props">
              <q-tr auto-width :props="props">
                <q-td v-for="col in props.cols" :key="col.name" :props="props">
                  <div v-if="col.name == 'status'">
                    <q-tooltip
                      ><span v-text="$t('payment_details')"></span
                    ></q-tooltip>
                    <q-icon
                      @click="showDetailsToggle(props.row)"
                      v-if="props.row.status === 'success'"
                      size="14px"
                      :name="props.row.outgoing ? 'call_made' : 'call_received'"
                      :color="props.row.outgoing ? 'pink' : 'green'"
                      class="cursor-pointer"
                    ></q-icon>
                    <q-icon
                      v-else-if="props.row.status === 'pending'"
                      @click="showDetailsToggle(props.row)"
                      name="downloading"
                      :style="
                        props.row.outgoing
                          ? 'transform: rotate(225deg)'
                          : 'transform: scaleX(-1) rotate(315deg)'
                      "
                      color="grey"
                      class="cursor-pointer"
                    ></q-icon>
                    <q-icon
                      v-else
                      @click="showDetailsToggle(props.row)"
                      name="warning"
                      color="yellow"
                      class="cursor-pointer"
                    ></q-icon>
                  </div>
                  <div v-else-if="col.name == 'created_at'">
                    <div>
                      <q-tooltip anchor="top middle">
                        <span
                          v-text="utils.formatDate(props.row.created_at)"
                        ></span>
                      </q-tooltip>
                      <span v-text="props.row.timeFrom"> </span>
                    </div>
                  </div>
                  <div
                    v-else-if="
                      ['wallet_id', 'payment_hash', 'memo'].includes(col.name)
                    "
                  >
                    <q-btn
                      v-if="props.row[col.name]"
                      icon="content_copy"
                      size="sm"
                      flat
                      class="cursor-pointer q-mr-xs"
                      @click="utils.copyText(props.row[col.name])"
                    >
                      <q-tooltip anchor="top middle">Copy</q-tooltip>
                    </q-btn>
                    <span
                      v-text="shortify(props.row[col.name], col.max_length)"
                    >
                    </span>
                    <q-tooltip>
                      <span v-text="props.row[col.name]"></span>
                    </q-tooltip>
                  </div>
                  <span
                    v-else
                    v-text="props.row[col.name]"
                    class="cursor-pointer"
                  ></span>
                </q-td>
              </q-tr>
            </template>
          </q-table>
        </q-card>
      </div>
    </div>
  </div>
  <div v-show="showDetails">
    <q-card>
      <q-card-section class="flex">
        <div>
          <q-btn
            flat
            round
            icon="arrow_back"
            class="q-mr-md"
            @click="showDetailsToggle(null)"
          ></q-btn>
        </div>
        <div class="self-center text-h6 text-weight-bolder text-grey-5">
          <span v-text="$t('payment_details_back')"></span>
        </div>
      </q-card-section>
      <q-separator></q-separator>
      <q-card-section class="text-h6">
        <q-item>
          <q-item-section avatar class="">
            <q-icon color="primary" name="receipt" size="44px"></q-icon>
          </q-item-section>

          <q-item-section>
            <q-item-label>
              <div class="text-h6">
                <span v-text="$t('payment_details')"></span>
              </div>
            </q-item-label>
            <q-item-label caption v-text="$t('payment_details_desc')">
            </q-item-label>
          </q-item-section>
        </q-item>
      </q-card-section>
      <q-card-section>
        <q-list separator>
          <q-item v-for="(value, key) in paymentDetails" :key="key">
            <q-item-section>
              <q-item-label v-text="key"></q-item-label>
              <q-item-label
                caption
                v-text="value"
                style="word-wrap: break-word"
              ></q-item-label>
            </q-item-section>
            <q-item-section side>
              <q-btn
                v-show="value"
                icon="content_copy"
                flat
                class="cursor-pointer q-ml-sm"
                @click="utils.copyText(value)"
              >
                <q-tooltip>Copy</q-tooltip>
              </q-btn>
            </q-item-section>
            <!-- <q-separator></q-separator> -->
          </q-item>
        </q-list>
      </q-card-section>
    </q-card>
  </div>
</template>
