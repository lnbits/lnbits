<template id="onchain-fee-rate">
  <div>
    <div class="row items-center q-mb-md">
      <div
        class="col-4 col-sm-2 q-pr-sm"
        v-text="$t('onchain.fee_rate_label')"
      ></div>
      <div class="col-8 col-sm-3 q-pr-sm">
        <q-input
          filled
          dense
          v-model.number="feeRate"
          step="any"
          :rules="[
            val =>
              (Number.isFinite(+val) && +val > 0) ||
              $t('onchain.field_required')
          ]"
          type="number"
          label="sats/vbyte"
        ></q-input>
      </div>
      <div class="col-12 col-sm-7 q-pt-sm">
        <q-slider
          v-model="sliderPosition"
          color="secondary"
          :markers="1"
          :marker-labels="{0: '1', 1: '10', 2: '100', 3: '1000'}"
          snap
          label
          label-always
          :label-value="getFeeRateLabel(feeRate)"
          :min="0"
          :max="3"
          :step="0.01"
          :aria-valuetext="feeRate + ' sats/vbyte'"
        ></q-slider>
      </div>
    </div>
    <div
      v-if="
        feeRate < recommededFees.hourFee || feeRate > recommededFees.fastestFee
      "
      class="row items-center q-mb-md"
    >
      <div class="col-4 col-sm-2 q-pr-sm"></div>
      <div class="col-10 q-pr-lg">
        <q-badge
          v-if="feeRate < recommededFees.hourFee"
          color="pink"
          size="lg"
          v-text="$t('onchain.fee_too_low_warning')"
        >
        </q-badge>
        <q-badge
          v-if="feeRate > recommededFees.fastestFee"
          color="pink"
          v-text="$t('onchain.fee_too_high_warning')"
        >
        </q-badge>
      </div>
    </div>

    <div class="row items-center q-mb-md">
      <div
        class="col-4 col-sm-2 q-pr-sm"
        v-text="$t('onchain.fee_label')"
      ></div>
      <div class="col-8 col-sm-3 q-pr-sm">
        <span v-text="feeValue"></span> sats
      </div>
      <div class="col-12 col-sm-7 q-pt-sm">
        <q-btn
          outline
          dense
          size="md"
          icon="refresh"
          color="grey"
          class="float-right"
          @click="refreshRecommendedFees()"
          :loading="refreshing"
          :label="$t('onchain.refresh_fee_rates')"
        ></q-btn>
      </div>
    </div>
  </div>
</template>
