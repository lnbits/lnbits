<template id="lnbits-admin-extensions">
  <q-card-section class="q-pa-none">
    <div>
      <div class="row items-center justify-between q-mb-md">
        <h6 class="q-my-none">
          <span v-text="$t('extensions')"></span>
        </h6>
        <q-btn
          unelevated
          color="primary"
          icon="memory"
          label="WASM Runtime"
          to="/admin/extensions/wasm"
        ></q-btn>
      </div>
      <div class="row q-col-gutter-md">
        <div class="col-12 q-mb-md">
          <p>
            <span v-text="$t('extension_sources')"></span>
          </p>
          <q-input
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
      <div class="row q-col-gutter-md">
        <div class="col-12 col-md-6">
          <p>
            <span v-text="$t('admin_extensions')"></span>
          </p>
          <q-select
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
            filled
            v-model="formData.lnbits_user_default_extensions"
            multiple
            :label="$t('user_default_extensions_label')"
            :hint="$t('user_default_extensions_hint')"
            :options="g.extensions"
          ></q-select>
        </div>
        <div class="col-12 col-md-6">
          <p>
            <span v-text="$t('miscellaneous')"></span>
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
            class="q-mt-md"
            filled
            v-model.number="formData.lnbits_wasm_invocation_retention_days"
            type="number"
            min="0"
            label="WASM invocation retention days"
            hint="Set to 0 to disable automatic cleanup."
          ></q-input>
          <br />
        </div>
        <div class="col-12 col-md-6">
          <p>
            <span v-text="$t('extension_builder_manifest_url')"></span>
          </p>
          <q-input
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
