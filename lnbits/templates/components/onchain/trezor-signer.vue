<template id="onchain-trezor-signer">
  <div>
    <q-btn
      @click="connectToDevice"
      split
      unelevated
      color="primary"
      :text-color="connected ? 'green' : ''"
      :label="connected ? 'Trezor connected' : 'Connect Trezor'"
    >
      <q-spinner v-if="isConnecting" color="secondary"></q-spinner>
    </q-btn>

    <q-btn
      v-if="connected"
      flat
      dense
      round
      icon="info"
      aria-label="Trezor device details"
      @click="showFeatures = true"
    ></q-btn>
    <q-dialog v-model="showFeatures" position="top">
      <q-card v-if="features" class="q-pa-lg q-pt-md">
        <q-card-section>
          <h5
            v-text="
              $t('onchain.connected_to_trezor', {
                label: features.payload.label
              })
            "
          ></h5>
          <q-input
            filled
            dense
            for="serial-port-console"
            v-model.trim="featuresJson"
            type="textarea"
            rows="20"
            cols="200"
            :label="$t('onchain.device_features')"
          ></q-input>
        </q-card-section>

        <q-card-section>
          <div class="row q-mt-lg">
            <q-btn
              v-close-popup
              flat
              color="grey"
              class="q-ml-auto"
              :label="$t('onchain.close')"
            ></q-btn>
          </div>
        </q-card-section>
      </q-card>
    </q-dialog>
  </div>
</template>
