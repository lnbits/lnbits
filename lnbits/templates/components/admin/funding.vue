<template id="lnbits-admin-funding">
  <q-card-section class="q-pa-none">
    <h6 class="q-my-none">
      <span v-text="$t('wallets_management')"></span>
    </h6>
    <br />
    <div>
      <div class="row">
        <div class="col">
          <p>
            <span v-text="$t('funding_source_info')"></span>
          </p>
          <ul>
            <li
              v-text="
                $t('funding_source', {
                  wallet_class: settings.lnbits_backend_wallet_class
                })
              "
            ></li>
            <li
              v-text="
                $t('node_balance', {
                  balance: (auditData.node_balance_sats || 0).toLocaleString()
                })
              "
            ></li>
            <li
              v-text="
                $t('lnbits_balance', {
                  balance: (auditData.lnbits_balance_sats || 0).toLocaleString()
                })
              "
            ></li>
            <li
              v-text="
                $t('funding_reserve_percent', {
                  percent:
                    auditData.lnbits_balance_sats > 0
                      ? (
                          (auditData.node_balance_sats /
                            auditData.lnbits_balance_sats) *
                          100
                        ).toFixed(2)
                      : 100
                })
              "
            ></li>
          </ul>
          <br />
        </div>
        <div class="col">
          <div v-if="g.settings.hasNodemanager">
            <p>
              <span v-text="$t('node_management')"></span>
            </p>
            <q-toggle
              :label="$t('toggle_node_ui')"
              v-model="formData.lnbits_node_ui"
            ></q-toggle>
            <q-toggle
              v-if="formData.lnbits_node_ui"
              :label="$t('toggle_public_node_ui')"
              v-model="formData.lnbits_public_node_ui"
            ></q-toggle>
            <br />
            <q-toggle
              v-if="formData.lnbits_node_ui"
              :label="$t('toggle_transactions_node_ui')"
              v-model="formData.lnbits_node_ui_transactions"
            ></q-toggle>
          </div>
          <p v-if="!g.settings.hasNodemanager">
            <span v-text="$t('node_management_not_supported')"></span>
          </p>
        </div>
      </div>
      <div class="row q-col-gutter-md">
        <div class="col-12">
          <h6 class="q-my-none">
            <span v-text="$t('routing_fee_reserve_calculations')"></span>
          </h6>
          <p class="q-mt-sm q-mb-none">
            <span v-html="$t('routing_fee_reserve_calculations_desc')"></span>
          </p>
        </div>
        <div class="col-12 col-md-4">
          <p>
            <span v-text="$t('fee_reserve')"></span>
            <sup>
              <q-icon name="info" size="16px" class="q-ml-xs"></q-icon>
              <q-tooltip max-width="300px">
                <span v-html="$t('fee_reserve_min_hint')"></span>
              </q-tooltip>
            </sup>
          </p>
          <q-input
            type="number"
            filled
            v-model="formData.lnbits_reserve_fee_min"
            :suffix="$t('millisats')"
          >
          </q-input>
        </div>
        <div class="col-12 col-md-4">
          <p>
            <span v-text="$t('fee_reserve_percent')"></span>
            <sup>
              <q-icon name="info" size="16px" class="q-ml-xs"></q-icon>
              <q-tooltip max-width="300px">
                <span v-html="$t('fee_reserve_percent_hint')"></span>
              </q-tooltip>
            </sup>
          </p>
          <q-input
            type="number"
            filled
            name="lnbits_reserve_fee_percent"
            v-model="formData.lnbits_reserve_fee_percent"
            step="0.1"
            suffix="%"
          ></q-input>
        </div>
      </div>
      <div class="row q-col-gutter-md q-mt-sm">
        <div class="col-12">
          <h6 class="q-my-none">
            <span v-text="$t('payment_timeouts')"></span>
          </h6>
        </div>
        <div class="col-12 col-md-4">
          <p><span v-text="$t('invoice_expiry')"></span></p>
          <q-input
            filled
            v-model.number="formData.lightning_invoice_expiry"
            type="number"
            :suffix="$t('seconds')"
            mask="#######"
          >
          </q-input>
        </div>
        <div class="col-12 col-md-4">
          <p>
            <span v-text="$t('payment_wait_time')"></span>
            <sup>
              <q-icon name="info" size="16px" class="q-ml-xs"></q-icon>
              <q-tooltip max-width="300px">
                <span v-text="$t('payment_wait_time_tooltip')"></span>
              </q-tooltip>
            </sup>
          </p>
          <q-input
            type="number"
            filled
            name="lnbits_funding_source_pay_invoice_wait_seconds"
            v-model="formData.lnbits_funding_source_pay_invoice_wait_seconds"
            :hint="$t('payment_wait_time_desc')"
            :suffix="$t('seconds')"
            step="1"
            min="0"
          ></q-input>
        </div>
      </div>
      <div v-if="isSuperUser">
        <lnbits-admin-funding-sources
          :form-data="formData"
          :allowed-funding-sources="settings.lnbits_allowed_funding_sources"
        />
        <div class="row q-col-gutter-md q-my-md">
          <div class="col-12 col-sm-8">
            <q-item tag="div">
              <q-item-section>
                <q-item-label
                  v-text="$t('funding_source_retries')"
                ></q-item-label>
                <q-item-label
                  caption
                  v-text="$t('funding_source_retries_desc')"
                ></q-item-label>
              </q-item-section>
              <q-item-section>
                <q-input
                  filled
                  v-model="formData.funding_source_max_retries"
                  type="number"
                />
              </q-item-section>
            </q-item>
          </div>
        </div>
      </div>
      <q-separator></q-separator>
      <h6 class="q-mt-lg q-mb-sm">
        <p v-text="$t('watchdog')"></p>
      </h6>
      <div class="row q-col-gutter-md">
        <div class="col-12">
          <p v-text="$t('watchdog_introduction')"></p>
        </div>
      </div>
      <div class="row q-col-gutter-md">
        <div class="col-12 col-md-6">
          <q-item tag="label" v-ripple>
            <q-item-section>
              <q-item-label v-text="$t('enable_watchdog')"></q-item-label>
              <q-item-label
                caption
                v-text="$t('enable_watchdog_desc')"
              ></q-item-label>
            </q-item-section>
            <q-item-section avatar>
              <q-toggle
                size="md"
                v-model="formData.lnbits_watchdog_switch_to_voidwallet"
                checked-icon="check"
                color="green"
                unchecked-icon="clear"
              />
            </q-item-section>
          </q-item>
        </div>
        <div class="col-12 col-md-6">
          <q-item tag="label" v-ripple>
            <q-item-section>
              <q-item-label
                v-text="$t('notification_watchdog_limit')"
              ></q-item-label>
              <q-item-label
                caption
                v-text="$t('notification_watchdog_limit_desc')"
              ></q-item-label>
            </q-item-section>
            <q-item-section avatar>
              <q-toggle
                size="md"
                v-model="formData.lnbits_notification_watchdog"
                checked-icon="check"
                color="green"
                unchecked-icon="clear"
              />
            </q-item-section>
          </q-item>
        </div>
        <div class="col-12 col-md-6">
          <q-item tag="label" v-ripple>
            <q-item-section>
              <q-item-label v-text="$t('watchdog_interval')"></q-item-label>
              <q-item-label
                caption
                v-text="$t('watchdog_interval_desc')"
              ></q-item-label>
            </q-item-section>
            <q-item-section>
              <q-input
                filled
                v-model="formData.lnbits_watchdog_interval_minutes"
                type="number"
              />
            </q-item-section>
          </q-item>
        </div>
        <div class="col-12 col-md-6">
          <q-item tag="label" v-ripple>
            <q-item-section>
              <q-item-label v-text="$t('watchdog_delta')"></q-item-label>
              <q-item-label
                caption
                v-text="$t('watchdog_delta_desc')"
              ></q-item-label>
            </q-item-section>
            <q-item-section>
              <q-input
                filled
                v-model="formData.lnbits_watchdog_delta"
                :suffix="$t('sats')"
                type="number"
              />
            </q-item-section>
          </q-item>
        </div>
      </div>
    </div>
  </q-card-section>
</template>
