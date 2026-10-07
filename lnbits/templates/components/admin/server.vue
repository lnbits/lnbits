<template id="lnbits-admin-server">
  <q-card-section class="q-pa-none">
    <h6 class="q-my-none q-mb-sm">Onchain payments</h6>
    <q-item tag="label" class="q-px-none">
      <q-item-section>
        <q-item-label>Allow onchain payments</q-item-label>
        <q-item-label caption>
          Allow users to create and send from server-managed Bitcoin wallets in
          Watchonly. Hardware and watch-only wallets remain available. Turning
          this off keeps existing wallets and recovery backups.
        </q-item-label>
      </q-item-section>
      <q-item-section avatar>
        <q-toggle
          v-model="formData.lnbits_allow_onchain_payments"
          :disable="
            !isSuperUser ||
            (!formData.lnbits_allow_onchain_payments &&
              !onchain?.backup_confirmed)
          "
          checked-icon="check"
          unchecked-icon="clear"
          color="primary"
          aria-label="Allow onchain payments"
        ></q-toggle>
      </q-item-section>
    </q-item>
    <div v-if="!isSuperUser" class="text-caption text-grey q-mb-md">
      The super user manages onchain payments and encryption key backups.
    </div>
    <div v-else class="q-mt-sm q-mb-lg">
      <q-banner
        v-if="onchainError"
        class="bg-negative text-white rounded-borders"
      >
        <span v-text="onchainError"></span>
        <template v-slot:action
          ><q-btn flat label="Retry" @click="loadOnchainStatus"></q-btn
        ></template>
      </q-banner>
      <q-linear-progress v-else-if="!onchain" indeterminate></q-linear-progress>
      <template v-else>
        <div class="row items-center q-gutter-sm q-mb-sm">
          <q-icon
            :name="onchain.configured ? 'lock' : 'key'"
            :color="onchain.configured ? 'positive' : 'warning'"
          ></q-icon>
          <span
            v-text="
              onchain.configured
                ? onchain.backup_confirmed
                  ? 'Encryption key backed up'
                  : 'Back up your encryption key to continue'
                : 'Set up your encryption key'
            "
          ></span>
        </div>
        <p class="text-caption text-grey">
          LNbits encrypts server wallet recovery phrases with this key. Generate
          it once, then keep a recovery copy somewhere safe. Setup and backup
          actions take effect immediately; use Save to apply the payment toggle.
        </p>
        <q-banner
          v-if="onchain.error && onchain.fingerprint"
          class="q-mb-md rounded-borders bg-warning text-black"
        >
          <span v-text="onchain.error"></span>
        </q-banner>
        <div class="row q-gutter-sm">
          <q-btn
            v-if="!onchain.configured && !onchain.fingerprint"
            color="primary"
            unelevated
            label="Generate encryption key"
            icon="key"
            :loading="onchainBusy"
            @click="setupOnchain"
          ></q-btn>
          <q-btn
            v-if="onchain.configured"
            outline
            color="primary"
            label="Back up encryption key"
            icon="download"
            :disable="onchainBusy"
            @click="openOnchainBackup"
          ></q-btn>
        </div>
        <q-expansion-item
          v-if="!onchain.configured"
          label="Restore an encryption key"
          icon="restore"
          class="q-mt-md"
        >
          <q-card-section class="q-px-none">
            <p class="text-caption">
              Restoring an instance? Restore its database and upload its
              original key backup. Existing keys cannot be replaced.
            </p>
            <q-file
              filled
              dense
              v-model="restoreFile"
              accept=".json,application/json"
              label="Encryption key backup"
              :max-file-size="4096"
              :disable="onchainBusy"
            ></q-file>
            <q-btn
              class="q-mt-sm"
              outline
              color="primary"
              label="Restore key"
              :disable="!restoreFile"
              :loading="onchainBusy"
              @click="restoreOnchain"
            ></q-btn>
          </q-card-section>
        </q-expansion-item>
        <div v-if="onchain.configured" class="text-caption text-grey q-mt-sm">
          <span v-if="onchain.source === 'file'"
            >Stored in the LNbits data folder and included in Download
            backup.</span
          >
          <span v-else
            >Supplied by the server environment. Keep a separate key backup;
            database backups do not include environment variables.</span
          >
        </div>
      </template>
    </div>
    <q-dialog v-model="backupDialog" :persistent="onchainBusy">
      <q-card style="width: 520px; max-width: 95vw">
        <q-card-section>
          <div class="text-h6">Back up your onchain encryption key</div>
          <p class="q-mt-md">
            Keep this file in a secure place, separately from your database
            backup. Anyone with both can recover the server wallets.
          </p>
          <p>
            If this key is lost, LNbits cannot unlock its server wallets. Users
            can still recover with their own wallet recovery phrases.
          </p>
          <q-btn
            color="primary"
            unelevated
            icon="download"
            label="Download key backup"
            :loading="onchainBusy"
            @click="downloadOnchainBackup"
          ></q-btn>
          <q-checkbox
            class="q-mt-md"
            v-model="backupSaved"
            :disable="!backupDownloaded"
            label="I have stored this key backup somewhere safe"
          ></q-checkbox>
        </q-card-section>
        <q-card-actions align="right">
          <q-btn
            flat
            label="Close"
            v-close-popup
            :disable="onchainBusy"
          ></q-btn>
          <q-btn
            color="primary"
            label="Confirm backup"
            :disable="!backupDownloaded || !backupSaved"
            :loading="onchainBusy"
            @click="confirmOnchainBackup"
          ></q-btn>
        </q-card-actions>
      </q-card>
    </q-dialog>
    <q-separator class="q-mb-lg q-mt-md"></q-separator>
    <h6 class="q-my-none q-mb-sm" v-text="$t('currency_settings')"></h6>
    <div
      class="text-caption text-grey q-mb-md"
      v-text="$t('currency_settings_desc')"
    ></div>
    <div class="row q-col-gutter-lg">
      <div class="col-12 col-md-6">
        <q-select
          dense
          filled
          v-model="formData.lnbits_allowed_currencies"
          multiple
          use-chips
          :hint="$t('allowed_currencies_hint')"
          :label="$t('allowed_currencies')"
          :options="g.currencies"
        ></q-select>
      </div>
      <div class="col-12 col-md-6">
        <q-select
          dense
          filled
          v-model="formData.lnbits_default_accounting_currency"
          clearable
          :hint="$t('default_account_currency_hint')"
          :label="$t('default_account_currency')"
          :options="
            formData.lnbits_allowed_currencies?.length
              ? formData.lnbits_allowed_currencies
              : g.allowedCurrencies
          "
        ></q-select>
      </div>
    </div>

    <q-separator class="q-mb-lg q-mt-md"></q-separator>
    <div class="row items-center q-gutter-sm q-mb-sm">
      <h6 class="q-my-none" v-text="$t('payment_limits')"></h6>
      <q-icon name="warning_amber" color="warning" size="20px">
        <q-tooltip v-text="$t('payment_limits_warning')"></q-tooltip>
      </q-icon>
    </div>
    <div
      class="text-caption text-grey q-mb-md"
      v-text="$t('payment_limits_desc')"
    ></div>
    <div class="row q-col-gutter-lg">
      <div class="col-12 col-md-6">
        <q-input
          dense
          filled
          type="number"
          v-model.number="formData.lnbits_max_outgoing_payment_amount_sats"
          :label="$t('max_outgoing_payment_amount')"
          :suffix="$t('sats')"
          step="1"
          min="0"
          :hint="$t('max_outgoing_payment_amount_desc')"
        ></q-input>
      </div>
      <div class="col-12 col-md-6">
        <q-input
          dense
          filled
          type="number"
          v-model.number="formData.lnbits_max_incoming_payment_amount_sats"
          :label="$t('max_incoming_payment_amount')"
          :suffix="$t('sats')"
          step="1"
          min="0"
          :hint="$t('max_incoming_payment_amount_desc')"
        ></q-input>
      </div>
    </div>

    <q-separator class="q-mb-lg q-mt-md"></q-separator>
    <q-expansion-item
      default-opened
      icon="alternate_email"
      :label="$t('lightning_addresses')"
      :caption="$t('lightning_addresses_desc')"
    >
      <q-card-section class="row q-col-gutter-lg">
        <div class="col-12">
          <q-select
            dense
            filled
            emit-value
            map-options
            v-model="formData.lnbits_ln_address_mode"
            :label="$t('ln_address_mode')"
            :hint="$t('ln_address_mode_hint')"
            :options="[
              {label: $t('ln_address_core_first'), value: 'core_first'},
              {
                label: $t('ln_address_extension_first'),
                value: 'extension_first'
              },
              {
                label: $t('ln_address_extension_only'),
                value: 'extension_only'
              }
            ]"
          ></q-select>
        </div>
        <div
          v-if="formData.lnbits_ln_address_mode != 'extension_only'"
          class="col-12 col-md-6"
        >
          <q-item tag="label" v-ripple>
            <q-item-section>
              <q-item-label
                v-text="$t('allow_users_specify_lightning_addresses')"
              ></q-item-label>
              <q-item-label
                caption
                v-text="
                  $t('allow_wallet_owners_set_custom_lightning_addresses')
                "
              ></q-item-label>
            </q-item-section>
            <q-item-section avatar>
              <q-toggle
                size="md"
                v-model="
                  formData.lnbits_allow_custom_wallet_lightning_addresses
                "
                checked-icon="check"
                color="primary"
                unchecked-icon="clear"
              />
            </q-item-section>
          </q-item>
        </div>
        <div
          v-if="formData.lnbits_ln_address_mode != 'extension_only'"
          class="col-12 col-md-6"
        >
          <q-item tag="label" v-ripple>
            <q-item-section>
              <q-item-label
                v-text="$t('charge_for_lightning_addresses')"
              ></q-item-label>
              <q-item-label
                caption
                v-text="$t('charge_users_set_change_lightning_address')"
              ></q-item-label>
              <q-item-label
                caption
                v-text="$t('service_fee_wallet_id_must_be_set')"
              ></q-item-label>
            </q-item-section>
            <q-item-section avatar>
              <q-toggle
                size="md"
                v-model="formData.lnbits_charge_wallet_lightning_addresses"
                checked-icon="check"
                color="primary"
                unchecked-icon="clear"
              />
            </q-item-section>
          </q-item>
          <q-input
            dense
            v-if="formData.lnbits_charge_wallet_lightning_addresses"
            class="q-mt-sm"
            filled
            type="number"
            min="0"
            v-model.number="formData.lnbits_wallet_lightning_address_price_sats"
            :label="$t('lightning_address_price')"
            :suffix="$t('sats')"
          ></q-input>
        </div>
        <div
          v-if="formData.lnbits_ln_address_mode != 'extension_only'"
          class="col-12"
        >
          <q-input
            dense
            filled
            type="textarea"
            autogrow
            v-model="lightningAddressBlacklistText"
            :label="$t('lightning_address_blacklist')"
            :hint="$t('lightning_address_blacklist_instructions')"
          ></q-input>
        </div>
      </q-card-section>
    </q-expansion-item>

    <q-separator class="q-mb-lg q-mt-md"></q-separator>
    <div class="row items-center q-gutter-sm q-mb-sm">
      <h6 class="q-my-none" v-text="$t('wallet_limiter')"></h6>
      <q-icon name="warning_amber" color="warning" size="20px">
        <q-tooltip v-text="$t('wallet_limiter_warning')"></q-tooltip>
      </q-icon>
    </div>
    <div
      class="text-caption text-grey q-mb-md"
      v-text="$t('wallet_limiter_desc')"
    ></div>
    <div class="row q-col-gutter-lg">
      <div class="col-12 col-md-4">
        <q-input
          dense
          filled
          type="number"
          min="0"
          v-model.number="formData.lnbits_wallet_limit_max_balance"
          :label="$t('wallet_max_ballance')"
          :suffix="$t('sats')"
          :hint="$t('zero_disables_limit')"
        ></q-input>
      </div>
      <div class="col-12 col-md-4">
        <q-input
          dense
          filled
          type="number"
          min="0"
          v-model.number="formData.lnbits_wallet_limit_daily_max_withdraw"
          :label="$t('wallet_limit_max_withdraw_per_day')"
          :suffix="$t('sats')"
          :hint="$t('zero_disables_limit')"
        ></q-input>
      </div>
      <div class="col-12 col-md-4">
        <q-input
          dense
          filled
          type="number"
          min="0"
          v-model.number="formData.lnbits_wallet_limit_secs_between_trans"
          :label="$t('wallet_limit_secs_between_trans')"
          :suffix="$t('seconds')"
          :hint="$t('zero_disables_limit')"
        ></q-input>
      </div>
      <div class="col-12">
        <div
          class="text-subtitle2 q-mb-sm"
          v-text="$t('payment_permissions')"
        ></div>
        <q-btn-toggle
          :model-value="formData.lnbits_only_allow_incoming_payments"
          @update:model-value="
            value => (formData.lnbits_only_allow_incoming_payments = value)
          "
          spread
          no-caps
          unelevated
          toggle-color="primary"
          :options="[
            {label: $t('send_and_receive'), value: false},
            {label: $t('receive_only'), value: true}
          ]"
          aria-label="Payment permissions"
        ></q-btn-toggle>
        <div
          class="text-caption text-grey q-mt-xs"
          v-text="$t('payment_permissions_desc')"
        ></div>
      </div>
    </div>

    <q-separator class="q-mb-lg q-mt-md"></q-separator>
    <q-expansion-item
      icon="percent"
      :label="$t('service_fees')"
      :caption="`${$t('advanced')} · ${$t('service_fees_desc')}`"
    >
      <q-card-section class="row q-col-gutter-lg">
        <div class="col-12 col-md-6">
          <q-input
            dense
            filled
            type="number"
            v-model.number="formData.lnbits_service_fee"
            :label="$t('service_fee_label')"
            step="0.1"
            suffix="%"
            :hint="$t('service_fee_hint')"
          ></q-input>
        </div>
        <div class="col-12 col-md-6">
          <q-input
            dense
            filled
            type="number"
            v-model.number="formData.lnbits_service_fee_max"
            :label="$t('service_fee_max_label')"
            :suffix="$t('sats')"
            :hint="$t('service_fee_max_hint')"
          ></q-input>
        </div>
        <div class="col-12 col-md-6">
          <q-input
            dense
            filled
            v-model="formData.lnbits_service_fee_wallet"
            :label="$t('fee_wallet_label')"
            :hint="$t('fee_wallet_hint')"
          ></q-input>
        </div>
        <div class="col-12 col-md-6">
          <q-item tag="label" v-ripple>
            <q-item-section>
              <q-item-label v-text="$t('disable_fee')"></q-item-label>
              <q-item-label
                caption
                v-text="$t('disable_fee_desc')"
              ></q-item-label>
            </q-item-section>
            <q-item-section avatar>
              <q-toggle
                size="md"
                v-model="formData.lnbits_service_fee_ignore_internal"
                checked-icon="check"
                color="primary"
                unchecked-icon="clear"
              />
            </q-item-section>
          </q-item>
        </div>
      </q-card-section>
    </q-expansion-item>
  </q-card-section>
</template>
