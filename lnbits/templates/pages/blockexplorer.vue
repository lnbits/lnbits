<template id="page-blockexplorer">
  <div class="row q-col-gutter-md justify-center">
    <div class="col-12 col-md-8 q-gutter-y-md">
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
              <q-btn
                flat
                round
                dense
                icon="search"
                :loading="loading"
                @click="search"
              />
            </template>
          </q-input>
        </q-card-section>
      </q-card>

      <!-- Chain tip + fee summary -->
      <q-card v-if="tip">
        <q-card-section>
          <div class="text-subtitle1 q-mb-sm" v-text="$t('chain_tip')"></div>
          <div class="row q-col-gutter-md">
            <div class="col-auto">
              <div class="text-caption text-grey" v-text="$t('block_height')"></div>
              <div class="text-h6" v-text="tip.height.toLocaleString()"></div>
            </div>
            <template v-if="feeList.length">
              <div class="col-auto" v-for="f in feeList" :key="f.label">
                <div class="text-caption text-grey" v-text="f.label"></div>
                <div class="text-body2" v-text="f.rate"></div>
              </div>
            </template>
          </div>
        </q-card-section>
      </q-card>

      <!-- Transaction result -->
      <q-card v-if="txResult">
        <q-card-section>
          <div class="text-subtitle1 q-mb-sm" v-text="$t('transaction')"></div>
          <div class="q-mb-xs">
            <span class="text-caption text-grey">txid: </span>
            <code style="word-break: break-all" v-text="txResult.txid"></code>
          </div>
          <div class="row q-col-gutter-md q-mb-sm">
            <div class="col-auto" v-if="txResult.blockheight">
              <div class="text-caption text-grey" v-text="$t('block_height')"></div>
              <div v-text="txResult.blockheight.toLocaleString()"></div>
            </div>
            <div class="col-auto" v-if="txResult.confirmations !== undefined">
              <div class="text-caption text-grey" v-text="$t('confirmations')"></div>
              <div v-text="txResult.confirmations > 0 ? txResult.confirmations : $t('unconfirmed')"></div>
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
                  <q-item-label v-else style="word-break: break-all">
                    <a href="#" @click.prevent="loadTx(vin.txid)" class="text-primary" v-text="vin.txid + ':' + vin.vout"></a>
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
          <code class="q-mb-sm" style="word-break: break-all; display: block" v-text="currentAddress"></code>
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
          <div class="text-subtitle2 q-mb-xs" v-text="$t('transaction_history') + ' (' + addressResult.history.length + ')'"></div>
          <q-list dense separator>
            <q-item
              v-for="h in addressResult.history"
              :key="h.tx_hash"
              clickable
              v-ripple
              @click="loadTx(h.tx_hash)"
            >
              <q-item-section>
                <q-item-label class="text-primary" style="word-break: break-all" v-text="h.tx_hash"></q-item-label>
                <q-item-label caption v-text="h.height > 0 ? $t('block_height') + ': ' + h.height.toLocaleString() : $t('unconfirmed')"></q-item-label>
              </q-item-section>
              <q-item-section side>
                <q-icon name="chevron_right" color="grey-5"></q-icon>
              </q-item-section>
            </q-item>
          </q-list>
          <div v-if="addressResult.history.length === 0" class="text-grey q-mt-sm" v-text="$t('no_transactions')"></div>
        </q-card-section>
      </q-card>
    </div>
  </div>
</template>
