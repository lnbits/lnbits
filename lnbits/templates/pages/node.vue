<template id="page-node">
  <q-dialog v-model="nodeInfoDialog.show" position="top">
    <lnbits-node-qrcode :info="nodeInfoDialog.data"></lnbits-node-qrcode>
  </q-dialog>
  <div class="row q-col-gutter-md justify-center">
    <div class="col q-gutter-y-md">
      <q-card>
        <div class="q-pa-md">
          <div class="q-gutter-y-md">
            <q-tabs v-model="tab" active-color="primary" align="justify">
              <q-tab
                name="dashboard"
                :label="$t('dashboard')"
                @update="val => (tab = val.name)"
              ></q-tab>
              <q-tab
                name="channels"
                :label="$t('channels')"
                @update="val => (tab = val.name)"
              ></q-tab>
              <q-tab
                name="transactions"
                :label="$t('transactions')"
                @update="val => (tab = val.name)"
              ></q-tab>
            </q-tabs>
          </div>
        </div>
        <q-form name="settings_form" id="settings_form">
          <q-tab-panels v-model="tab" animated>
            <q-tab-panel name="dashboard">
              <q-card-section class="q-pa-none">
                <lnbits-node-info :info="this.info"></lnbits-node-info>
                <div class="row q-col-gutter-lg q-mt-sm">
                  <div class="col-12 col-md-8 q-gutter-y-md">
                    <div class="row q-col-gutter-md q-pb-lg">
                      <div class="col-12 col-md-6 col-xl-4 q-gutter-y-md">
                        <lnbits-stat
                          :title="$t('total_capacity')"
                          :msat="this.channel_stats.total_capacity"
                        />
                      </div>
                      <div class="col-12 col-md-6 col-xl-4 q-gutter-y-md">
                        <lnbits-stat
                          title="Balance"
                          :msat="this.info.balance_msat"
                        />
                      </div>

                      <div class="col-12 col-md-6 col-xl-4 q-gutter-y-md">
                        <lnbits-stat
                          title="Fees collected"
                          :msat="this.info.fees?.total_msat"
                        />
                      </div>

                      <div class="col-12 col-md-6 col-xl-4 q-gutter-y-md">
                        <lnbits-stat
                          title="Onchain Balance"
                          :btc="this.info.onchain_balance_sat / 100000000"
                        />
                      </div>

                      <div class="col-12 col-md-6 col-xl-4 q-gutter-y-md">
                        <lnbits-stat
                          title="Onchain Confirmed"
                          :btc="this.info.onchain_confirmed_sat / 100000000"
                        />
                      </div>
                      <div class="col-12 col-md-6 col-xl-4 q-gutter-y-md">
                        <lnbits-stat
                          title="Peers"
                          :amount="this.info.num_peers"
                        />
                      </div>
                      <div class="col-12 col-md-6 col-xl-4 q-gutter-y-md">
                        <lnbits-stat
                          :title="$t('avg_channel_size')"
                          :msat="this.channel_stats.avg_size"
                        />
                      </div>
                      <div class="col-12 col-md-6 col-xl-4 q-gutter-y-md">
                        <lnbits-stat
                          :title="$t('biggest_channel_size')"
                          :msat="this.channel_stats.biggest_size"
                        />
                      </div>
                      <div class="col-12 col-md-6 col-xl-4 q-gutter-y-md">
                        <lnbits-stat
                          :title="$t('smallest_channel_size')"
                          :msat="this.channel_stats.smallest_size"
                        />
                      </div>
                    </div>
                  </div>
                  <div class="column col-12 col-md-4 q-gutter-y-md">
                    <lnbits-node-ranks :ranks="this.ranks"></lnbits-node-ranks>
                    <lnbits-channel-stats
                      :stats="this.channel_stats"
                    ></lnbits-channel-stats>
                  </div>
                </div>
              </q-card-section>
            </q-tab-panel>
            <q-tab-panel name="channels">
              <q-dialog v-model="connectPeerDialog.show" position="top">
                <q-card class="q-pa-lg q-pt-xl lnbits__dialog-card">
                  <q-form class="q-gutter-md">
                    <q-input
                      dense
                      type="text"
                      filled
                      v-model="connectPeerDialog.data.uri"
                      label="Node URI"
                      hint="pubkey@host:port"
                    ></q-input>

                    <div class="row q-mt-lg">
                      <q-btn
                        :label="$t('connect')"
                        color="primary"
                        @click="connectPeer"
                      ></q-btn>
                      <q-btn
                        v-close-popup
                        flat
                        color="grey"
                        class="q-ml-auto"
                        :label="$t('cancel')"
                      ></q-btn>
                    </div>
                  </q-form>
                </q-card>
              </q-dialog>

              <q-dialog v-model="setFeeDialog.show">
                <q-card class="q-pa-lg q-pt-xl lnbits__dialog-card">
                  <label class="text-h6">Set Channel Fee</label>
                  <p class="text-caption" v-text="setFeeDialog.channel_id"></p>
                  <q-separator></q-separator>
                  <q-form class="q-gutter-md">
                    <q-input
                      dense
                      type="number"
                      filled
                      v-model.number="setFeeDialog.data.fee_ppm"
                      label="Fee Rate PPM"
                    ></q-input>
                    <q-input
                      dense
                      type="number"
                      filled
                      v-model.number="setFeeDialog.data.fee_base_msat"
                      label="Fee Base msat"
                    ></q-input>

                    <div class="row q-mt-lg">
                      <q-btn
                        :label="$t('set')"
                        color="primary"
                        @click="setChannelFee(setFeeDialog.channel_id)"
                      ></q-btn>
                      <q-btn
                        v-close-popup
                        flat
                        color="grey"
                        class="q-ml-auto"
                        :label="$t('cancel')"
                      ></q-btn>
                    </div>
                  </q-form>
                </q-card>
              </q-dialog>

              <q-dialog v-model="openChannelDialog.show">
                <q-card class="q-pa-lg q-pt-xl lnbits__dialog-card">
                  <q-form class="q-gutter-md">
                    <q-input
                      dense
                      type="text"
                      filled
                      v-model="openChannelDialog.data.peer_id"
                      label="Peer ID"
                    ></q-input>
                    <q-input
                      dense
                      type="number"
                      filled
                      v-model.number="openChannelDialog.data.funding_amount"
                      label="Funding Amount"
                    ></q-input>
                    <q-expansion-item icon="warning" label="Advanced">
                      <q-card>
                        <q-card-section>
                          <div class="column q-gutter-md">
                            <q-input
                              dense
                              type="number"
                              filled
                              v-model.number="
                                openChannelDialog.data.push_amount
                              "
                              label="Push Amount"
                              hint="This gifts sats to the other side!"
                            ></q-input>

                            <q-input
                              dense
                              type="number"
                              filled
                              v-model.number="openChannelDialog.data.fee_rate"
                              label="Fee Rate"
                            ></q-input>
                          </div>
                        </q-card-section>
                      </q-card>
                    </q-expansion-item>

                    <div class="row q-mt-lg">
                      <q-btn
                        :label="$t('open')"
                        color="primary"
                        @click="openChannel"
                      ></q-btn>
                      <q-btn
                        v-close-popup
                        flat
                        color="grey"
                        class="q-ml-auto"
                        :label="$t('cancel')"
                      ></q-btn>
                    </div>
                  </q-form>
                </q-card>
              </q-dialog>

              <q-dialog v-model="closeChannelDialog.show" position="top">
                <q-card class="q-pa-lg q-pt-xl lnbits__dialog-card">
                  <q-form class="q-gutter-md">
                    <div>
                      <q-checkbox
                        v-model="closeChannelDialog.data.force"
                        label="Force"
                      />
                    </div>

                    <div class="row q-mt-lg">
                      <q-btn
                        :label="$t('close')"
                        color="primary"
                        @click="closeChannel"
                      ></q-btn>
                      <q-btn
                        v-close-popup
                        flat
                        color="grey"
                        class="q-ml-auto"
                        :label="$t('cancel')"
                      ></q-btn>
                    </div>
                  </q-form>
                </q-card>
              </q-dialog>

              <q-card-section class="q-pa-none">
                <div class="row q-col-gutter-lg">
                  <div class="col-12 col-xl-6">
                    <q-card class="full-height">
                      <q-card-section class="q-gutter-y-sm">
                        <div
                          class="row items-center q-mt-none q-gutter-x-sm no-wrap"
                        >
                          <div class="col-grow text-h6 q-my-none col-grow">
                            Channels
                          </div>
                          <q-input
                            filled
                            dense
                            clearable
                            v-model="channels.filter"
                            placeholder="Search..."
                            class="col-auto"
                          ></q-input>
                          <q-select
                            dense
                            size="sm"
                            style="min-width: 200px"
                            filled
                            multiple
                            clearable
                            v-model="stateFilters"
                            :options="this.states"
                            class="col-auto"
                          ></q-select>
                          <q-btn
                            unelevated
                            color="primary"
                            size="md"
                            class="col-auto"
                            @click="showOpenChannelDialog()"
                          >
                            Open channel
                          </q-btn>
                        </div>
                        <div>
                          <div class="text-subtitle1 col-grow">Total</div>
                          <lnbits-channel-balance
                            :balance="this.totalBalance"
                          ></lnbits-channel-balance>
                        </div>
                        <q-separator></q-separator>
                        <q-table
                          dense
                          flat
                          :rows="this.filteredChannels"
                          :filter="channels.filter"
                          no-data-label="No channels opened"
                        >
                          <template v-slot:header="props">
                            <q-tr :props="props" style="height: 0"> </q-tr>
                          </template>
                          <template v-slot:body="props">
                            <q-tr :props="props">
                              <div class="q-pb-sm">
                                <div class="row items-center q-gutter-sm">
                                  <div
                                    class="text-subtitle1"
                                    v-text="props.row.name"
                                  ></div>
                                  <div
                                    class="text-caption"
                                    v-if="props.row.peer_id"
                                  >
                                    <span>Peer ID</span>
                                    <q-btn
                                      size="xs"
                                      flat
                                      dense
                                      icon="content_paste"
                                      @click="utils.copyText(props.row.peer_id)"
                                    ></q-btn>
                                  </div>
                                  <div class="text-caption col-grow">
                                    <span>Fees</span>
                                    <q-btn
                                      size="xs"
                                      flat
                                      dense
                                      icon="settings"
                                      @click="showSetFeeDialog(props.row.id)"
                                    ></q-btn>
                                    <span v-if="props.row.fee_ppm">
                                      <span v-text="props.row.fee_ppm"></span>
                                      ppm,
                                      <span
                                        v-text="props.row.fee_base_msat"
                                      ></span>
                                      msat
                                    </span>
                                  </div>
                                  <div class="text-caption" v-if="props.row.id">
                                    <span>Channel ID</span>
                                    <q-btn
                                      size="xs"
                                      flat
                                      dense
                                      icon="content_paste"
                                      @click="utils.copyText(props.row.id)"
                                    ></q-btn>
                                  </div>
                                  <div
                                    class="text-caption"
                                    v-if="props.row.short_id"
                                  >
                                    <span v-text="props.row.short_id"></span>
                                    <q-btn
                                      size="xs"
                                      flat
                                      dense
                                      icon="content_paste"
                                      @click="
                                        utils.copyText(props.row.short_id)
                                      "
                                    ></q-btn>
                                  </div>
                                  <q-badge
                                    rounded
                                    :color="
                                      states.find(
                                        s => s.value == props.row.state
                                      )?.color
                                    "
                                    v-text="
                                      states.find(
                                        s => s.value == props.row.state
                                      )?.label
                                    "
                                  >
                                  </q-badge>
                                  <q-btn
                                    :disable="props.row.state !== 'active'"
                                    flat
                                    dense
                                    size="md"
                                    @click="showCloseChannelDialog(props.row)"
                                    icon="cancel"
                                    color="pink"
                                  ></q-btn>
                                </div>

                                <lnbits-channel-balance
                                  :balance="props.row.balance"
                                  :color="props.row.color"
                                ></lnbits-channel-balance>
                              </div>
                            </q-tr>
                          </template>
                        </q-table>
                      </q-card-section>
                    </q-card>
                  </div>
                  <div class="col-12 col-xl-6">
                    <q-card class="full-height">
                      <q-card-section class="column q-gutter-y-sm">
                        <div
                          class="row items-center q-mt-none justify-between q-gutter-x-md no-wrap"
                        >
                          <div class="col-grow text-h6 q-my-none">Peers</div>
                          <q-input
                            filled
                            dense
                            clearable
                            v-model="peers.filter"
                            placeholder="Search..."
                            class="col-auto"
                          ></q-input>
                          <q-btn
                            class="col-auto"
                            color="primary"
                            @click="connectPeerDialog.show = true"
                          >
                            Connect Peer
                          </q-btn>
                        </div>
                        <q-separator></q-separator>
                        <q-table
                          dense
                          flat
                          :rows="peers.data"
                          :filter="peers.filter"
                          no-data-label="No transactions made yet"
                        >
                          <template v-slot:header="props">
                            <q-tr :props="props" style="height: 0"> </q-tr>
                          </template>
                          <template v-slot:body="props">
                            <q-tr :props="props">
                              <div class="row no-wrap items-center q-gutter-sm">
                                <div class="q-my-sm col-grow">
                                  <div
                                    class="text-subtitle1 text-bold"
                                    v-text="props.row.alias"
                                  ></div>
                                  <div class="row items-center q-gutter-sm">
                                    <q-badge
                                      :style="`background-color: #${props.row.color}`"
                                      class="text-bold"
                                      v-text="'#' + props.row.color"
                                    >
                                    </q-badge>
                                    <div
                                      class="text-bold"
                                      v-text="shortenNodeId(props.row.id)"
                                    ></div>
                                    <q-btn
                                      size="xs"
                                      flat
                                      dense
                                      icon="content_paste"
                                      @click="utils.copyText(props.row.id)"
                                    ></q-btn>
                                    <q-btn
                                      size="xs"
                                      flat
                                      dense
                                      icon="qr_code"
                                      @click="showNodeInfoDialog(props.row)"
                                    ></q-btn>
                                  </div>
                                </div>
                                <q-btn
                                  unelevated
                                  color="primary"
                                  @click="showOpenChannelDialog(props.row.id)"
                                >
                                  Open channel
                                </q-btn>
                                <q-btn
                                  flat
                                  dense
                                  size="md"
                                  @click="disconnectPeer(props.row.id)"
                                  icon="cancel"
                                  color="pink"
                                ></q-btn>
                              </div>
                            </q-tr>
                          </template>
                        </q-table>
                      </q-card-section>
                    </q-card>
                  </div>
                </div>
              </q-card-section>
            </q-tab-panel>
            <q-tab-panel name="transactions">
              <q-card-section class="q-pa-none">
                <q-dialog
                  v-model="transactionDetailsDialog.show"
                  position="top"
                >
                  <q-card class="my-card">
                    <q-card-section>
                      <div class="text-center q-mb-lg">
                        <div
                          v-if="
                            transactionDetailsDialog.data.isIn &&
                            transactionDetailsDialog.data.pending
                          "
                        >
                          <q-icon
                            size="18px"
                            :name="'call_received'"
                            :color="'green'"
                          ></q-icon>
                          <span v-text="$t('payment_received')"></span>
                        </div>
                        <div class="row q-my-md">
                          <div class="col-3">
                            <b v-text="$t('payment_hash')"></b>:
                          </div>
                          <div class="col-9 text-wrap mono">
                            <span
                              v-text="
                                transactionDetailsDialog.data.payment_hash
                              "
                            ></span>
                            <q-icon
                              name="content_copy"
                              @click="
                                utils.copyText(
                                  transactionDetailsDialog.data.payment_hash
                                )
                              "
                              size="1em"
                              color="grey"
                              class="q-mb-xs cursor-pointer"
                            />
                          </div>
                          <div
                            class="row"
                            v-if="
                              transactionDetailsDialog.data.preimage &&
                              !transactionDetailsDialog.data.pending
                            "
                          >
                            <div class="col-3">
                              <b v-text="$t('payment_proof')"></b>:
                            </div>
                            <div class="col-9 text-wrap mono">
                              <span
                                v-text="transactionDetailsDialog.data.preimage"
                              ></span>
                              <q-icon
                                name="content_copy"
                                @click="
                                  utils.copyText(
                                    transactionDetailsDialog.data.preimage
                                  )
                                "
                                size="1em"
                                color="grey"
                                class="q-mb-xs cursor-pointer"
                              />
                            </div>
                          </div>
                        </div>
                        <div
                          v-if="transactionDetailsDialog.data.bolt11"
                          class="text-center q-mb-lg"
                        >
                          <a
                            :href="
                              'lightning:' +
                              transactionDetailsDialog.data.bolt11
                            "
                          >
                            <q-responsive :ratio="1" class="q-mx-xl">
                              <qrcode-vue
                                :value="
                                  'lightning:' +
                                  transactionDetailsDialog.data.bolt11.toUpperCase()
                                "
                                :options="{width: 340}"
                                class="rounded-borders"
                              ></qrcode-vue>
                            </q-responsive>
                          </a>
                          <q-btn
                            outline
                            color="grey"
                            @click="
                              utils.copyText(
                                transactionDetailsDialog.data.bolt11
                              )
                            "
                            :label="$t('copy_invoice')"
                            class="q-mt-sm"
                          ></q-btn>
                        </div>
                      </div>
                    </q-card-section>
                  </q-card>
                </q-dialog>

                <div class="row q-col-gutter-md q-pb-lg"></div>

                <div class="row q-col-gutter-lg">
                  <div class="col-12 col-lg-6 q-gutter-y-md">
                    <q-card>
                      <q-card-section>
                        <div class="row items-center no-wrap q-mb-sm">
                          <div class="col text-h6 q-my-none">Payments</div>
                          <q-input
                            v-if="payments.length > 10"
                            filled
                            dense
                            clearable
                            v-model="paymentsTable.filter"
                            debounce="300"
                            placeholder="Search by tag, memo, amount"
                            class="q-mb-md"
                          >
                          </q-input>
                        </div>
                        <q-table
                          dense
                          flat
                          :rows="paymentsTable.data"
                          :columns="paymentsTable.columns"
                          v-model:pagination="paymentsTable.pagination"
                          row-key="payment_hash"
                          no-data-label="No transactions made yet"
                          :filter="paymentsTable.filter"
                          @request="getPayments"
                        >
                          <template v-slot:body-cell-pending="props">
                            <q-td auto-width class="text-center">
                              <q-icon
                                v-if="!props.row.pending"
                                size="xs"
                                name="call_made"
                                color="green"
                                @click="showTransactionDetailsDialog(props.row)"
                              ></q-icon>
                              <q-icon
                                v-else
                                size="xs"
                                name="settings_ethernet"
                                color="grey"
                                @click="showTransactionDetailsDialog(props.row)"
                              >
                                <q-tooltip>Pending</q-tooltip>
                              </q-icon>
                              <q-dialog
                                v-model="props.row.expand"
                                :props="props"
                                position="top"
                              >
                                <q-card
                                  class="q-pa-lg q-pt-xl lnbits__dialog-card"
                                >
                                  <div class="text-center q-mb-lg">
                                    <div
                                      v-if="props.row.isIn && props.row.pending"
                                    >
                                      <q-icon
                                        name="settings_ethernet"
                                        color="grey"
                                      ></q-icon>
                                      <span
                                        v-text="$t('invoice_waiting')"
                                      ></span>
                                      <lnbits-payment-details
                                        :payment="props.row"
                                      ></lnbits-payment-details>
                                      <div
                                        v-if="props.row.bolt11"
                                        class="text-center q-mb-lg"
                                      >
                                        <a
                                          :href="
                                            'lightning:' + props.row.bolt11
                                          "
                                        >
                                          <q-responsive
                                            :ratio="1"
                                            class="q-mx-xl"
                                          >
                                            <qrcode-vue
                                              :value="
                                                'lightning:' +
                                                props.row.bolt11.toUpperCase()
                                              "
                                              :options="{width: 340}"
                                              class="rounded-borders"
                                            ></qrcode-vue>
                                          </q-responsive>
                                        </a>
                                      </div>
                                      <div class="row q-mt-lg">
                                        <q-btn
                                          outline
                                          color="grey"
                                          @click="
                                            utils.copyText(props.row.bolt11)
                                          "
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
                                    <div
                                      v-else-if="
                                        props.row.isPaid && props.row.isIn
                                      "
                                    >
                                      <q-icon
                                        size="18px"
                                        :name="'call_received'"
                                        :color="'green'"
                                      ></q-icon>
                                      <span
                                        v-text="$t('payment_received')"
                                      ></span>
                                      <lnbits-payment-details
                                        :payment="props.row"
                                      ></lnbits-payment-details>
                                    </div>
                                    <div
                                      v-else-if="
                                        props.row.isPaid && props.row.isOut
                                      "
                                    >
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
                                    <div
                                      v-else-if="
                                        props.row.isOut && props.row.pending
                                      "
                                    >
                                      <q-icon
                                        name="settings_ethernet"
                                        color="grey"
                                      ></q-icon>
                                      <span
                                        v-text="$t('outgoing_payment_pending')"
                                      ></span>
                                      <lnbits-payment-details
                                        :payment="props.row"
                                      ></lnbits-payment-details>
                                    </div>
                                  </div>
                                </q-card>
                              </q-dialog>
                            </q-td>
                          </template>
                          <template v-slot:body-cell-date="props">
                            <q-td auto-width key="date" :props="props">
                              <q-tooltip
                                ><span
                                  v-text="utils.formatTimestamp(props.row.time)"
                                ></span
                              ></q-tooltip>
                              <span
                                v-text="
                                  utils.formatTimestampFrom(props.row.time)
                                "
                              ></span>
                            </q-td>
                          </template>
                          <template v-slot:body-cell-destination="props">
                            <q-td auto-width key="destination">
                              <div
                                class="row items-center justify-between no-wrap"
                              >
                                <q-badge
                                  :style="`background-color: #${props.row.destination?.color}`"
                                  class="text-bold"
                                  v-text="props.row.destination?.alias"
                                ></q-badge>
                                <div>
                                  <q-btn
                                    size="xs"
                                    flat
                                    dense
                                    icon="content_paste"
                                    @click="utils.copyText(info.id)"
                                  ></q-btn>
                                  <q-btn
                                    size="xs"
                                    flat
                                    dense
                                    icon="qr_code"
                                    @click="
                                      showNodeInfoDialog(props.row.destination)
                                    "
                                  ></q-btn>
                                </div>
                              </div>
                            </q-td>
                          </template>
                        </q-table>
                      </q-card-section>
                    </q-card>
                  </div>
                  <div class="col-12 col-lg-6 q-gutter-y-md">
                    <q-card>
                      <q-card-section>
                        <div class="row items-center no-wrap q-mb-sm">
                          <div class="col text-h6 q-my-none">Invoices</div>
                          <q-input
                            v-if="payments.length > 10"
                            filled
                            dense
                            clearable
                            v-model="paymentsTable.filter"
                            debounce="300"
                            placeholder="Search by tag, memo, amount"
                            class="q-mb-md"
                          >
                          </q-input>
                        </div>

                        <q-table
                          dense
                          flat
                          :rows="invoiceTable.data"
                          :columns="invoiceTable.columns"
                          v-model:pagination="invoiceTable.pagination"
                          no-data-label="No transactions made yet"
                          :filter="invoiceTable.filter"
                          @request="getInvoices"
                        >
                          <template v-slot:body-cell-pending="props">
                            <q-td auto-width class="text-center">
                              <q-icon
                                v-if="!props.row.pending"
                                size="xs"
                                name="call_received"
                                color="green"
                                @click="showTransactionDetailsDialog(props.row)"
                              ></q-icon>
                              <q-icon
                                v-else
                                size="xs"
                                name="settings_ethernet"
                                color="grey"
                                @click="showTransactionDetailsDialog(props.row)"
                              >
                                <q-tooltip>Pending</q-tooltip>
                              </q-icon>
                            </q-td>
                          </template>

                          <template v-slot:body-cell-paid_at="props">
                            <q-td auto-width :props="props">
                              <div v-if="props.row.paid_at">
                                <q-tooltip
                                  ><span
                                    v-text="
                                      utils.formatTimestamp(props.row.paid_at)
                                    "
                                  ></span
                                ></q-tooltip>
                                <span
                                  v-text="
                                    utils.formatTimestampFrom(props.row.paid_at)
                                  "
                                ></span>
                              </div>
                            </q-td>
                          </template>

                          <template v-slot:body-cell-expiry="props">
                            <q-td auto-width :props="props">
                              <div v-if="props.row.expiry">
                                <q-tooltip
                                  ><span
                                    v-text="
                                      utils.formatTimestamp(props.row.expiry)
                                    "
                                  ></span
                                ></q-tooltip>
                                <span
                                  v-text="
                                    utils.formatTimestampFrom(props.row.expiry)
                                  "
                                ></span>
                              </div>
                            </q-td>
                          </template>
                        </q-table>
                      </q-card-section>
                    </q-card>
                  </div>
                </div>
              </q-card-section>
            </q-tab-panel>
          </q-tab-panels>
        </q-form>
      </q-card>
    </div>
  </div>
</template>

<template id="page-node-public">
  <div
    v-if="!enabled"
    class="q-ma-lg-xl q-mx-auto q-ma-xl"
    style="max-width: 1048px"
  >
    <h2>Node public page not enabled.</h2>
  </div>
  <div
    v-if="enabled"
    class="q-ma-lg-xl q-mx-auto q-ma-xl"
    style="max-width: 1048px"
  >
    <lnbits-node-info :info="this.info"></lnbits-node-info>

    <div class="row q-col-gutter-lg q-mt-sm">
      <div class="col-12 col-md-8 q-gutter-y-md">
        <div class="row q-col-gutter-md q-pb-lg">
          <div class="col-12 col-md-6 q-gutter-y-md">
            <lnbits-stat
              :title="$t('total_capacity')"
              :msat="this.channel_stats.total_capacity"
            />
          </div>

          <div class="col-12 col-md-6 q-gutter-y-md">
            <lnbits-stat title="Peers" :amount="this.info.num_peers" />
          </div>
          <div class="col-12 col-md-6 q-gutter-y-md">
            <lnbits-stat
              :title="$t('avg_channel_size')"
              :msat="this.channel_stats.avg_size"
            />
          </div>
          <div class="col-12 col-md-6 q-gutter-y-md">
            <lnbits-stat
              :title="$t('biggest_channel_size')"
              :msat="this.channel_stats.biggest_size"
            />
          </div>
          <div class="col-12 col-md-6 q-gutter-y-md">
            <lnbits-stat
              :title="$t('smallest_channel_size')"
              :msat="this.channel_stats.smallest_size"
            />
          </div>
          <div class="col-12 col-md-6 q-gutter-y-md">
            <lnbits-stat
              :title="$t('smallest_channel_size')"
              :msat="this.channel_stats.smallest_size"
            />
          </div>
        </div>
      </div>
      <div class="column col-12 col-md-4 q-gutter-y-md">
        <lnbits-node-ranks :ranks="this.ranks"></lnbits-node-ranks>
        <lnbits-channel-stats
          :stats="this.channel_stats"
        ></lnbits-channel-stats>
      </div>
    </div>
  </div>
</template>
