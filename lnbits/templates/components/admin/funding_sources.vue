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
        <p>
          <span v-text="$t('funding_source')"></span>
          <small><span v-text="$t('requires_server_restart')"></span></small>
        </p>
        <q-select
          filled
          v-model="formData.lnbits_backend_wallet_class"
          :hint="$t('funding_source_info')"
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
          v-for="([key, prop], i) in Object.entries(
            fundingSources.get(fund)
          ).filter(([, p]) => !p.advanced)"
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
              :value="prop.value"
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
        <q-expansion-item
          v-if="
            Object.entries(fundingSources.get(fund)).some(([, p]) => p.advanced)
          "
          dense
          expand-separator
          icon="tune"
          label="Advanced"
          class="q-mt-sm"
        >
          <div
            class="row"
            v-for="([key, prop], i) in Object.entries(
              fundingSources.get(fund)
            ).filter(([, p]) => p.advanced)"
            :key="`adv-${i}`"
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
        </q-expansion-item>
      </div>
    </q-list>
    <lnbits-dialog
      :show="showQRDialog"
      :position="'standard'"
      @update:show="showQRDialog = $event"
    >
      <q-card-section>
        <lnbits-qrcode :value="qrValue"></lnbits-qrcode>
      </q-card-section>
    </lnbits-dialog>
  </div>
</template>
