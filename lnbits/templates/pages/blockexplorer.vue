<template id="page-blockexplorer">
  <div class="row q-col-gutter-md">
    <div class="col-12">
      <div class="row items-start q-col-gutter-md">
        <div class="col-12 col-md">
          <div class="row items-center q-gutter-x-sm">
            <div class="text-h5" v-text="$t('block_explorer')"></div>
            <q-btn
              v-if="!g.isPublicPage && g.settings.blockExplorerPublic"
              type="a"
              href="/blockexplorer/public"
              target="_blank"
              rel="noopener noreferrer"
              outline
              dense
              color="primary"
              icon-right="open_in_new"
              :label="$t('public_page')"
            ></q-btn>
          </div>
        </div>
        <div class="col-12 col-md-6 col-lg-5">
          <q-input
            outlined
            dense
            clearable
            color="primary"
            class="be-search"
            v-model="query"
            :label="$t('blockexplorer_search_label')"
            @keyup.enter="search"
            @clear="clearResult"
          >
            <template v-slot:append>
              <q-btn
                flat
                round
                dense
                icon="search"
                :loading="loading"
                @click="search"
              ></q-btn>
            </template>
          </q-input>
        </div>
      </div>
    </div>

    <div v-if="recentBlocks.length" class="col-12">
      <div class="row items-center q-mb-sm">
        <div class="col">
          <q-badge color="primary" :label="$t('projected_blocks')"></q-badge>
        </div>
        <div class="col text-right">
          <q-badge
            color="secondary"
            :label="`${$t('chain_tip')} #${recentBlocks[0].height.toLocaleString()}`"
          ></q-badge>
        </div>
      </div>

      <div class="be-block-stream">
        <transition-group
          name="be-projected"
          tag="div"
          class="be-block-lane be-block-lane--projected"
        >
          <q-card
            v-for="block in projectedBlocksDisplay"
            :key="block.id"
            square
            class="be-block-cube be-block-cube--projected text-white column"
          >
            <q-card-section class="be-block-content full-height column q-pa-sm">
              <div class="row items-center justify-between no-wrap">
                <q-icon name="hourglass_top" size="xs"></q-icon>
                <div
                  class="text-caption ellipsis q-ml-xs"
                  v-text="block.label"
                ></div>
              </div>
              <q-space></q-space>
              <div
                class="text-subtitle2 text-weight-bold"
                v-text="`${block.feeRate.toFixed(1)} sat/vB`"
              ></div>
              <div
                class="text-caption"
                v-text="`${block.vsize.toFixed(2)} MvB`"
              ></div>
              <q-linear-progress
                :value="block.fill"
                color="white"
                track-color="transparent"
                class="q-mt-xs"
              ></q-linear-progress>
              <q-tooltip>
                <div v-text="$t('projected_block_desc')"></div>
                <div v-text="`${block.feeRate.toFixed(2)} sat/vB`"></div>
              </q-tooltip>
            </q-card-section>
          </q-card>
        </transition-group>

        <div class="be-block-boundary"></div>

        <transition-group
          name="be-confirmed"
          tag="div"
          class="be-block-lane be-block-lane--confirmed"
        >
          <q-card
            v-for="(b, index) in recentBlocks"
            :key="b.height"
            square
            class="be-block-cube be-block-cube--confirmed text-white cursor-pointer column"
            v-ripple
            @click="openBlock(b)"
          >
            <q-card-section class="be-block-content full-height column q-pa-sm">
              <div class="row items-center justify-between">
                <q-icon name="inventory_2" size="xs"></q-icon>
                <q-icon v-if="index === 0" name="fiber_new" size="xs"></q-icon>
              </div>
              <q-space></q-space>
              <div
                class="text-subtitle2 text-weight-bold"
                v-text="'#' + b.height.toLocaleString()"
              ></div>
              <div class="text-caption ellipsis" v-text="b.timeAgo"></div>
              <div
                v-if="b.intervalMinutes !== null"
                class="be-block-interval text-caption q-mt-xs"
                v-text="
                  $t('block_interval_short', {
                    minutes: b.intervalMinutes.toFixed(1)
                  })
                "
              ></div>
              <q-tooltip>
                <div v-if="index === 0" v-text="$t('latest')"></div>
                <div v-text="b.hash"></div>
                <div v-text="b.utcTime"></div>
                <div v-text="$t('block_diff', {value: b.difficulty})"></div>
              </q-tooltip>
            </q-card-section>
          </q-card>
        </transition-group>
      </div>
    </div>

    <div class="col-12 col-md-6 order-last">
      <q-card class="full-height">
        <q-card-section>
          <div class="row items-start justify-between q-mb-md">
            <div>
              <div class="text-subtitle1" v-text="$t('block_intervals')"></div>
              <div
                class="text-caption text-grey"
                v-text="$t('block_intervals_desc')"
              ></div>
            </div>
            <q-chip
              dense
              color="primary"
              text-color="white"
              icon="schedule"
              :label="averageBlockInterval"
            ></q-chip>
          </div>
          <canvas ref="blockIntervalChart"></canvas>
        </q-card-section>
      </q-card>
    </div>

    <div class="col-12 col-md-6 order-last">
      <q-card class="full-height">
        <q-card-section>
          <div class="q-mb-sm">
            <div class="row items-center justify-between">
              <div
                class="text-subtitle1"
                v-text="$t('mempool_fee_distribution')"
              ></div>
              <div class="row items-center q-gutter-x-xs">
                <q-chip
                  v-if="tip"
                  dense
                  color="primary"
                  text-color="white"
                  icon="account_tree"
                  :label="`${$t('block_height')} ${tip.height.toLocaleString()}`"
                ></q-chip>
                <q-chip
                  dense
                  color="secondary"
                  text-color="white"
                  icon="data_usage"
                  :label="mempoolSize"
                >
                  <q-tooltip v-text="$t('mempool_virtual_size')"></q-tooltip>
                </q-chip>
              </div>
            </div>
            <div v-if="feeList.length" class="row items-center q-gutter-x-md">
              <div
                class="text-caption text-grey"
                v-text="$t('fee_estimates')"
              ></div>
              <div
                v-for="f in feeList"
                :key="f.label"
                class="text-caption no-wrap"
              >
                <span class="text-grey" v-text="f.label"></span>
                <span class="q-ml-xs text-weight-medium" v-text="f.rate"></span>
              </div>
            </div>
          </div>
          <canvas ref="mempoolChart"></canvas>
        </q-card-section>
      </q-card>
    </div>

    <!-- Search results -->
    <div
      v-if="selectedBlock || txResult || addressResult"
      class="col-12 q-gutter-y-md"
    >
      <!-- Block detail -->
      <q-card v-if="selectedBlock">
        <q-card-section>
          <div class="row items-center justify-between no-wrap">
            <div class="row items-center no-wrap q-gutter-x-sm">
              <q-icon name="inventory_2" color="primary" size="sm"></q-icon>
              <div>
                <div
                  class="text-h6"
                  v-text="
                    $t('block_number', {
                      height: selectedBlock.height.toLocaleString()
                    })
                  "
                ></div>
                <div
                  class="text-caption text-grey"
                  v-text="selectedBlock.utcTime"
                ></div>
              </div>
            </div>
            <q-btn
              flat
              round
              dense
              icon="close"
              :aria-label="$t('close')"
              @click="closeBlock"
            ></q-btn>
          </div>
        </q-card-section>
        <q-separator></q-separator>
        <q-card-section class="row q-col-gutter-lg q-pb-lg">
          <div class="col-12 col-md-6">
            <div class="text-caption text-grey" v-text="$t('block_hash')"></div>
            <code
              class="text-caption be-wrap"
              v-text="selectedBlock.hash"
            ></code>
          </div>
          <div class="col-12 col-md-6">
            <div
              class="text-caption text-grey"
              v-text="$t('previous_block')"
            ></div>
            <code
              class="text-caption be-wrap"
              v-text="selectedBlock.prev_hash"
            ></code>
          </div>
          <div class="col-12 col-md-6">
            <div
              class="text-caption text-grey"
              v-text="$t('merkle_root')"
            ></div>
            <code
              class="text-caption be-wrap"
              v-text="selectedBlock.merkle_root"
            ></code>
          </div>
          <div class="col-6 col-sm-3 col-md-1">
            <div class="text-caption text-grey" v-text="$t('version')"></div>
            <div v-text="'0x' + selectedBlock.version.toString(16)"></div>
          </div>
          <div class="col-6 col-sm-3 col-md-1">
            <div class="text-caption text-grey" v-text="$t('bits')"></div>
            <div v-text="selectedBlock.bits"></div>
          </div>
          <div class="col-6 col-sm-3 col-md-2">
            <div class="text-caption text-grey" v-text="$t('difficulty')"></div>
            <div v-text="selectedBlock.difficulty"></div>
          </div>
          <div class="col-6 col-sm-3 col-md-2">
            <div class="text-caption text-grey" v-text="$t('nonce')"></div>
            <div v-text="selectedBlock.nonce.toLocaleString()"></div>
          </div>
        </q-card-section>
        <q-separator></q-separator>
        <q-card-section>
          <div class="row items-center justify-between q-mb-sm">
            <div class="text-subtitle1" v-text="$t('transactions')"></div>
            <q-spinner
              v-if="blockTransactionsLoading"
              color="primary"
              size="sm"
            ></q-spinner>
          </div>
          <q-banner
            v-if="blockTransactionsError"
            dense
            class="bg-grey-9 text-white"
            v-text="blockTransactionsError"
          ></q-banner>
          <q-list v-else-if="blockTransactions.length" bordered separator>
            <q-item
              v-for="transaction in blockTransactions"
              :key="transaction.txid"
              clickable
              v-ripple
              @click="loadTx(transaction.txid)"
            >
              <q-item-section avatar>
                <q-icon name="receipt_long" color="primary"></q-icon>
              </q-item-section>
              <q-item-section>
                <q-item-label
                  v-text="
                    $t('transaction_position', {
                      position: transaction.position + 1
                    })
                  "
                ></q-item-label>
                <q-item-label caption class="be-wrap" v-text="transaction.txid">
                </q-item-label>
              </q-item-section>
              <q-item-section side>
                <q-icon name="chevron_right"></q-icon>
              </q-item-section>
            </q-item>
          </q-list>
          <div
            v-else-if="!blockTransactionsLoading"
            class="text-caption text-grey"
            v-text="$t('no_transactions')"
          ></div>
          <div
            v-if="
              !blockTransactionsError &&
              (blockTransactionsOffset > 0 || blockTransactionsHasMore)
            "
            class="row justify-end q-gutter-sm q-mt-md"
          >
            <q-btn
              outline
              dense
              color="primary"
              icon="chevron_left"
              :label="$t('previous_page')"
              :disable="
                blockTransactionsOffset === 0 || blockTransactionsLoading
              "
              @click="previousBlockTransactions"
            ></q-btn>
            <q-btn
              outline
              dense
              color="primary"
              icon-right="chevron_right"
              :label="$t('next_page')"
              :disable="!blockTransactionsHasMore || blockTransactionsLoading"
              @click="nextBlockTransactions"
            ></q-btn>
          </div>
        </q-card-section>
      </q-card>

      <!-- Transaction result -->
      <q-card v-if="txResult">
        <q-card-section>
          <div class="row items-center justify-between q-mb-sm">
            <div class="row items-center q-gutter-sm">
              <div class="text-subtitle1" v-text="$t('transaction')"></div>
              <q-badge
                v-if="txStatus"
                :color="txStatus.confirmed ? 'positive' : 'orange'"
                :label="
                  txStatus.confirmed ? $t('confirmed') : $t('unconfirmed')
                "
              ></q-badge>
              <q-spinner v-if="!txStatus" size="1em" color="grey" />
            </div>
            <q-btn flat round dense icon="close" @click="clearResult" />
          </div>
          <div class="q-mb-sm">
            <span
              class="text-caption text-grey"
              v-text="$t('txid') + ': '"
            ></span>
            <code class="text-caption be-wrap" v-text="txResult.txid"></code>
          </div>
          <div class="row q-col-gutter-md q-mb-sm">
            <div class="col-auto" v-if="txStatus && txStatus.height">
              <div
                class="text-caption text-grey"
                v-text="$t('block_height')"
              ></div>
              <div v-text="txStatus.height.toLocaleString()"></div>
            </div>
            <div class="col-auto" v-if="txStatus && txStatus.fee !== null">
              <div class="text-caption text-grey" v-text="$t('fee')"></div>
              <div v-text="txStatus.fee + ' sat'"></div>
            </div>
            <div class="col-auto" v-if="txResult.vsize || txResult.size">
              <div class="text-caption text-grey" v-text="$t('vsize')"></div>
              <div v-text="(txResult.vsize || txResult.size) + ' vB'"></div>
            </div>
            <div class="col-auto" v-if="txResult.weight">
              <div class="text-caption text-grey" v-text="$t('weight')"></div>
              <div v-text="txResult.weight + ' WU'"></div>
            </div>
          </div>
          <q-expansion-item
            icon="login"
            :label="$t('inputs') + ' (' + txResult.vin.length + ')'"
            dense
            class="q-mb-xs"
          >
            <q-list dense separator>
              <q-item v-for="(vin, i) in txResult.vin" :key="i">
                <q-item-section>
                  <q-item-label
                    v-if="vin.coinbase"
                    class="text-grey"
                    v-text="$t('coinbase')"
                  >
                  </q-item-label>
                  <q-item-label v-else class="be-wrap">
                    <a
                      href="#"
                      @click.prevent="loadTx(vin.txid)"
                      class="text-primary"
                      v-text="vin.txid + ':' + vin.vout"
                    ></a>
                  </q-item-label>
                </q-item-section>
              </q-item>
            </q-list>
          </q-expansion-item>
          <q-expansion-item
            icon="logout"
            :label="$t('outputs') + ' (' + txResult.vout.length + ')'"
            dense
          >
            <q-list dense separator>
              <q-item v-for="(vout, i) in txResult.vout" :key="i">
                <q-item-section>
                  <q-item-label>
                    <template
                      v-if="vout.scriptPubKey && vout.scriptPubKey.address"
                    >
                      <a
                        href="#"
                        @click.prevent="loadAddress(vout.scriptPubKey.address)"
                        class="text-primary"
                        v-text="vout.scriptPubKey.address"
                      ></a>
                    </template>
                    <template
                      v-else-if="
                        vout.scriptPubKey &&
                        vout.scriptPubKey.type === 'nulldata'
                      "
                    >
                      <span class="text-grey">OP_RETURN</span>
                    </template>
                    <template v-else-if="vout.scriptPubKey">
                      <span v-text="vout.scriptPubKey.type"></span>
                    </template>
                  </q-item-label>
                  <q-item-label
                    caption
                    v-text="vout.value + ' BTC'"
                  ></q-item-label>
                </q-item-section>
              </q-item>
            </q-list>
          </q-expansion-item>
        </q-card-section>
      </q-card>

      <!-- Address result -->
      <q-card v-if="addressResult">
        <q-card-section>
          <div class="row items-center justify-between q-mb-xs">
            <div class="text-subtitle1" v-text="$t('address')"></div>
            <q-btn flat round dense icon="close" @click="clearResult" />
          </div>
          <div class="text-caption q-mb-sm">
            <code class="be-wrap" v-text="currentAddress"></code>
          </div>
          <div class="row q-col-gutter-md q-mb-md">
            <div class="col-auto">
              <div
                class="text-caption text-grey"
                v-text="$t('confirmed_balance')"
              ></div>
              <div
                v-text="
                  addressResult.balance.confirmed.toLocaleString() + ' sat'
                "
              ></div>
            </div>
            <div
              class="col-auto"
              v-if="addressResult.balance.unconfirmed !== 0"
            >
              <div
                class="text-caption text-grey"
                v-text="$t('unconfirmed_balance')"
              ></div>
              <div
                v-text="
                  addressResult.balance.unconfirmed.toLocaleString() + ' sat'
                "
              ></div>
            </div>
          </div>
          <div
            class="text-subtitle2 q-mb-xs"
            v-text="
              $t('transaction_history') + ' (' + addressHistory.length + ')'
            "
          ></div>
          <q-list dense separator>
            <q-item
              v-for="h in paginatedAddressHistory"
              :key="h.tx_hash"
              clickable
              v-ripple
              @click="loadTx(h.tx_hash)"
            >
              <q-item-section>
                <q-item-label
                  class="text-primary be-wrap"
                  v-text="h.tx_hash"
                ></q-item-label>
                <q-item-label
                  caption
                  v-text="
                    h.height > 0
                      ? $t('block_height') + ': ' + h.height.toLocaleString()
                      : $t('unconfirmed')
                  "
                ></q-item-label>
              </q-item-section>
              <q-item-section side>
                <q-icon name="chevron_right" color="grey-5"></q-icon>
              </q-item-section>
            </q-item>
          </q-list>
          <div
            v-if="addressResult.history_error"
            class="text-warning q-mt-sm text-caption"
            v-text="$t('history_unavailable')"
          ></div>
          <div
            v-else-if="addressHistory.length === 0"
            class="text-grey q-mt-sm"
            v-text="$t('no_transactions')"
          ></div>
          <div
            v-if="addressHistoryPages > 1"
            class="row items-center justify-between q-gutter-sm q-mt-md"
          >
            <div
              class="text-caption text-grey"
              v-text="addressHistoryRange"
            ></div>
            <q-pagination
              v-model="addressHistoryPage"
              :max="addressHistoryPages"
              :max-pages="$q.screen.lt.sm ? 5 : 9"
              boundary-numbers
              direction-links
              color="primary"
              size="sm"
            ></q-pagination>
          </div>
        </q-card-section>
      </q-card>
    </div>
  </div>
</template>

<style>
.be-wrap {
  word-break: break-all;
}

.be-search.q-field--outlined .q-field__control::before {
  border-color: var(--q-primary);
}

.be-block-stream {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 28px minmax(0, 1fr);
  align-items: end;
  overflow: hidden;
}

.be-block-lane {
  position: relative;
  display: flex;
  align-items: flex-end;
  gap: 14px;
  min-width: 0;
  min-height: 150px;
  padding: 20px 12px 8px;
  overflow: hidden;
}

.be-block-lane--projected {
  justify-content: flex-end;
}

.be-block-lane--confirmed {
  justify-content: flex-start;
}

.be-block-boundary {
  position: relative;
  justify-self: center;
  width: 1px;
  height: 142px;
  margin-bottom: 8px;
  border-left: 2px dotted var(--q-primary);
}

.be-block-cube {
  --be-block-color: var(--q-secondary);
  position: relative;
  flex: 0 0 104px;
  width: 104px;
  height: 122px;
  overflow: visible;
  color: white;
  background: var(--be-block-color);
  border: 0 !important;
  border-radius: 0 !important;
  box-shadow: none !important;
  transition:
    transform 180ms ease,
    filter 180ms ease;
}

.be-block-cube--projected {
  --be-block-color: var(--q-primary);
}

.be-block-cube--confirmed {
  --be-block-color: var(--q-secondary);
}

.be-block-cube::before {
  position: absolute;
  top: -14px;
  left: -10px;
  width: calc(100% + 10px);
  height: 14px;
  content: '';
  background: var(--be-block-color);
  filter: brightness(0.66);
  clip-path: polygon(0 0, calc(100% - 14px) 0, 100% 100%, 10px 100%);
}

.be-block-cube::after {
  position: absolute;
  top: -14px;
  left: -10px;
  width: 10px;
  height: calc(100% + 14px);
  content: '';
  background: var(--be-block-color);
  filter: brightness(0.35);
  clip-path: polygon(0 0, 100% 14px, 100% 100%, 0 calc(100% - 14px));
}

.be-block-content {
  position: relative;
  z-index: 1;
  box-sizing: border-box;
  min-width: 0;
  max-width: 100%;
  overflow: hidden;
}

.be-block-interval {
  max-width: 100%;
  line-height: 1.2;
  overflow-wrap: anywhere;
}

.be-block-cube:hover {
  z-index: 2;
  filter: brightness(1.08);
  transform: translateY(-3px);
}

.be-confirmed-enter-active,
.be-confirmed-leave-active,
.be-confirmed-move,
.be-projected-enter-active,
.be-projected-leave-active,
.be-projected-move {
  transition:
    opacity 420ms ease,
    transform 520ms ease;
}

.be-confirmed-enter-from {
  opacity: 0;
  transform: translateX(-118px);
}

.be-confirmed-leave-to {
  opacity: 0;
  transform: translateX(118px);
}

.be-projected-enter-from {
  opacity: 0;
  transform: translateX(-118px);
}

.be-projected-leave-to {
  opacity: 0;
  transform: translateX(118px);
}

.be-confirmed-leave-active,
.be-projected-leave-active {
  position: absolute;
}

@media (max-width: 599px) {
  .be-block-stream {
    grid-template-columns: minmax(0, 1fr) 20px minmax(0, 1fr);
  }

  .be-block-lane {
    gap: 12px;
    padding-right: 8px;
    padding-left: 8px;
  }

  .be-block-cube {
    flex-basis: 92px;
    width: 92px;
    height: 116px;
  }
}
</style>
