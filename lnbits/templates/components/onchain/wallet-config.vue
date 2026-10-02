<template id="onchain-wallet-config">
  <div>
    <q-banner v-if="loadError"
      >Could not load onchain settings.<template v-slot:action
        ><q-btn flat label="Retry" @click="getConfig"></q-btn></template
    ></q-banner>
    <q-card-section>
      <div class="row items-center no-wrap">
        <div class="col row items-center q-gutter-sm">
          <slot name="trezor"></slot><slot name="serial"></slot>
        </div>
        <q-btn
          flat
          round
          dense
          class="q-ml-sm"
          icon="settings"
          aria-label="Onchain settings"
          :disable="busy"
          @click="openSettings"
          ><q-tooltip>Blockchain settings</q-tooltip></q-btn
        >
      </div>
    </q-card-section>

    <q-dialog v-model="show" position="top">
      <q-card class="q-pa-lg q-pt-xl lnbits__dialog-card">
        <q-form @submit="updateConfig" class="q-gutter-md">
          <q-select
            filled
            dense
            emit-value
            map-options
            v-model="config.explorer_provider"
            :options="explorerOptions"
            label="Block explorer"
          ></q-select>
          <q-input
            v-if="config.explorer_provider === 'mempool'"
            filled
            dense
            v-model.trim="config.mempool_endpoint"
            hint="Use mempool.space or your own Mempool server URL for this network."
            type="text"
            :label="$t('onchain.mempool_endpoint')"
          >
          </q-input>

          <q-input
            filled
            dense
            v-model.number="config.receive_gap_limit"
            type="number"
            min="0"
            :label="$t('onchain.receive_gap_limit')"
          ></q-input>

          <q-input
            filled
            dense
            v-model.number="config.change_gap_limit"
            type="number"
            min="0"
            :label="$t('onchain.change_gap_limit')"
          ></q-input>

          <q-select
            filled
            dense
            emit-value
            v-model="config.network"
            map-options
            readonly
            hide-dropdown-icon
            :options="networkOptions"
            :label="$t('onchain.network')"
          ></q-select>

          <q-toggle
            :label="
              config.sats_denominated
                ? $t('onchain.sats_denominated')
                : $t('onchain.btc_denominated')
            "
            color="primary"
            v-model="config.sats_denominated"
          ></q-toggle>

          <div class="row q-mt-lg">
            <q-btn
              unelevated
              color="primary"
              :disable="
                config.explorer_provider === 'mempool' &&
                !config.mempool_endpoint
              "
              type="submit"
              :label="$t('onchain.update')"
            ></q-btn>
            <q-btn
              v-close-popup
              flat
              color="grey"
              class="q-ml-auto"
              :label="$t('onchain.cancel')"
            ></q-btn>
          </div>
        </q-form>
      </q-card>
    </q-dialog>
  </div>
</template>
