<template id="lnbits-admin-assets-config">
  <q-card-section class="q-pa-none">
    <h6 class="q-my-none q-mb-sm">Assets</h6>
    <div class="row q-col-gutter-md">
      <div class="col-12 col-md-3">
        <p>
          <span v-text="$t('max_asset_size_kb')"></span>
        </p>
        <q-input
          filled
          type="number"
          v-model.number="formData.lnbits_max_asset_size_kb"
          :label="$t('max_asset_size_kb')"
          step="1"
          min="0"
          :hint="$t('max_asset_size_kb_desc')"
        ></q-input>
      </div>

      <div class="col-12 col-md-3">
        <p>
          <span v-text="$t('assets_allowed_mime_types')"></span>
        </p>
        <q-input
          filled
          type="number"
          v-model.number="formData.lnbits_assets_allowed_mime_types"
          :label="$t('assets_allowed_mime_types')"
          step="1"
          min="0"
          :hint="$t('assets_allowed_mime_types_desc')"
        ></q-input>
      </div>
    </div>
    <q-separator class="q-mb-lg q-mt-sm"></q-separator>
    <h6 class="q-my-none q-mb-sm">Thumbnails</h6>
    <div class="row q-col-gutter-md">
      <div class="col-12 col-md-3">
        <p>
          <span v-text="$t('thumbnail_width')"></span>
        </p>
        <q-input
          filled
          type="number"
          v-model.number="formData.lnbits_asset_thumbnail_width"
          :label="$t('thumbnail_width')"
          step="1"
          min="0"
          :hint="$t('thumbnail_width_desc')"
        ></q-input>
      </div>
      <div class="col-12 col-md-3">
        <p>
          <span v-text="$t('thumbnail_height')"></span>
        </p>
        <q-input
          filled
          type="number"
          v-model.number="formData.lnbits_asset_thumbnail_height"
          :label="$t('thumbnail_height')"
          step="1"
          min="0"
          :hint="$t('thumbnail_height_desc')"
        ></q-input>
      </div>
      <div class="col-12 col-md-3">
        <p>
          <span v-text="$t('thumbnail_format')"></span>
        </p>
        <q-input
          filled
          type="number"
          v-model.number="formData.lnbits_asset_thumbnail_format"
          :label="$t('thumbnail_format')"
          step="1"
          min="0"
          :hint="$t('thumbnail_format_desc')"
        ></q-input>
      </div>
    </div>
    <q-separator class="q-mb-lg q-mt-sm"></q-separator>
    <h6 class="q-my-none q-mb-sm">Users</h6>
    <div class="row q-col-gutter-md">
      <div class="col-12 col-md-3">
        <p>
          <span v-text="$t('max_assets_per_user')"></span>
        </p>
        <q-input
          filled
          type="number"
          v-model.number="formData.lnbits_max_assets_per_user"
          :label="$t('max_assets_per_user')"
          step="1"
          min="0"
          :hint="$t('max_assets_per_user_desc')"
        ></q-input>
      </div>
      <div class="col-12 col-md-6">
        <p>
          <span v-text="$t('assets_no_limit_users')"></span>
        </p>
        <q-input
          filled
          type="number"
          v-model.number="formData.lnbits_assets_no_limit_users"
          :label="$t('assets_no_limit_users')"
          step="1"
          min="0"
          :hint="$t('assets_no_limit_users_desc')"
        ></q-input>
      </div>
    </div>
  </q-card-section>
</template>
