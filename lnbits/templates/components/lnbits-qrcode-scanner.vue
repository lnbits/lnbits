<template id="lnbits-qrcode-scanner">
  <lnbits-dialog
    :show="showScanner"
    :cancel-label="$t('cancel')"
    @update:show="showScanner = $event"
    @cancel="reset"
  >
    <div class="text-center q-mb-lg">
      <qrcode-stream
        @detect="detect"
        @camera-on="onInitQR"
        class="rounded-borders"
      ></qrcode-stream>
    </div>
  </lnbits-dialog>
</template>
