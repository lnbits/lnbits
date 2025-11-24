<template id="lnbits-qrcode-scanner">
  <q-dialog v-model="g.showScanner" position="top">
    <q-card class="q-pa-lg q-pt-xl">
      <div class="text-center q-mb-lg">
        <qrcode-stream
          @detect="detect"
          @camera-on="onInitQR"
          class="rounded-borders"
        ></qrcode-stream>
      </div>
      <div class="row q-mt-lg">
        <q-btn
          @click="g.showScanner = false"
          flat
          color="grey"
          class="q-ml-auto"
          :label="$t('cancel')"
        ></q-btn>
      </div>
    </q-card>
  </q-dialog>
</template>
