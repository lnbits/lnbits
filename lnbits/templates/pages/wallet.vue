<template id="page-wallet">
  <div class="row q-col-gutter-md" style="margin-bottom: 6rem">
    <div class="col-12 col-md-8 q-gutter-y-md">
      <lnbits-wallet-header></lnbits-wallet-header>

      <q-card
        :style="
          $q.screen.lt.md
            ? {
                background: $q.screen.lt.md ? 'none !important' : '',
                boxShadow: $q.screen.lt.md ? 'none !important' : '',
                border: $q.screen.lt.md ? 'none !important' : '',
                marginTop: $q.screen.lt.md ? '0px !important' : ''
              }
            : ''
        "
      >
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
      v-if="!mobileSimple"
      class="wallet-sidebar"
      class="col-12 col-md-5 q-gutter-y-md"
    >
      <lnbits-wallet-details />

      <q-card v-if="adsEnabled">
        <q-card-section>
          <h6
            v-text="AD_SPACE_TITLE"
            class="text-subtitle1 q-mt-none q-mb-sm"
          ></h6>
        </q-card-section>
        <q-card-section v-for="ad in ads" class="q-pa-none">
          <a
            style="display: inline-block"
            :href="ad[0]"
            class="q-ml-md q-mb-xs q-mr-md"
          >
            <img
              v-if="$q.dark.isActive"
              style="max-width: 100%; height: auto"
              :src="ad[1]"
            />
            <img v-else style="max-width: 100%; height: auto" :src="ad[2]" />
          </a>
        </q-card-section>
      </q-card>

      <div v-show="chartDataPointCount" class="col-12 col-md-5 q-gutter-y-md">
        <q-card v-if="chartConfig.showBalance">
          <q-card-section class="q-pa-none">
            <div style="height: 200px" class="q-pa-sm">
              <canvas ref="walletBalanceChart"></canvas>
            </div>
          </q-card-section>
        </q-card>
        <q-card v-if="chartConfig.showBalanceInOut">
          <q-card-section class="q-pa-none">
            <div style="height: 200px" class="q-pa-sm">
              <canvas ref="walletBalanceInOut"></canvas>
            </div>
          </q-card-section>
        </q-card>
        <q-card v-if="chartConfig.showPaymentCountInOut">
          <q-card-section class="q-pa-none">
            <div style="height: 200px" class="q-pa-sm">
              <canvas ref="walletPaymentsInOut"></canvas>
            </div>
          </q-card-section>
        </q-card>
      </div>
      <div v-if="hasChartActive && !chartDataPointCount">
        <q-card>
          <q-card-section> No chart data available</q-card-section>
        </q-card>
      </div>
    </div>
  </div>

  <q-dialog v-model="icon.show" position="top">
    <q-card class="q-pa-lg q-pt-xl lnbits__dialog-card">
      <q-form @submit="setIcon" class="q-gutter-md">
        <div class="q-gutter-sm q-pa-sm flex flex-wrap justify-center">
          <!-- Loop through all icons -->
          <q-btn
            v-for="(thisIcon, index) in icon.options"
            :key="index"
            @click="setSelectedIcon(thisIcon)"
            round
            text-color="black"
            :color="
              icon.data.icon === thisIcon
                ? icon.data.color || 'primary'
                : 'grey-5'
            "
            size="md"
            :icon="thisIcon"
            class="q-mb-sm"
          ></q-btn>
        </div>
        <div class="q-pa-sm flex justify-between items-center">
          <div class="flex q-pl-lg">
            <!-- Color options -->
            <q-btn
              v-for="(color, index) in icon.colorOptions"
              :key="'color-' + index"
              @click="setSelectedColor(color)"
              round
              :color="color"
              size="xs"
              style="width: 24px; height: 24px; min-width: 24px; padding: 0"
              class="q-mr-xs"
            ></q-btn>
          </div>
          <q-btn
            unelevated
            color="primary"
            :disable="!icon.data.icon"
            type="submit"
          >
            Save Icon
          </q-btn>
        </div>
      </q-form>
    </q-card>
  </q-dialog>

  <q-dialog v-model="receive.show" position="top" @hide="onReceiveDialogHide">
    <q-card
      v-if="!receive.paymentReq"
      class="q-pa-lg q-pt-xl lnbits__dialog-card"
    >
      <lnbits-wallet-not-receive />
    </q-card>

    <q-card
      v-else-if="receive.paymentReq && receive.lnurl == null"
      class="q-pa-lg q-pt-xl lnbits__dialog-card"
    >
      <lnbits-wallet-receive />
    </q-card>
  </q-dialog>

  <q-dialog v-model="parse.show" @hide="closeParseDialog" position="top">
    <q-card class="q-pa-lg q-pt-xl lnbits__dialog-card">
      <lnbits-wallet-parse></lnbits-wallet-parse>
    </q-card>
  </q-dialog>

  <q-dialog v-model="parse.camera.show" position="top">
    <q-card class="q-pa-lg q-pt-xl">
      <div class="text-center q-mb-lg">
        <qrcode-stream
          @detect="decodeQR"
          @camera-on="onInitQR"
          class="rounded-borders"
        ></qrcode-stream>
      </div>
      <div class="row q-mt-lg">
        <q-btn
          @click="closeCamera"
          flat
          color="grey"
          class="q-ml-auto"
          :label="$t('cancel')"
        ></q-btn>
      </div>
    </q-card>
  </q-dialog>

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

  <lnbits-wallet-disclaimer></lnbits-wallet-disclaimer>
</template>
