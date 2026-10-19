<template id="page-wasm-studio">
  <div v-if="g.user?.admin">
    <q-card class="q-mb-md">
      <q-toolbar class="q-py-sm">
        <q-btn
          flat
          round
          icon="arrow_back"
          to="/admin#extensions"
          :aria-label="$t('extensions')"
        ></q-btn>
        <h1
          class="col text-subtitle1 q-my-none q-ml-sm"
          v-text="$t('wasm_studio_title')"
        ></h1>
        <q-btn
          unelevated
          no-caps
          color="primary"
          icon="add"
          :label="$t('wasm_studio_add')"
          :disable="loading || loadError || saving"
          @click="showAddDialog = true"
        ></q-btn>
      </q-toolbar>
    </q-card>
    <q-card>
      <q-card-section v-if="loading" class="text-center" aria-busy="true">
        <q-spinner-dots size="40px" color="primary"></q-spinner-dots>
      </q-card-section>
      <q-banner
        v-else-if="loadError"
        class="bg-negative text-white"
        role="alert"
      >
        <span v-text="$t('wasm_studio_load_failed')"></span>
        <template v-slot:action>
          <q-btn
            flat
            :label="$t('ai_builder_retry')"
            @click="loadSettings"
          ></q-btn>
        </template>
      </q-banner>
      <q-card-section
        v-else-if="!models.length"
        v-text="$t('wasm_studio_empty')"
      ></q-card-section>
      <q-list v-else separator>
        <q-item v-for="(model, index) in models" :key="index" class="q-py-md">
          <q-item-section style="overflow-wrap: anywhere; min-width: 0">
            <q-item-label
              class="text-subtitle1"
              v-text="model.name"
            ></q-item-label>
            <q-item-label caption>
              <span v-text="providerName(model.provider)"></span>
              · <span v-text="model.model"></span>
            </q-item-label>
            <q-item-label
              v-if="model.base_url"
              caption
              v-text="model.base_url"
            ></q-item-label>
            <q-item-label caption>
              <span v-text="$t('wasm_studio_api_key')"></span>:
              <span
                v-if="model.api_key"
                :aria-label="$t('wasm_studio_key_saved')"
                >••••••••</span
              >
              <span v-else v-text="$t('wasm_studio_no_key')"></span>
            </q-item-label>
          </q-item-section>
          <q-item-section side>
            <q-btn
              flat
              round
              color="negative"
              icon="delete"
              :aria-label="$t('wasm_studio_remove')"
              :loading="removing === index"
              :disable="saving"
              @click="confirmRemove(model, index)"
            >
              <q-tooltip v-text="$t('wasm_studio_remove')"></q-tooltip>
            </q-btn>
          </q-item-section>
        </q-item>
      </q-list>
    </q-card>
    <q-dialog v-model="showAddDialog" :persistent="saving" @hide="resetForm">
      <q-card class="q-pa-lg lnbits__dialog-card" style="width: 500px">
        <q-form class="q-gutter-md" @submit="addModel">
          <h2 class="text-h6 q-my-none" v-text="$t('wasm_studio_add')"></h2>
          <q-input
            v-model.trim="form.name"
            filled
            autofocus
            :label="$t('wasm_extension_name')"
            :rules="[required]"
            maxlength="100"
            :disable="saving"
          ></q-input>
          <q-select
            v-model="form.provider"
            filled
            :label="$t('wasm_studio_provider')"
            :options="providers"
            emit-value
            map-options
            :rules="[required]"
            :disable="saving"
          ></q-select>
          <q-input
            v-model.trim="form.model"
            filled
            :label="$t('wasm_studio_model')"
            :hint="$t('wasm_studio_model_hint')"
            :rules="[required, validateModel]"
            maxlength="256"
            :disable="saving"
          ></q-input>
          <q-input
            v-model="form.api_key"
            filled
            type="password"
            autocomplete="new-password"
            :label="$t('wasm_studio_api_key')"
            :hint="$t('wasm_studio_api_key_hint')"
            maxlength="4096"
            :disable="saving"
          ></q-input>
          <q-input
            v-model.trim="form.base_url"
            filled
            :label="$t('wasm_studio_base_url')"
            :hint="$t('wasm_studio_base_url_hint')"
            :rules="[validateBaseUrl]"
            maxlength="2048"
            :disable="saving"
          ></q-input>
          <div class="row justify-end q-gutter-sm">
            <q-btn
              flat
              :label="$t('close')"
              v-close-popup
              :disable="saving"
            ></q-btn>
            <q-btn
              unelevated
              no-caps
              color="primary"
              type="submit"
              :label="$t('wasm_studio_add')"
              :loading="saving"
            ></q-btn>
          </div>
        </q-form>
      </q-card>
    </q-dialog>
  </div>
</template>
