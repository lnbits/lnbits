<template id="page-wallet">
  <div class="row q-col-gutter-md" style="margin-bottom: 6rem">
    <div class="col-12 col-md-7 q-gutter-y-md">
      <lnbits-wallet-header></lnbits-wallet-header>
      <q-card style="lnbits-wallet-payment-list">
        <q-card-section>
          <payment-list
            @filter-changed="handleFilterChange"
            :update="updatePayments"
            :mobile-simple="mobileSimple"
            :expand-details="expandDetails"
          ></payment-list>
        </q-card-section>
      </q-card>
    </div>

    <div
      v-if="!g.mobileSimple"
      id="lnbits-wallet-sidebar"
      class="col-12 col-md-5 q-gutter-y-md"
    >
      <lnbits-wallet-details></lnbits-wallet-details>
    </div>
  </div>

  <div
    class="lt-md fixed-bottom left-0 right-0 bg-primary text-white shadow-2 z-top"
  >
    <q-tabs active-class="px-0" indicator-color="transparent" align="justify">
      <q-tab
        icon="file_download"
        @click="showReceiveDialog"
        :label="$t('receive')"
      >
      </q-tab>

      <q-tab @click="showParseDialog" icon="file_upload" :label="$t('send')">
      </q-tab>
    </q-tabs>
    <q-btn
      round
      size="35px"
      unelevated
      icon="qr_code_scanner"
      @click="showCamera"
      class="text-white bg-primary z-top vertical-bottom absolute-center absolute"
    >
    </q-btn>
  </div>

  <lnbits-wallet-receive-dialog />
  <lnbits-wallet-parse-dialog />
  <lnbits-wallet-disclaimer-dialog />
</template>
