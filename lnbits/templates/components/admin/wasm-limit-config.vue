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
            ></q-input>
          </div>
        </div>
      </div>
    </div>
  </q-card-section>
</template>
