<template id="lnbits-admin-wasm-limit-config">
  <q-card-section class="q-pa-none">
    <div>
      <div class="row items-center justify-between q-mb-md q-col-gutter-sm">
        <div class="row items-center q-gutter-sm">
          <q-btn flat dense round icon="arrow_back" :to="backRoute">
            <q-tooltip v-text="backTooltip"></q-tooltip>
          </q-btn>
          <div>
            <h6 class="q-my-none">Wasm Limit Config</h6>
            <div
              class="text-caption text-grey-7"
              v-text="pageDescription"
            ></div>
          </div>
        </div>
        <q-btn-dropdown
          unelevated
          color="primary"
          icon="tune"
          label="Custom Extension Limit"
          :loading="wasmRuntimeLimitExtensionsLoading"
        >
          <q-list style="min-width: 280px; max-width: min(420px, 90vw)">
            <q-item-label header>
              Select an extension from the list to customize
            </q-item-label>
            <q-item
              v-if="
                !wasmRuntimeLimitExtensionsLoading &&
                wasmRuntimeLimitExtensionOptions.length === 0
              "
            >
              <q-item-section>
                <q-item-label>No installed WASM extensions found.</q-item-label>
              </q-item-section>
            </q-item>
            <q-item
              v-for="extension in wasmRuntimeLimitExtensionOptions"
              :key="extension.value"
              clickable
              v-close-popup
              @click="openWasmExtensionLimit(extension.value)"
            >
              <q-item-section>
                <q-item-label v-text="extension.label"></q-item-label>
              </q-item-section>
            </q-item>
          </q-list>
        </q-btn-dropdown>
      </div>

      <template v-if="!isExtensionLimitRoute">
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
      </template>

      <div
        v-if="isExtensionLimitRoute"
        class="row items-center justify-between q-mb-md"
      >
        <div>
          <div class="text-subtitle1 text-weight-medium">
            Extension overrides
          </div>
          <div class="text-caption text-grey-7">
            Empty values inherit the global defaults. A saved 0 disables that
            limit for the selected extension.
          </div>
        </div>
        <div v-if="selectedWasmRuntimeLimitExtension" class="col-12 col-md-7">
          <div class="row items-center q-gutter-sm full-height">
            <q-chip
              dense
              :color="
                selectedWasmRuntimeLimitExtension.active ? 'positive' : 'grey-7'
              "
              text-color="white"
              :label="
                selectedWasmRuntimeLimitExtension.active ? 'Active' : 'Inactive'
              "
            ></q-chip>
            <q-chip
              dense
              outline
              color="primary"
              :label="customWasmLimitCount + ' custom overrides'"
            ></q-chip>
          </div>
        </div>
      </div>

      <q-banner
        v-if="
          isExtensionLimitRoute &&
          !wasmRuntimeLimitExtensionsLoading &&
          !selectedWasmRuntimeLimitExtension
        "
        rounded
        class="bg-grey-2 text-grey-8 q-mb-lg"
      >
        WASM extension not found.
      </q-banner>

      <div v-if="isExtensionLimitRoute && selectedWasmRuntimeLimitExtension">
        <div
          v-for="group in wasmRuntimeLimitGroups"
          :key="'extension-' + group.title"
          class="q-mb-lg"
        >
          <div class="text-subtitle2 text-weight-medium q-mb-sm">
            <span v-text="group.title"></span>
          </div>
          <div class="row q-col-gutter-md">
            <div
              v-for="field in group.fields"
              :key="'extension-' + field.name"
              class="col-12 col-md-6"
            >
              <q-input
                filled
                dense
                type="number"
                min="0"
                v-model="wasmExtensionLimitDraft[field.name]"
                :label="field.label"
                :hint="wasmExtensionLimitHint(field)"
                :placeholder="wasmExtensionLimitPlaceholder(field)"
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

        <div class="row justify-end q-gutter-sm q-mt-md">
          <q-btn
            flat
            color="primary"
            icon="restart_alt"
            label="Clear Overrides"
            :disable="wasmExtensionLimitsSaving"
            @click="clearWasmExtensionLimits"
          ></q-btn>
          <q-btn
            unelevated
            color="primary"
            icon="save"
            label="Save Extension Limits"
            :loading="wasmExtensionLimitsSaving"
            @click="saveWasmExtensionLimits"
          ></q-btn>
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
