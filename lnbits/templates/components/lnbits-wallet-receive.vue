<template id="lnbits-wallet-receive">
  <lnbits-qrcode
    v-if="receive.fiatPaymentReq"
    :show-buttons="false"
    :href="receive.fiatPaymentReq"
    :value="receive.fiatPaymentReq"
  >
  </lnbits-qrcode>
  <lnbits-qrcode
    v-else
    :href="'lightning:' + receive.paymentReq"
    :value="'lightning:' + receive.paymentReq"
  >
  </lnbits-qrcode>
  <div class="text-center">
    <h3 class="q-my-md">
      <span v-text="formattedAmount"></span>
    </h3>
    <h5 v-if="receive.unit != 'sat'" class="q-mt-none q-mb-sm">
      <span v-text="formattedSatAmount"></span>
    </h5>
    <div v-if="!receive.fiatPaymentReq">
      <q-chip v-if="hasNfc" outline square color="positive">
        <q-avatar icon="nfc" color="positive" text-color="white"></q-avatar>
        <span v-text="$t('nfc_supported')"></span>
      </q-chip>
    </div>
  </div>
  <div class="row q-mt-lg">
    <q-btn
      v-close-popup
      flat
      color="grey"
      class="q-ml-auto"
      :label="$t('close')"
    ></q-btn>
  </div>
</template>
