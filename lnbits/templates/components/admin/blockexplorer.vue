<template id="lnbits-admin-blockexplorer">
  <q-card-section class="q-pa-none">
    <h6 class="q-my-none q-mb-sm">
      <span v-text="$t('block_explorer')"></span>
    </h6>
    <div class="row q-mb-lg">
      <div class="col-md-6 col-sm-12 q-pr-sm">
        <q-item tag="label" v-ripple>
          <q-item-section avatar>
            <q-toggle
              size="md"
              v-model="formData.lnbits_blockexplorer_enabled"
              checked-icon="check"
              color="green"
              unchecked-icon="clear"
            />
          </q-item-section>
          <q-item-section>
            <q-item-label v-text="$t('enable_block_explorer')"></q-item-label>
            <q-item-label
              caption
              v-text="$t('block_explorer_desc')"
            ></q-item-label>
          </q-item-section>
        </q-item>
      </div>
    </div>
    <q-separator class="q-mb-lg q-mt-sm"></q-separator>
    <div class="row q-col-gutter-md">
      <div class="col-12 col-md-8">
        <q-input
          filled
          v-model="formData.lnbits_blockexplorer_electrum_url"
          :label="$t('electrum_server_url')"
          :hint="$t('electrum_server_url_hint')"
        ></q-input>
      </div>
    </div>
  </q-card-section>
</template>
