<template id="page-blockexplorer">
  <div class="row q-col-gutter-md">

    <!-- Left column: blocks + search + results -->
    <div class="col-12 col-md-7 q-gutter-y-md">

      <!-- Recent blocks (mempool-style squares) -->
      <q-card v-if="blocks.length">
        <q-card-section>
          <div class="text-subtitle1 q-mb-md" v-text="$t('recent_blocks')"></div>
          <div class="row q-gutter-sm">
            <q-card
              v-for="b in formattedBlocks"
              :key="b.height"
              flat
              class="bg-primary text-white cursor-pointer"
              v-ripple
              @click="openBlock(b)"
            >
              <q-card-section class="q-pa-sm">
                <div class="text-subtitle1 text-weight-bold" v-text="'#' + b.height.toLocaleString()"></div>
                <div class="text-caption q-mt-xs" v-text="b.timeAgo"></div>
                <div class="text-caption q-mt-sm"><code v-text="b.shortHash"></code></div>
                <div class="text-caption" v-text="'diff ' + b.difficulty"></div>
              </q-card-section>
            </q-card>
          </div>
        </q-card-section>
      </q-card>

      <!-- Block detail dialog -->
      <q-dialog v-model="blockDialog">
        <q-card v-if="selectedBlock">
          <q-card-section class="bg-primary text-white q-pb-sm">
            <div class="text-h6" v-text="'Block #' + selectedBlock.height.toLocaleString()"></div>
            <div class="text-caption" v-text="selectedBlock.utcTime"></div>
          </q-card-section>
          <q-card-section>
            <div class="q-mb-md">
              <div class="text-caption text-grey q-mb-xs">Hash</div>
              <code class="text-caption be-wrap" v-text="selectedBlock.hash"></code>
            </div>
            <div class="q-mb-md">
              <div class="text-caption text-grey q-mb-xs">Previous block</div>
              <code class="text-caption be-wrap" v-text="selectedBlock.prev_hash"></code>
            </div>
            <div class="q-mb-lg">
              <div class="text-caption text-grey q-mb-xs">Merkle root</div>
              <code class="text-caption be-wrap" v-text="selectedBlock.merkle_root"></code>
            </div>
            <div class="row q-col-gutter-md">
              <div class="col-6 col-sm-3">
                <div class="text-caption text-grey">Version</div>
                <div v-text="'0x' + selectedBlock.version.toString(16)"></div>
              </div>
              <div class="col-6 col-sm-3">
                <div class="text-caption text-grey">Bits</div>
                <div v-text="selectedBlock.bits"></div>
              </div>
              <div class="col-6 col-sm-3">
                <div class="text-caption text-grey">Difficulty</div>
                <div v-text="selectedBlock.difficulty"></div>
              </div>
              <div class="col-6 col-sm-3">
                <div class="text-caption text-grey">Nonce</div>
                <div v-text="selectedBlock.nonce.toLocaleString()"></div>
              </div>
            </div>
          </q-card-section>
          <q-card-actions align="right">
            <q-btn flat v-close-popup v-text="$t('close')"></q-btn>
          </q-card-actions>
        </q-card>
      </q-dialog>

      <q-card>
        <q-card-section>
          <div class="text-h6" v-text="$t('block_explorer')"></div>
        </q-card-section>
        <q-card-section class="q-pt-none">
          <q-input
            filled
            v-model="query"
            :label="$t('blockexplorer_search_label')"
            :hint="$t('blockexplorer_search_hint')"
            @keyup.enter="search"
          >
            <template v-slot:append>
              <q-btn flat round dense icon="search" :loading="loading" @click="search" />
            </template>
          </q-input>
        </q-card-section>
      </q-card>

      <!-- Transaction result -->
      <q-card v-if="txResult">
        <q-card-section>
          <div class="text-subtitle1 q-mb-sm" v-text="$t('transaction')"></div>
          <div class="q-mb-xs">
            <span class="text-caption text-grey">txid: </span>
            <code class="text-caption be-wrap" v-text="txResult.txid"></code>
          </div>
          <div class="row q-col-gutter-md q-mb-sm">
            <div class="col-auto" v-if="txResult.blockheight">
              <div class="text-caption text-grey" v-text="$t('block_height')"></div>
              <div v-text="txResult.blockheight.toLocaleString()"></div>
            </div>
            <div class="col-auto" v-if="txResult.confirmations !== undefined">
              <div class="text-caption text-grey" v-text="$t('confirmations')"></div>
              <div
                v-text="txResult.confirmations > 0 ? txResult.confirmations : $t('unconfirmed')"
              ></div>
            </div>
            <div class="col-auto" v-if="txResult.vsize || txResult.size">
              <div class="text-caption text-grey">vsize</div>
              <div v-text="(txResult.vsize || txResult.size) + ' vB'"></div>
            </div>
            <div class="col-auto" v-if="txResult.fee !== undefined">
              <div class="text-caption text-grey">fee</div>
              <div v-text="txResult.fee + ' sat'"></div>
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
                  <q-item-label v-if="vin.coinbase" class="text-grey" v-text="$t('coinbase')">
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
                    <template v-if="vout.scriptPubKey && vout.scriptPubKey.address">
                      <a
                        href="#"
                        @click.prevent="loadAddress(vout.scriptPubKey.address)"
                        class="text-primary"
                        v-text="vout.scriptPubKey.address"
                      ></a>
                    </template>
                    <template v-else-if="vout.scriptPubKey">
                      <span v-text="vout.scriptPubKey.type"></span>
                    </template>
                  </q-item-label>
                  <q-item-label caption v-text="vout.value + ' BTC'"></q-item-label>
                </q-item-section>
              </q-item>
            </q-list>
          </q-expansion-item>
        </q-card-section>
      </q-card>

      <!-- Address result -->
      <q-card v-if="addressResult">
        <q-card-section>
          <div class="text-subtitle1 q-mb-xs" v-text="$t('address')"></div>
          <div class="text-caption q-mb-sm"><code class="be-wrap" v-text="currentAddress"></code></div>
          <div class="row q-col-gutter-md q-mb-md">
            <div class="col-auto">
              <div class="text-caption text-grey" v-text="$t('confirmed_balance')"></div>
              <div v-text="addressResult.balance.confirmed.toLocaleString() + ' sat'"></div>
            </div>
            <div class="col-auto" v-if="addressResult.balance.unconfirmed !== 0">
              <div class="text-caption text-grey" v-text="$t('unconfirmed_balance')"></div>
              <div v-text="addressResult.balance.unconfirmed.toLocaleString() + ' sat'"></div>
            </div>
          </div>
          <div
            class="text-subtitle2 q-mb-xs"
            v-text="$t('transaction_history') + ' (' + addressResult.history.length + ')'"
          ></div>
          <q-list dense separator>
            <q-item
              v-for="h in addressResult.history"
              :key="h.tx_hash"
              clickable
              v-ripple
              @click="loadTx(h.tx_hash)"
            >
              <q-item-section>
                <q-item-label class="text-primary be-wrap" v-text="h.tx_hash"></q-item-label>
                <q-item-label
                  caption
                  v-text="h.height > 0 ? $t('block_height') + ': ' + h.height.toLocaleString() : $t('unconfirmed')"
                ></q-item-label>
              </q-item-section>
              <q-item-section side>
                <q-icon name="chevron_right" color="grey-5"></q-icon>
              </q-item-section>
            </q-item>
          </q-list>
          <div
            v-if="addressResult.history.length === 0"
            class="text-grey q-mt-sm"
            v-text="$t('no_transactions')"
          ></div>
        </q-card-section>
      </q-card>
    </div>

    <!-- Right column: chain tip + fees -->
    <div class="col-12 col-md-5 q-gutter-y-md">
      <q-card v-if="tip">
        <q-card-section>
          <div class="text-subtitle1 q-mb-sm" v-text="$t('chain_tip')"></div>
          <div class="text-caption text-grey" v-text="$t('block_height')"></div>
          <div class="text-h6 q-mb-md" v-text="tip.height.toLocaleString()"></div>
          <template v-if="feeList.length">
            <div class="text-subtitle2 q-mb-sm" v-text="$t('fee_estimates')"></div>
            <q-list dense>
              <q-item v-for="f in feeList" :key="f.label" class="q-px-none">
                <q-item-section>
                  <q-item-label class="text-caption text-grey" v-text="f.label"></q-item-label>
                </q-item-section>
                <q-item-section side>
                  <q-item-label class="text-body2" v-text="f.rate"></q-item-label>
                </q-item-section>
              </q-item>
            </q-list>
          </template>
        </q-card-section>
      </q-card>
    </div>

  </div>
</template>

<style>
.be-wrap { word-break: break-all; }
</style>
