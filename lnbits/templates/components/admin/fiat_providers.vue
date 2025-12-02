<template id="lnbits-admin-fiat-providers">
  <h6 class="q-my-none q-mb-sm">
    <span v-text="$t('fiat_providers')"></span>
    <q-btn
      round
      flat
      @click="hideInputToggle = !hideInputToggle"
      :icon="hideInputToggle ? 'visibility_off' : 'visibility'"
    ></q-btn>
  </h6>
  <div class="row">
    <div class="col">
      <q-list bordered class="rounded-borders">
        <q-expansion-item header-class="text-primary text-bold">
          <template v-slot:header>
            <q-item-section avatar>
              <q-avatar>
                <q-img src="/static/images/stripe_logo.ico"></q-img>
              </q-avatar>
            </q-item-section>

            <q-item-section> Stripe </q-item-section>

            <q-item-section side>
              <div class="row items-center">
                <q-toggle
                  size="md"
                  :label="$t('enabled')"
                  v-model="formData.stripe_enabled"
                  color="green"
                  unchecked-icon="clear"
                />
              </div>
            </q-item-section>
          </template>

          <q-card class="q-pb-xl">
            <q-expansion-item :label="$t('api_stripe')" default-opened>
              <q-card-section class="q-pa-md">
                <q-input
                  filled
                  type="text"
                  v-model="formData.stripe_api_endpoint"
                  :label="$t('endpoint')"
                ></q-input>
                <q-input
                  filled
                  class="q-mt-md"
                  :type="hideInputToggle ? 'password' : 'text'"
                  v-model="formData.stripe_api_secret_key"
                  :label="$t('secret_key')"
                ></q-input>
                <q-input
                  filled
                  class="q-mt-md"
                  type="text"
                  v-model="formData.stripe_payment_success_url"
                  :label="$t('callback_success_url')"
                  :hint="$t('callback_success_url_hint')"
                ></q-input>
              </q-card-section>
              <q-card-section class="q-pa-md">
                <div class="row">
                  <div class="col">
                    <q-btn
                      outline
                      color="grey"
                      class="float-right"
                      :label="$t('check_connection')"
                      @click="checkFiatProvider('stripe')"
                    ></q-btn>
                  </div>
                </div>
              </q-card-section>
            </q-expansion-item>

            <q-expansion-item :label="$t('webhook')" default-opened>
              <q-card-section>
                <span v-text="$t('webhook_stripe_description')"></span>
              </q-card-section>
              <q-card-section>
                <q-input
                  filled
                  class="q-mt-md"
                  type="text"
                  disable
                  v-model="formData.stripe_payment_webhook_url"
                  :label="$t('webhook_url')"
                  :hint="$t('webhook_url_hint')"
                ></q-input>
                <q-input
                  filled
                  class="q-mt-md"
                  :type="hideInputToggle ? 'password' : 'text'"
                  v-model="formData.stripe_webhook_signing_secret"
                  :label="$t('signing_secret')"
                  :hint="$t('signing_secret_hint')"
                ></q-input>
              </q-card-section>
              <q-card-section>
                <span v-text="$t('webhook_events_list')"></span>
                <ul>
                  <li>
                    <code>checkout.session.completed</code>
                  </li>
                  - the user completed the checkout process
                  <li><code>invoice.paid</code></li>
                  - the invoice was successfully paid (for subscriptions)
                  <li><code>payment_intent.succeeded</code></li>
                  - the intent was successfully paid (for tap-to-pay in TPoS)
                </ul>
              </q-card-section>
            </q-expansion-item>
            <q-expansion-item :label="$t('service_fee')">
              <q-card-section>
                <div class="row">
                  <div class="col-md-4 col-sm-12">
                    <q-input
                      filled
                      class="q-ma-sm"
                      type="number"
                      min="0"
                      v-model="formData.stripe_limits.service_fee_percent"
                      @update:model-value="formData.touch = null"
                      :label="$t('service_fee_label')"
                      :hint="$t('service_fee_hint')"
                    ></q-input>
                  </div>
                  <div class="col-md-4 col-sm-12">
                    <q-input
                      filled
                      class="q-ma-sm"
                      type="number"
                      min="0"
                      v-model="formData.stripe_limits.service_max_fee_sats"
                      @update:model-value="formData.touch = null"
                      :label="$t('service_fee_max')"
                      :hint="$t('service_fee_max_hint')"
                    ></q-input>
                  </div>
                  <div class="col-md-4 col-sm-12">
                    <q-input
                      filled
                      class="q-ma-sm"
                      type="text"
                      v-model="formData.stripe_limits.service_fee_wallet_id"
                      @update:model-value="formData.touch = null"
                      :label="$t('fee_wallet_label')"
                      :hint="$t('fee_wallet_hint')"
                    ></q-input>
                  </div>
                </div>
              </q-card-section>
            </q-expansion-item>
            <q-expansion-item :label="$t('amount_limits')">
              <q-card-section>
                <div class="row">
                  <div class="col-md-4 col-sm-12">
                    <q-input
                      filled
                      class="q-ma-sm"
                      type="number"
                      min="0"
                      v-model="formData.stripe_limits.service_min_amount_sats"
                      @update:model-value="formData.touch = null"
                      :label="$t('min_incoming_payment_amount')"
                      :hint="$t('min_incoming_payment_amount_desc')"
                    ></q-input>
                  </div>
                  <div class="col-md-4 col-sm-12">
                    <q-input
                      filled
                      class="q-ma-sm"
                      type="number"
                      min="0"
                      v-model="formData.stripe_limits.service_max_amount_sats"
                      @update:model-value="formData.touch = null"
                      :label="$t('max_incoming_payment_amount')"
                      :hint="$t('max_incoming_payment_amount_desc')"
                    ></q-input>
                  </div>
                  <div class="col-md-4 col-sm-12">
                    <q-input
                      filled
                      class="q-ma-sm"
                      v-model="formData.stripe_limits.service_faucet_wallet_id"
                      @update:model-value="formData.touch = null"
                      :label="$t('faucest_wallet_id')"
                      :hint="$t('faucest_wallet_id_hint')"
                    ></q-input>
                  </div>
                </div>
                <q-item>
                  <q-item-section>
                    <q-item-label v-text="$t('faucest_wallet')"></q-item-label>
                    <q-item-label caption>
                      <ul>
                        <li>
                          <span
                            v-text="
                              $t('faucest_wallet_desc_1', {
                                provider: 'stripe'
                              })
                            "
                          ></span>
                        </li>
                        <li>
                          <span
                            v-text="
                              $t('faucest_wallet_desc_2', {
                                provider: 'stripe'
                              })
                            "
                          ></span>
                        </li>
                        <li>
                          <span v-text="$t('faucest_wallet_desc_3')"></span>
                        </li>
                        <li>
                          <span
                            v-text="
                              $t('faucest_wallet_desc_4', {
                                provider: 'stripe'
                              })
                            "
                          ></span>
                        </li>
                        <li>
                          <span v-text="$t('faucest_wallet_desc_5')"></span>
                        </li>
                      </ul>
                      <br />
                    </q-item-label>
                  </q-item-section>
                </q-item>
              </q-card-section>
            </q-expansion-item>
            <q-expansion-item :label="$t('allowed_users')">
              <q-card-section>
                <q-input
                  filled
                  v-model="formAddStripeUser"
                  @keydown.enter="addStripeAllowedUser"
                  type="text"
                  :label="$t('allowed_users_label')"
                  :hint="
                    $t('allowed_users_hint_feature', {
                      feature: 'Stripe'
                    })
                  "
                >
                  <q-btn
                    @click="addStripeAllowedUser"
                    dense
                    flat
                    icon="add"
                  ></q-btn>
                </q-input>
                <div>
                  <q-chip
                    v-for="user in formData.stripe_limits.allowed_users"
                    @update:model-value="formData.touch = null"
                    :key="user"
                    removable
                    @remove="removeStripeAllowedUser(user)"
                    color="primary"
                    text-color="white"
                    :label="user"
                    class="ellipsis"
                  >
                  </q-chip>
                </div>
              </q-card-section>
            </q-expansion-item>
          </q-card>
        </q-expansion-item>

        <q-separator />

        <q-expansion-item header-class="text-primary text-bold">
          <template v-slot:header>
            <q-item-section avatar>
              <q-avatar>
                <q-img src="/static/images/square_logo.png"></q-img>
              </q-avatar>
            </q-item-section>

            <q-item-section> Square </q-item-section>

            <q-item-section side>
              <div class="row items-center">Disabled</div>
            </q-item-section>
          </template>

          <q-card>
            <q-card-section> Coming Soon </q-card-section>
          </q-card>
        </q-expansion-item>
      </q-list>
    </div>
  </div>
</template>
