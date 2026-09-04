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
        <q-item tag="label" v-ripple>
          <q-item-section avatar>
            <q-toggle
              size="md"
              v-model="formData.lnbits_blockexplorer_public_api"
              checked-icon="check"
              color="green"
              unchecked-icon="clear"
            />
          </q-item-section>
          <q-item-section>
            <q-item-label
              v-text="$t('blockexplorer_public_api')"
            ></q-item-label>
            <q-item-label
              caption
              v-text="$t('blockexplorer_public_api_desc')"
            ></q-item-label>
          </q-item-section>
        </q-item>
        <q-item tag="label" v-ripple>
          <q-item-section avatar>
            <q-toggle
              size="md"
              v-model="formData.lnbits_blockexplorer_in_user_menu"
              :disable="!formData.lnbits_blockexplorer_public_api"
              checked-icon="check"
              color="green"
              unchecked-icon="clear"
            />
          </q-item-section>
          <q-item-section>
            <q-item-label
              v-text="$t('blockexplorer_in_user_menu')"
            ></q-item-label>
            <q-item-label
              caption
              v-text="$t('blockexplorer_in_user_menu_desc')"
            ></q-item-label>
          </q-item-section>
        </q-item>
        <div
          v-if="formData.lnbits_blockexplorer_public_api"
          class="q-pl-lg q-mt-xs"
        >
          <q-btn
            type="a"
            href="/blockexplorer/public"
            target="_blank"
            rel="noopener noreferrer"
            icon="open_in_new"
            :label="$t('view_public_block_explorer')"
            color="primary"
            flat
            dense
          ></q-btn>
        </div>
      </div>
    </div>
    <q-separator class="q-mb-lg q-mt-md"></q-separator>
    <h6 class="q-my-none q-mb-sm">
      <span v-text="$t('electrum_compatible_server')"></span>
    </h6>
    <div class="row q-col-gutter-md">
      <div class="col-12 col-md-4">
        <q-select
          filled
          v-model="electrumServerPreset"
          :options="electrumServerOptions"
          :label="$t('electrum_server_url')"
          :hint="$t('electrum_server_url_hint')"
        ></q-select>
      </div>
      <div class="col-12 col-md-4" v-if="electrumServerPreset === 'Custom'">
        <q-input
          filled
          v-model="formData.lnbits_blockexplorer_electrum_url"
          :label="$t('electrum_server_url_custom')"
          :hint="$t('electrum_server_url_hint')"
        ></q-input>
      </div>
      <div class="col-12 col-md-4">
        <q-select
          filled
          v-model="formData.lnbits_blockexplorer_network"
          :options="['main', 'test', 'regtest', 'signet']"
          :label="$t('blockexplorer_network')"
          :hint="$t('blockexplorer_network_hint')"
        ></q-select>
      </div>
      <div class="col-12">
        <q-btn
          type="a"
          href="https://1209k.com/bitcoin-eye/ele.php?chain=btc"
          target="_blank"
          rel="noopener noreferrer"
          icon="open_in_new"
          :label="$t('view_public_electrum_servers')"
          color="primary"
          flat
          dense
        ></q-btn>
      </div>
    </div>
  </q-card-section>
</template>
