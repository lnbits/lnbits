<template id="lnbits-admin-wasm-limit-config">
  <q-card-section class="q-pa-none">
    <div>
      <div class="row items-center q-gutter-sm q-mb-md">
        <q-btn flat dense round icon="arrow_back" to="/admin#extensions">
          <q-tooltip>Extensions Settings</q-tooltip>
        </q-btn>
        <div>
          <h6 class="q-my-none">Wasm Limit Config</h6>
          <div class="text-caption text-grey-7">
            These values are global upper bounds. Use 0 to disable a global
            limit.
          </div>
        </div>
      </div>

      <div
        v-for="group in wasmRuntimeLimitGroups"
        :key="group.title"
        class="q-mb-lg"
      >
        <div class="text-subtitle2 text-weight-medium q-mb-sm">
          <span v-text="group.title"></span>
        </div>
        <div class="row q-col-gutter-md">
          <div
            v-for="field in group.fields"
            :key="field.name"
            class="col-12 col-md-6"
          >
            <q-input
              filled
              dense
              type="number"
              min="0"
              v-model.number="formData[field.name]"
              :label="field.label"
              :hint="field.description"
            >
              <template v-slot:append>
                <q-btn
                  dense
                  flat
                  round
                  icon="info"
                  color="primary"
                  @click.stop.prevent="showWasmLimitInfo(field)"
                >
                  <q-tooltip max-width="360px">
                    <span v-text="field.details"></span>
                  </q-tooltip>
                </q-btn>
              </template>
            </q-input>
          </div>
        </div>
      </div>

      <q-dialog v-model="wasmLimitInfoDialog.show">
        <q-card style="width: min(560px, calc(100vw - 32px)); max-width: 560px">
          <q-card-section class="row items-center q-pb-none">
            <div class="text-h6" v-text="wasmLimitInfoDialog.title"></div>
            <q-space></q-space>
            <q-btn v-close-popup flat round dense icon="close"></q-btn>
          </q-card-section>
          <q-card-section>
            <div
              class="text-body1"
              style="line-height: 1.6"
              v-text="wasmLimitInfoDialog.details"
            ></div>
          </q-card-section>
        </q-card>
      </q-dialog>
    </div>
  </q-card-section>
</template>
