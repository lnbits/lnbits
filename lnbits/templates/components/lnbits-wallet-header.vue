<template id="lnbits-wallet-header">
  <q-card
    :style="
      $q.screen.lt.md
        ? {
            background: $q.screen.lt.md ? 'none !important' : '',
            boxShadow: $q.screen.lt.md ? 'none !important' : '',
            border: $q.screen.lt.md ? 'none !important' : '',
            width: $q.screen.lt.md && mobileSimple ? '90% !important' : ''
          }
        : ''
    "
  >
    <q-card-section style="height: 130px">
      <div class="row q-gutter-md">
        <div v-if="isSatsDenomination" class="col-1" style="max-width: 30px">
          <q-btn
            v-if="g.fiatTracking"
            @click="swapBalancePriority"
            style="height: 50px"
            class="q-mt-lg"
            color="primary"
            flat
            dense
            icon="swap_vert"
          ></q-btn>
        </div>
        <div class="col">
          <div
            class="column"
            :class="{
              'q-pt-sm': g.fiatTracking,
              'q-pt-lg': !g.fiatTracking
            }"
            v-if="!isFiatPriority || !g.fiatTracking"
            style="height: 100px"
          >
            <div class="col-7">
              <div class="row">
                <div class="col-auto">
                  <div class="text-h3 q-my-none full-width">
                    <strong
                      v-text="formatBalance(this.g.wallet.sat)"
                      class="text-no-wrap"
                      :style="{
                        fontSize: 'clamp(0.75rem, 10vw, 3rem)',
                        display: 'inline-block',
                        maxWidth: '100%'
                      }"
                    ></strong>
                  </div>
                </div>
                <div class="col-auto">
                  <lnbits-update-balance
                    v-if="$q.screen.lt.lg"
                    :wallet_id="this.g.wallet.id"
                    :callback="updateBalanceCallback"
                    :small_btn="true"
                  ></lnbits-update-balance>
                </div>
              </div>
            </div>
            <div class="col-2">
              <div v-if="g.fiatTracking">
                <span
                  class="text-h5 text-italic"
                  v-text="formattedFiatAmount"
                  style="opacity: 0.75"
                ></span>
              </div>
            </div>
          </div>

          <div
            class="column"
            v-if="isFiatPriority && g.fiatTracking"
            :class="{
              'q-pt-sm': g.fiatTracking,
              'q-pt-lg': !g.fiatTracking
            }"
            style="height: 100px"
          >
            <div class="col-7">
              <div class="row">
                <div class="col-auto">
                  <div
                    v-if="g.fiatTracking"
                    class="text-h3 q-my-none text-no-wrap"
                  >
                    <strong v-text="formattedFiatAmount"></strong>
                  </div>
                </div>
                <div class="col-auto">
                  <lnbits-update-balance
                    v-if="$q.screen.lt.lg"
                    :wallet_id="this.g.wallet.id"
                    :callback="updateBalanceCallback"
                    :small_btn="true"
                  ></lnbits-update-balance>
                </div>
              </div>
            </div>
            <div class="col-2">
              <span
                class="text-h5 text-italic"
                style="opacity: 0.75"
                v-text="formattedBalance + LNBITS_DENOMINATION"
              >
              </span>
            </div>
          </div>

          <div
            class="absolute-right q-pa-md"
            v-if="$q.screen.gt.md && g.fiatTracking && isSatsDenomination"
          >
            <div class="text-bold text-italic">BTC Price</div>
            <span
              class="text-bold text-italic"
              v-text="formattedExchange"
            ></span>
          </div>
          <q-btn
            v-if="$q.screen.lt.md"
            @click="simpleMobile()"
            color="primary"
            class="q-ml-xl absolute-right"
            dense
            size="sm"
            style="height: 20px; margin-top: 75px"
            flat
            :icon="mobileSimple ? 'unfold_more' : 'unfold_less'"
            :label="mobileSimple ? $t('more') : $t('less')"
          ></q-btn>
        </div>
      </div>
    </q-card-section>
    <div class="row q-pb-md q-px-md q-col-gutter-md gt-sm">
      <div class="col">
        <q-btn
          unelevated
          color="primary"
          class="q-mr-md"
          @click="showParseDialog"
          :disable="!this.g.wallet.canSendPayments"
          :label="$t('paste_request')"
        ></q-btn>
        <q-btn
          unelevated
          color="primary"
          class="q-mr-md"
          @click="showReceiveDialog"
          :disable="!this.g.wallet.canReceivePayments"
          :label="$t('create_invoice')"
        ></q-btn>
        <q-btn
          unelevated
          color="secondary"
          icon="qr_code_scanner"
          :disable="
            !this.g.wallet.canReceivePayments && !this.g.wallet.canSendPayments
          "
          @click="showCamera"
        >
          <q-tooltip><span v-text="$t('camera_tooltip')"></span></q-tooltip>
        </q-btn>
        <lnbits-update-balance
          v-if="$q.screen.gt.md"
          :wallet_id="this.g.wallet.id"
          :callback="updateBalanceCallback"
          :small_btn="false"
        ></lnbits-update-balance>
      </div>
    </div>
  </q-card>
</template>
