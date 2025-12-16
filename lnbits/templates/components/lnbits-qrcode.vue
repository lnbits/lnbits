<template id="lnbits-qrcode">
  <div
    class="qrcode__outer"
    :style="`margin: 13px auto; max-width: ${maxWidth}px`"
  >
    <div ref="qrWrapper" class="qrcode__wrapper">
      <a
        :href="href"
        :title="href === '' ? value : href"
        @click="clickQrCode"
        class="no-link full-width"
      >
        <qrcode-vue
          ref="qrCode"
          :value="value"
          :margin="margin"
          :size="size"
          level="Q"
          render-as="svg"
          class="rounded-borders q-mb-sm"
        >
          <q-tooltip :model-value="href === '' ? value : href"></q-tooltip>
        </qrcode-vue>
      </a>
      <q-img
        :src="logo"
        class="qrcode__image"
        alt="qrcode icon"
        style="pointer-events: none"
      ></q-img>
    </div>
    <div
      v-if="showButtons"
      class="qrcode__buttons row q-gutter-x-sm items-center justify-end no-wrap full-width"
    >
      <q-btn
        v-if="nfc && nfcSupported"
        :disabled="nfcTagWriting"
        flat
        dense
        class="text-grey"
        icon="nfc"
        @click="writeNfcTag"
      >
        <q-tooltip>Write NFC Tag</q-tooltip>
      </q-btn>
      <q-btn
        v-if="print"
        flat
        dense
        class="text-grey"
        @click="printQrCode()"
        icon="print"
      >
        <q-tooltip>Print</q-tooltip>
      </q-btn>
      <q-btn flat dense class="text-grey" icon="download" @click="downloadSVG">
        <q-tooltip>Download SVG</q-tooltip>
      </q-btn>
      <q-btn
        flat
        dense
        class="text-grey"
        @click="utils.copyText(value)"
        icon="content_copy"
      >
        <q-tooltip>Copy</q-tooltip>
      </q-btn>
    </div>
  </div>
</template>
