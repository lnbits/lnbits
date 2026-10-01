<template id="onchain-serial-port-config">
  <div>
    <div class="row q-mt-md">
      <div class="col-12">
        <q-input
          filled
          dense
          v-model.trim="config.name"
          :label="$t('onchain.name_optional')"
        ></q-input>
      </div>
    </div>
    <q-separator class="q-mt-sm"></q-separator>
    <div class="row q-mt-md">
      <div class="col-12">
        <q-input
          filled
          dense
          v-model.trim="config.baudRate"
          type="number"
          :label="$t('onchain.baud_rate')"
        ></q-input>
      </div>
    </div>
    <div class="row q-mt-md">
      <div class="col-12">
        <q-input
          filled
          dense
          v-model.trim="config.bufferSize"
          type="number"
          :label="$t('onchain.buffer_size')"
        ></q-input>
      </div>
    </div>
    <div class="row q-mt-md">
      <div class="col-12">
        <q-input
          filled
          dense
          v-model.trim="config.flowControl"
          :label="$t('onchain.flow_control')"
        ></q-input>
      </div>
    </div>
    <div class="row q-mt-md">
      <div class="col-12">
        <q-input
          filled
          dense
          v-model.trim="config.parity"
          :label="$t('onchain.parity')"
        ></q-input>
      </div>
    </div>
    <div class="row q-mt-md">
      <div class="col-12">
        <q-input
          filled
          dense
          v-model.trim="config.dataBits"
          type="number"
          :label="$t('onchain.data_bits')"
        ></q-input>
      </div>
    </div>

    <div class="row q-mt-md">
      <div class="col-12">
        <q-input
          filled
          dense
          v-model.trim="config.stopBits"
          type="number"
          :label="$t('onchain.stop_bits')"
        ></q-input>
      </div>
    </div>
  </div>
</template>
