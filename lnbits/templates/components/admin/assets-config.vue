<template id="lnbits-admin-assets-config">
  <q-card-section class="q-pa-none">
    <h6 class="q-my-none q-mb-sm">Assets</h6>
    <div class="row q-col-gutter-md">
      <div class="col-12 col-md-3">
        <p>
          <span v-text="$t('max_asset_size_mb')"></span>
        </p>
        <q-input
          filled
          type="number"
          v-model.number="formData.lnbits_max_asset_size_mb"
          :label="$t('max_asset_size_mb')"
          step="0.1"
          min="0"
          :hint="$t('max_asset_size_mb_desc')"
        ></q-input>
      </div>

      <div class="col-12 col-md-9">
        <p>
          <span v-text="$t('assets_allowed_mime_types')"></span>
        </p>
        <q-input
          filled
          v-model.number="newAllowedAssetMimeType"
          @keydown.enter="addAllowedAssetMimeType()"
          :label="$t('assets_allowed_mime_types')"
          :hint="$t('assets_allowed_mime_types_desc')"
        >
          <q-btn
            @click="addAllowedAssetMimeType()"
            dense
            flat
            icon="add"
          ></q-btn>
        </q-input>
        <div>
          <q-chip
            v-for="type in formData.lnbits_assets_allowed_mime_types"
            :key="type"
            removable
            @remove="removeAllowedAssetMimeType(type)"
            color="primary"
            text-color="white"
            class="ellipsis"
            :label="type"
            ><q-tooltip
              v-if="identifier"
              anchor="top middle"
              self="bottom middle"
              ><span v-text="identifier"></span></q-tooltip
          ></q-chip>
        </div>
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
          v-model.number="formData.lnbits_asset_thumbnail_format"
          :label="$t('thumbnail_format')"
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
      <div class="col-12 col-md-9">
        <p>
          <span v-text="$t('assets_no_limit_users')"></span>
        </p>
        <q-input
          filled
          v-model="newNoLimitUser"
          @keydown.enter="addNewNoLimitUser()"
          :label="$t('assets_no_limit_users')"
          :hint="$t('assets_no_limit_users_desc')"
        >
          <q-btn @click="addNewNoLimitUser()" dense flat icon="add"></q-btn>
        </q-input>
        <div>
          <q-chip
            v-for="type in formData.lnbits_assets_no_limit_users"
            :key="type"
            removable
            @remove="removeNoLimitUser(type)"
            color="primary"
            text-color="white"
            class="ellipsis"
            :label="type"
            ><q-tooltip
              v-if="identifier"
              anchor="top middle"
              self="bottom middle"
              ><span v-text="identifier"></span></q-tooltip
          ></q-chip>
        </div>
      </div>
    </div>
  </q-card-section>
  <q-card-section>
    <!-- for spacing -->
    <br />
  </q-card-section>
</template>
