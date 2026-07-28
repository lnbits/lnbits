<template id="lnbits-admin-server">
  <q-card-section class="q-pa-none">
    <div>
      <h6 class="q-my-none">
        <span v-text="$t('currency_settings')"></span>
      </h6>
      <div class="row q-col-gutter-md">
        <div class="col-12 col-md-6">
          <p>
            <span v-text="$t('allowed_currencies')"></span>
          </p>
          <q-select
            filled
            v-model="formData.lnbits_allowed_currencies"
            multiple
            :hint="$t('allowed_currencies_hint')"
            :label="$t('allowed_currencies')"
            :options="g.currencies"
          ></q-select>
        </div>
        <div class="col-12 col-md-6">
          <p>
            <span v-text="$t('default_account_currency')"></span>
          </p>
          <q-select
            filled
            v-model="formData.lnbits_default_accounting_currency"
            clearable
            :hint="$t('default_account_currency_hint')"
            :label="$t('currency')"
            :options="
              formData.lnbits_allowed_currencies?.length
                ? formData.lnbits_allowed_currencies
                : g.allowedCurrencies
            "
          ></q-select>
        </div>
      </div>

      <q-separator class="q-mb-lg q-mt-sm"></q-separator>
      <h6 class="q-my-none q-mb-sm">
        <span v-text="$t('payments')"></span>
      </h6>
      <div class="row q-col-gutter-md">
        <div class="col-12 col-md-4">
          <q-input
            filled
            type="number"
            v-model.number="formData.lnbits_max_outgoing_payment_amount_sats"
            :label="$t('max_outgoing_payment_amount')"
            step="1"
            min="0"
            :hint="$t('max_outgoing_payment_amount_desc')"
          ></q-input>
        </div>

        <div class="col-12 col-md-4">
          <q-input
            filled
            type="number"
            v-model.number="formData.lnbits_max_incoming_payment_amount_sats"
            :label="$t('max_incoming_payment_amount')"
            step="1"
            min="0"
            :hint="$t('max_incoming_payment_amount_desc')"
          ></q-input>
        </div>
        <div class="col-12 col-md-6"></div>
      </div>

      <q-separator class="q-mb-lg q-mt-sm"></q-separator>
      <h6 class="q-my-none q-mb-sm" v-text="$t('lightning_addresses')"></h6>
      <div class="row q-col-gutter-md">
        <div class="col-12 col-md-6 q-mt-sm">
          <q-item tag="label" v-ripple>
            <q-item-section>
              <q-item-label
                v-text="$t('enable_lightning_address')"
              ></q-item-label>
              <q-item-label
                caption
                v-text="$t('enable_lightning_address_for_all_wallets')"
              ></q-item-label>
            </q-item-section>
            <q-item-section avatar>
              <q-toggle
                size="md"
                v-model="formData.lnbits_enable_wallet_lightning_addresses"
                checked-icon="check"
                color="green"
                unchecked-icon="clear"
              />
            </q-item-section>
          </q-item>
        </div>
        <div
          v-if="formData.lnbits_enable_wallet_lightning_addresses"
          class="col-12 col-md-6 q-mt-sm"
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
                color="green"
                unchecked-icon="clear"
              />
            </q-item-section>
          </q-item>
        </div>
        <div
          v-if="formData.lnbits_enable_wallet_lightning_addresses"
          class="col-12 col-md-6 q-mt-sm"
        >
          <div>
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
                  color="green"
                  unchecked-icon="clear"
                />
              </q-item-section>
            </q-item>
          </div>
          <q-input
            v-if="formData.lnbits_charge_wallet_lightning_addresses"
            class="q-mt-sm"
            filled
            dense
            type="number"
            min="0"
            v-model.number="formData.lnbits_wallet_lightning_address_price_sats"
            :label="$t('lightning_address_price')"
            suffix="sats"
          ></q-input>
        </div>
        <div
          v-if="formData.lnbits_enable_wallet_lightning_addresses"
          class="col-12 col-md-6 q-mt-sm"
        >
          <q-input
            filled
            dense
            type="textarea"
            autogrow
            v-model="lightningAddressBlacklistText"
            :label="$t('lightning_address_blacklist')"
            :hint="$t('lightning_address_blacklist_instructions')"
          ></q-input>
        </div>
      </div>

      <q-separator class="q-mb-lg q-mt-md"></q-separator>
      <h6 class="q-my-none q-mb-sm">
        <span v-text="$t('wallet_limiter')"></span>
      </h6>
      <div class="row q-col-gutter-md">
        <div class="col-12 col-md-3">
          <q-input
            filled
            type="number"
            v-model.number="formData.lnbits_wallet_limit_max_balance"
            :label="$t('wallet_max_ballance')"
          ></q-input>
        </div>
        <div class="col-12 col-md-3">
          <q-input
            filled
            type="number"
            v-model.number="formData.lnbits_wallet_limit_daily_max_withdraw"
            :label="$t('wallet_limit_max_withdraw_per_day')"
          ></q-input>
        </div>
        <div class="col-12 col-md-3">
          <q-input
            filled
            type="number"
            v-model.number="formData.lnbits_wallet_limit_secs_between_trans"
            :label="$t('wallet_limit_secs_between_trans')"
          ></q-input>
        </div>
        <div class="col-12 col-md-3">
          <q-toggle
            v-model="formData.lnbits_only_allow_incoming_payments"
            :label="$t('only_incoming_payments_allowed')"
            ><q-tooltip v-text="$t('disable_outgoing_payments')"></q-tooltip
          ></q-toggle>
        </div>
      </div>

      <q-separator class="q-mb-lg q-mt-sm"></q-separator>
      <h6 class="q-my-none q-mb-sm">
        <span v-text="$t('service_fees')"></span>
      </h6>
      <div class="row q-col-gutter-md">
        <div class="col-12 col-md-4">
          <q-input
            filled
            type="number"
            v-model.number="formData.lnbits_service_fee"
            :label="$t('service_fee_label')"
            step="0.1"
            :suffix="'%'"
          ></q-input>
          <br />
        </div>
        <div class="col-12 col-md-4">
          <q-input
            filled
            type="number"
            v-model.number="formData.lnbits_service_fee_max"
            :label="$t('service_fee_max_label')"
            :suffix="$t('sats')"
          ></q-input>
          <br />
        </div>
        <div class="col-12 col-md-6">
          <q-input
            filled
            v-model="formData.lnbits_service_fee_wallet"
            :label="$t('fee_wallet_label')"
            :hint="$t('fee_wallet_hint')"
          ></q-input>
          <br />
        </div>
        <div class="col-12 col-md-6">
          <q-item tag="label" v-ripple>
            <q-item-section>
              <q-item-label v-text="$t('disable_fee')"></q-item-label>
            </q-item-section>
            <q-item-section avatar>
              <q-toggle
                size="md"
                v-model="formData.lnbits_service_fee_ignore_internal"
                checked-icon="check"
                color="green"
                unchecked-icon="clear"
              />
            </q-item-section>
          </q-item>
          <br />
        </div>
      </div>
    </div>
  </q-card-section>
</template>
