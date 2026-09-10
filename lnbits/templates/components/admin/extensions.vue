<template id="lnbits-admin-extensions">
  <q-card-section class="q-pa-none">
    <div>
      <div class="row items-center justify-between q-mb-md">
        <h6 class="q-my-none q-mb-sm">
          <span v-text="$t('extension_sources')"></span>
        </h6>
      </div>
      <div class="row q-col-gutter-md">
        <div class="col-12 q-mb-md">
          <q-input
            dense
            class="q-mb-md"
            filled
            v-model="formAddExtensionsManifest"
            @keydown.enter="addExtensionsManifest"
            type="text"
            :label="$t('ext_sources_label')"
            :hint="$t('ext_sources_hint')"
          >
            <q-btn @click="addExtensionsManifest" dense flat icon="add"></q-btn>
          </q-input>
          <div>
            <q-chip
              v-for="manifestUrl in formData.lnbits_extensions_manifests"
              :key="manifestUrl"
              removable
              @remove="removeExtensionsManifest(manifestUrl)"
              color="primary"
              text-color="white"
              ><span class="ellipsis" v-text="manifestUrl"></span
            ></q-chip>
          </div>
        </div>
      </div>
      <q-separator class="q-mb-lg q-mt-md"></q-separator>
      <h6 class="q-my-none q-mb-sm">WASM Extensions</h6>
      <div class="row q-col-gutter-md">
        <div class="col-12 q-mb-md">
          <q-input
            dense
            class="q-mb-md"
            filled
            v-model="formAddWasmManifest"
            type="text"
            :label="$t('wasm_sources_label')"
            :hint="$t('wasm_sources_hint')"
          >
            <q-btn @click="addWasmManifest" dense flat icon="add"></q-btn>
          </q-input>
          <div class="q-mb-md">
            <q-chip
              v-for="manifestUrl in formData.lnbits_wasm_extensions_manifests"
              :key="manifestUrl"
              removable
              @remove="removeWasmManifest(manifestUrl)"
              color="primary"
              text-color="white"
              ><span class="ellipsis" v-text="manifestUrl"></span
            ></q-chip>
          </div>
          <div class="row q-gutter-sm">
            <q-btn
              unelevated
              color="primary"
              icon="memory"
              label="WASM Runtime"
              to="/admin/extensions/wasm"
            ></q-btn>
            <q-btn
              unelevated
              color="primary"
              icon="tune"
              label="Wasm Limit Config"
              to="/admin/extensions/wasm/limits"
            ></q-btn>
          </div>
        </div>
      </div>
      <q-separator class="q-mb-lg q-mt-md"></q-separator>
      <h6 class="q-my-none q-mb-sm">Access and Defaults</h6>
      <div class="row q-col-gutter-md">
        <div class="col-12 col-md-6">
          <p>
            <span v-text="$t('admin_extensions')"></span>
          </p>
          <q-select
            dense
            filled
            v-model="formData.lnbits_admin_extensions"
            multiple
            :label="$t('admin_extensions_label')"
            :hint="$t('admin_extensions_hint')"
            :options="g.extensions"
          ></q-select>
        </div>

        <div class="col-12 col-md-6">
          <p>
            <span v-text="$t('user_default_extensions')"></span>
          </p>
          <q-select
            dense
            filled
            v-model="formData.lnbits_user_default_extensions"
            multiple
            :label="$t('user_default_extensions_label')"
            :hint="$t('user_default_extensions_hint')"
            :options="g.extensions"
          ></q-select>
        </div>
        <div class="col-12">
          <q-separator class="q-mb-lg q-mt-md"></q-separator>
          <h6 class="q-my-none q-mb-sm">Advanced</h6>
        </div>
        <div class="col-12 col-md-6">
          <p>
            <span v-text="$t('miscellanous')"></span>
          </p>
          <q-item tag="label" v-ripple>
            <q-item-section>
              <q-item-label>
                <span v-text="$t('misc_disable_extensions')"></span>
              </q-item-label>
              <q-item-label caption>
                <span v-text="$t('misc_disable_extensions_label')"></span>
              </q-item-label>
            </q-item-section>
            <q-item-section avatar>
              <q-toggle
                size="md"
                v-model="formData.lnbits_extensions_deactivate_all"
                checked-icon="check"
                color="green"
                unchecked-icon="clear"
              />
            </q-item-section>
          </q-item>
          <q-item tag="label" v-ripple>
            <q-item-section>
              <q-item-label>
                <span v-text="$t('misc_disable_extensions_builder')"></span>
              </q-item-label>
              <q-item-label caption>
                <span
                  v-text="$t('misc_disable_extensions_builder_label')"
                ></span>
              </q-item-label>
            </q-item-section>
            <q-item-section avatar>
              <q-toggle
                size="md"
                v-model="formData.lnbits_extensions_builder_activate_non_admins"
                checked-icon="check"
                color="green"
                unchecked-icon="clear"
              />
            </q-item-section>
          </q-item>
          <q-item tag="label" v-ripple>
            <q-item-section>
              <q-item-label>
                <span v-text="$t('misc_hide_api')"></span>
              </q-item-label>
              <q-item-label caption>
                <span v-text="$t('misc_hide_api_label')"></span>
              </q-item-label>
            </q-item-section>
            <q-item-section avatar>
              <q-toggle
                size="md"
                v-model="formData.lnbits_hide_api"
                checked-icon="check"
                color="green"
                unchecked-icon="clear"
              />
            </q-item-section>
          </q-item>
          <q-input
            dense
            class="q-mt-md"
            filled
            v-model.number="formData.lnbits_wasm_invocation_retention_days"
            type="number"
            min="0"
            label="WASM invocation retention"
            :suffix="$t('days')"
            hint="Set to 0 to disable automatic cleanup."
          ></q-input>
        </div>
        <div class="col-12 col-md-6">
          <p>
            <span v-text="$t('extension_builder_manifest_url')"></span>
          </p>
          <q-input
            dense
            filled
            v-model="formData.lnbits_extensions_builder_manifest_url"
            :label="$t('extension_builder_manifest_url')"
            :hint="$t('extension_builder_manifest_url_hint')"
          ></q-input>
        </div>
        <div class="col-12 col-md-6 q-pb-md">
          <p>
            <span v-text="$t('reviews_url')"></span>
          </p>
          <q-input
            dense
            filled
            v-model="formData.lnbits_extensions_reviews_url"
            :label="$t('reviews_url_label')"
            :hint="$t('reviews_url_hint')"
            type="url"
            autocomplete="off"
          ></q-input>
        </div>
      </div>
    </div>
  </q-card-section>
</template>
