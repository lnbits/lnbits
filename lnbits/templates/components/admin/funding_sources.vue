<template id="lnbits-admin-funding-sources">
  <div class="funding-sources">
    <h6 class="q-my-none q-mb-sm">
      <span v-text="$t('funding_sources')"></span>
      <q-btn
        round
        flat
        @click="this.hideInput = !this.hideInput"
        :icon="this.hideInput ? 'visibility_off' : 'visibility'"
      ></q-btn>
    </h6>

    <div class="row">
      <div class="col-12">
        <p>Active Funding<small> (Requires server restart)</small></p>
        <q-select
          filled
          v-model="formData.lnbits_backend_wallet_class"
          hint="Select the active funding wallet"
          :options="sortedAllowedFundingSources"
          :option-label="item => getFundingSourceLabel(item)"
        ></q-select>
      </div>
    </div>
    <q-list
      class="q-mt-md"
      v-for="(fund, idx) in allowedFundingSources"
      :key="idx"
    >
      <div
        v-if="
          fundingSources.get(fund) &&
          fund === formData.lnbits_backend_wallet_class
        "
      >
        <div
          class="row"
          v-for="([key, prop], i) in Object.entries(fundingSources.get(fund))"
          :key="i"
        >
          <div class="col-12">
            <q-input
              v-model="formData[key]"
              filled
              class="q-mt-sm"
              :type="hideInput ? 'password' : 'text'"
              :label="prop.label"
              :hint="prop.hint"
              :readonly="prop.readonly || false"
            >
              <q-btn
                v-if="prop.copy"
                @click="utils.copyText(formData[key])"
                icon="content_copy"
                class="cursor-pointer"
                color="grey"
                flat
                dense
              ></q-btn>
              <q-btn
                v-if="prop.qrcode"
                @click="showQRValue(formData[key])"
                icon="qr_code"
                class="cursor-pointer"
                color="grey"
                flat
                dense
              ></q-btn>
            </q-input>
          </div>
        </div>
      </div>
    </q-list>
    <q-dialog v-model="showQRDialog">
      <q-card class="q-pa-md">
        <q-card-section>
          <lnbits-qrcode :value="qrValue"></lnbits-qrcode>
        </q-card-section>
        <q-card-actions align="right">
          <q-btn flat :label="$t('close')" v-close-popup />
        </q-card-actions>
      </q-card>
    </q-dialog>
  </div>
</template>
