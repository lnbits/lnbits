<template id="onchain-payment">
  <div>
    <q-form @submit="checkAndSend" ref="paymentFormRef" class="q-gutter-y-md">
      <fieldset
        :disabled="showChecking"
        style="border: 0; padding: 0; margin: 0; min-width: 0"
      >
        <q-card class="q-mt-lg">
          <q-card-section>
            <onchain-send-to
              v-model:data="sendToList"
              :fee-rate="feeRate"
              :tx-size="txSize"
              :selected-amount="selectedAmount"
              :sats-denominated="satsDenominated"
              @update:outputs="handleOutputsChange"
              @send-max="sendMaximum"
            ></onchain-send-to>
          </q-card-section>
        </q-card>

        <q-card class="q-mt-lg">
          <q-card-section>
            <div class="row items-center">
              <div class="col-12 col-sm-4">
                <q-toggle
                  :label="$t('onchain.show_custom_fee')"
                  color="primary"
                  class="float-left"
                  v-model="showCustomFee"
                ></q-toggle>
              </div>

              <div class="col-12 col-sm-8">
                <div class="float-right">
                  <span v-text="$t('onchain.fee_rate_label')"></span>
                  <span class="text-subtitle2 q-ml-md">
                    <span v-text="feeRate"></span> sats/vbyte</span
                  >
                  <span class="q-ml-lg" v-text="$t('onchain.fee_label')"></span>
                  <span
                    class="text-subtitle2 q-ml-md"
                    v-text="satBtc(feeValue)"
                  ></span>
                </div>
              </div>
            </div>

            <div
              v-show="showCustomFee"
              class="row items-center no-wrap q-mt-md"
            >
              <div class="col-12">
                <q-separator class="q-mb-md"></q-separator>
                <onchain-fee-rate
                  :fee-value="feeValue"
                  v-model:rate="feeRate"
                  :mempool-endpoint="mempoolEndpoint"
                  :sats-denominated="satsDenominated"
                ></onchain-fee-rate>
              </div>
            </div>
          </q-card-section>
        </q-card>

        <q-card class="q-mt-lg">
          <q-card-section>
            <div class="row items-center">
              <div class="col-12 col-sm-4">
                <q-toggle
                  :label="$t('onchain.show_coin_select')"
                  color="primary"
                  class="float-left"
                  v-model="showCoinSelect"
                ></q-toggle>
              </div>

              <div class="col-12 col-sm-8">
                <div class="float-right">
                  <span v-text="$t('onchain.balance_label')"></span>
                  <span
                    class="text-subtitle2 q-ml-md"
                    v-text="satBtc(balance)"
                  ></span>
                  <span
                    class="q-ml-lg"
                    v-text="$t('onchain.selected_label')"
                  ></span>
                  <span
                    class="text-subtitle2 q-ml-md"
                    v-text="satBtc(selectedAmount)"
                  ></span>
                </div>
              </div>
            </div>

            <div
              v-show="showCoinSelect"
              class="row items-center no-wrap q-mt-md"
            >
              <div class="col-12">
                <q-separator class="q-mb-md"></q-separator>
                <onchain-utxo-list
                  ref="utxoList"
                  :utxos="utxos"
                  :selectable="true"
                  :payed-amount="totalPayedAmount"
                  :mempool-endpoint="mempoolEndpoint"
                  :sats-denominated="satsDenominated"
                ></onchain-utxo-list>
              </div>
            </div>
          </q-card-section>
        </q-card>

        <q-card class="q-mt-lg">
          <q-card-section>
            <div class="row items-center">
              <div class="col-12 col-sm-4">
                <q-toggle
                  :label="$t('onchain.show_change')"
                  color="primary"
                  class="float-left"
                  v-model="showChange"
                ></q-toggle>
              </div>

              <div class="col-12 col-sm-4">
                <q-badge
                  v-if="changeAmount > 0 && changeAmount < DUST_LIMIT"
                  class="text-subtitle2 float-right"
                  color="yellow"
                  text-color="black"
                  v-text="$t('onchain.below_dust_limit_warning')"
                >
                </q-badge>
              </div>
              <div class="col-12 col-sm-4">
                <div class="float-right">
                  <span v-text="$t('onchain.change_label')"></span>
                  <span
                    v-if="changeAmount < 0"
                    class="text-subtitle2 q-ml-md"
                    v-text="satBtc(0)"
                  ></span>
                  <span
                    v-if="changeAmount >= 0"
                    class="text-subtitle2 q-ml-md"
                    v-text="satBtc(changeAmount)"
                  ></span>
                </div>
              </div>
            </div>

            <div v-show="showChange" class="row items-center no-wrap q-mt-md">
              <div class="col-12">
                <q-separator class="q-mb-md"></q-separator>
                <div class="row items-center">
                  <div
                    class="col-12 col-sm-2 q-pr-sm"
                    v-text="$t('onchain.change_account')"
                  ></div>
                  <div class="col-12 col-sm-3 q-pr-sm">
                    <q-select
                      filled
                      dense
                      emit-value
                      v-model="changeWallet"
                      :options="accounts"
                      @update:model-value="selectChangeAddress"
                      :rules="[val => !!val || $t('onchain.field_required')]"
                      :label="$t('onchain.wallet_account')"
                    ></q-select>
                  </div>
                  <div class="col-12 col-sm-7">
                    <q-input
                      filled
                      dense
                      readonly
                      v-model.trim="changeAddress.address"
                      :rules="[val => !!val || $t('onchain.field_required')]"
                      type="text"
                      :label="$t('onchain.change_address')"
                    ></q-input>
                  </div>
                </div>
              </div>
            </div>
          </q-card-section>
        </q-card>

        <div class="row items-center no-wrap q-mb-md q-pt-lg">
          <div class="col-auto">
            <q-btn
              unelevated
              color="primary"
              :disable="!canReview || showChecking"
              :loading="showChecking"
              :label="isHotWallet ? 'Review payment' : 'Sign with device'"
              @click="checkAndSend"
            ></q-btn>
            <q-btn
              v-if="!isHotWallet"
              flat
              label="Export PSBT"
              :disable="!canReview || showChecking"
              @click="showPsbtDialog"
              class="q-ml-sm"
            ></q-btn>
          </div>

          <div class="col">
            <q-spinner
              v-if="showChecking"
              size="2.55em"
              color="primary"
            ></q-spinner>
            <q-badge
              v-if="changeAmount < 0"
              class="text-subtitle2 float-right"
              color="yellow"
              text-color="black"
              v-text="$t('onchain.payed_amount_higher_warning')"
            >
            </q-badge>
          </div>
        </div>
      </fieldset>
    </q-form>
    <q-dialog v-model="showPsbt" position="top">
      <q-card class="q-pa-lg q-pt-xl">
        <q-input
          filled
          dense
          v-model.trim="psbtBase64"
          type="textarea"
          rows="25"
          cols="200"
          :label="$t('onchain.psbt_label')"
        ></q-input>

        <div class="row q-mt-lg">
          <q-btn
            v-close-popup
            flat
            color="grey"
            class="q-ml-auto"
            :label="$t('onchain.close')"
          ></q-btn>
        </div>
      </q-card>
    </q-dialog>

    <q-dialog v-model="showFinalTx" :persistent="showChecking" position="top">
      <q-card class="lnbits__dialog-card q-pa-lg">
        <h2 class="text-h6 q-mt-none">Review payment</h2>
        <p>
          Check the address and amount before sending on
          <span v-text="network === 'Testnet' ? 'Testnet3' : network"></span>.
          Bitcoin payments cannot be reversed.
        </p>
        <template v-if="signedTx">
          <div
            v-for="(out, index) in signedTx.outputs"
            :key="index"
            class="q-py-md"
          >
            <div class="row items-center">
              <div
                class="col text-subtitle2"
                v-text="
                  addresses.some(a => a.address === out.address && a.isChange)
                    ? 'Change back to your wallet'
                    : 'Recipient'
                "
              ></div>
              <strong v-text="satBtc(out.amount)"></strong>
            </div>
            <code class="block text-wrap q-mt-xs" v-text="out.address"></code>
          </div>
          <q-separator></q-separator>
          <div class="row q-my-md">
            <span class="col">Network fee</span
            ><strong v-text="satBtc(signedTx.fee)"></strong>
          </div>
          <q-expansion-item label="Transaction details" dense>
            <q-input
              filled
              readonly
              :model-value="signedTxHex"
              type="textarea"
              rows="3"
              label="Signed transaction"
            ></q-input>
          </q-expansion-item>
        </template>
        <div class="row q-mt-lg">
          <q-btn
            unelevated
            color="primary"
            label="Confirm and send"
            :loading="showChecking"
            :disable="!signedTxHex || showChecking"
            @click="broadcastTransaction"
          ></q-btn
          ><q-btn
            flat
            label="Back"
            class="q-ml-auto"
            v-close-popup
            :disable="showChecking"
          ></q-btn>
        </div>
      </q-card>
    </q-dialog>
  </div>
</template>
