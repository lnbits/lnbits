<template id="onchain-send-to">
  <div class="row items-center no-wrap q-mb-md">
    <div class="col-12">
      <q-table
        flat
        dense
        hide-header
        :rows="data"
        :columns="paymentTable.columns"
        v-model:pagination="paymentTable.pagination"
      >
        <template v-slot:body="props">
          <q-tr :props="props">
            <q-td colspan="100%">
              <div class="row items-start">
                <div class="col-1">
                  <q-btn
                    flat
                    dense
                    size="l"
                    @click="deletePaymentAddress(props.row)"
                    icon="cancel"
                    color="grey"
                    class="q-mt-sm"
                  ></q-btn>
                </div>
                <div class="col-11 col-sm-7 q-pr-sm">
                  <q-input
                    filled
                    dense
                    v-model.trim="props.row.address"
                    type="text"
                    label="Bitcoin address or payment link"
                    :error="!!props.row.error"
                    :error-message="props.row.error"
                    :rules="[val => !!val || $t('onchain.field_required')]"
                    @update:model-value="handleAddressInput(props.row)"
                    ><template v-slot:append
                      ><q-btn
                        flat
                        round
                        dense
                        icon="qr_code_scanner"
                        aria-label="Scan bitcoin address"
                        @click="scanAddress(props.row)"
                      ></q-btn></template
                  ></q-input>
                </div>
                <div class="col-9 col-sm-3 q-pr-sm">
                  <q-input
                    filled
                    dense
                    v-model.number="props.row.amount"
                    type="number"
                    step="1"
                    :label="$t('onchain.amount_sats')"
                    :rules="[
                      val => !!val || $t('onchain.field_required'),
                      val =>
                        (Number.isSafeInteger(+val) && +val >= DUST_LIMIT) ||
                        $t('onchain.amount_too_small')
                    ]"
                    @update:model-value="handleOutputsChange"
                  ></q-input>
                </div>
                <div class="col-3 col-sm-1">
                  <q-btn
                    outline
                    color="grey"
                    @click="sendMaxToAddress(props.row)"
                    :label="$t('onchain.max')"
                  ></q-btn>
                </div>
              </div>
            </q-td>
          </q-tr>
        </template>
      </q-table>
      <div class="row items-center no-wrap">
        <div class="col-auto q-pr-sm">
          <q-btn
            unelevated
            color="primary"
            @click="addPaymentAddress"
            class="full-width"
            :label="$t('onchain.add')"
          ></q-btn>
        </div>
        <div class="col">
          <div class="float-right">
            <span v-text="$t('onchain.payed_amount')"></span>
            <span
              class="text-subtitle2 q-ml-lg"
              v-text="satBtc(getTotalPaymentAmount())"
            ></span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
