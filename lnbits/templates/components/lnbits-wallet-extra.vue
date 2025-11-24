<template id="lnbits-wallet-extra">
  <q-card class="wallet-extra">
    <q-card-section class="q-pb-xs">
      <div class="row items-center">
        <q-avatar
          size="lg"
          :icon="g.wallet.extra.icon"
          :text-color="$q.dark.isActive ? 'black' : 'grey-3'"
          :color="g.wallet.extra.color"
        >
        </q-avatar>
        <lnbits-wallet-icon @update-wallet="updateWallet"></lnbits-wallet-icon>
        <div class="text-subtitle1 q-mt-none q-mb-none">
          <span v-text="$t('wallet')"></span>
          <strong><em v-text="g.wallet.name"></em></strong>
        </div>
        <q-space></q-space>
        <div class="float-right">
          <q-btn
            @click="updateWallet({pinned: !g.wallet.extra.pinned})"
            round
            class="float-right"
            :color="g.wallet.extra.pinned ? 'primary' : 'grey-5'"
            text-color="black"
            size="sm"
            icon="push_pin"
            style="transform: rotate(30deg)"
          >
            <q-tooltip><span v-text="$t('pin_wallet')"></span></q-tooltip>
          </q-btn>
        </div>
      </div>
    </q-card-section>
    <q-card-section class="q-pa-none">
      <q-separator></q-separator>
      <q-list>
        <lnbits-wallet-paylinks
          @send-lnurl="handleSendLnurl"
        ></lnbits-wallet-paylinks>
        <q-separator></q-separator>
        <lnbits-wallet-share></lnbits-wallet-share>
        <q-separator></q-separator>
        <q-expansion-item
          group="extras"
          icon="phone_android"
          :label="$t('access_wallet_on_mobile')"
        >
          <q-card>
            <q-card-section>
              You can connect to this wallet from a mobile app:
              <ul>
                <li>
                  Download
                  <a class="text-secondary" href="https://zeusln.app">Zeus</a>
                  or
                  <a class="text-secondary" href="https://bluewallet.io/"
                    >BlueWallet</a
                  >
                  from App Store or Google Play
                </li>
                <li>
                  Enable the
                  <a class="text-secondary" href="/lndhub">LndHub </a>
                  extension for this account
                </li>
                <li>
                  Scan the QR code in the
                  <a class="text-secondary" href="/lndhub">LndHub </a>
                  extensions with your mobile app
                </li>
              </ul>
            </q-card-section>
            <q-card-section>
              Or you can access the wallet directly from your mobile browser
              using:
              <q-expansion-item
                icon="mobile_friendly"
                :label="$t('export_to_phone')"
              >
                <q-card>
                  <q-card-section>
                    <p
                      class="text-center"
                      v-text="$t('export_to_phone_desc')"
                    ></p>
                    <lnbits-qrcode
                      :value="`${baseUrl}wallet?usr=${g.user.id}&wal=${g.wallet.id}`"
                    ></lnbits-qrcode>
                  </q-card-section>
                </q-card>
              </q-expansion-item>
            </q-card-section>
          </q-card>
        </q-expansion-item>
        <q-separator></q-separator>
        <q-expansion-item
          group="extras"
          icon="settings"
          :label="$t('wallet_config')"
        >
          <q-card>
            <q-card-section>
              <div class="row">
                <div class="col-6">
                  <q-input filled v-model="g.wallet.name" label="Name" dense />
                </div>
                <div class="col-4 q-pl-sm">
                  <q-btn
                    :disable="!g.wallet.name.length"
                    unelevated
                    class="q-mt-xs full-width"
                    color="primary"
                    :label="$t('update_name')"
                    dense
                    @click="updateWallet({name: g.wallet.name})"
                  ></q-btn>
                </div>
                <div class="col-2"></div>
              </div>
            </q-card-section>
            <q-card-section v-if="g.isSatsDenomination">
              <div class="row">
                <div class="col-6">
                  <q-select
                    filled
                    dense
                    v-model="g.wallet.currency"
                    @change="updateWallet({currency: g.wallet.currency})"
                    type="text"
                    :disable="g.fiatTracking"
                    :options="g.allowedCurrencies"
                    :label="$t('currency_settings')"
                  ></q-select>
                </div>
                <div class="col-4 q-pl-sm">
                  <q-btn
                    dense
                    color="primary"
                    class="q-mt-xs full-width"
                    @click="handleFiatTracking()"
                    :disable="g.wallet.currency == ''"
                    :label="g.fiatTracking ? 'Remove' : 'Add'"
                  ></q-btn>
                </div>
                <div class="col-2">
                  <q-btn
                    v-if="g.user.admin"
                    flat
                    round
                    icon="settings"
                    class="float-right q-mb-lg"
                    to="/admin#exchange_providers"
                    ><q-tooltip v-text="$t('exchange_providers')"></q-tooltip
                  ></q-btn>
                </div>
              </div>
            </q-card-section>
            <q-card-section>
              <div class="row">
                <div class="col-6">
                  <p v-text="$t('delete_wallet_desc')"></p>
                </div>
                <div class="col-4 q-pl-sm">
                  <q-btn
                    unelevated
                    color="red-10"
                    class="full-width"
                    @click="deleteWallet()"
                    :label="$t('delete_wallet')"
                  ></q-btn>
                </div>
                <div class="col-2"></div>
              </div>
            </q-card-section>
          </q-card>
        </q-expansion-item>
        <q-separator></q-separator>
        <q-expansion-item
          group="extras"
          icon="insights"
          :label="$t('wallet_charts')"
        >
          <q-card>
            <q-card-section>
              <div class="row">
                <div class="col-md-4 col-sm-12">
                  <q-checkbox
                    dense
                    v-model="chartConfig.showBalanceChart"
                    :label="$t('payments_balance_chart')"
                  >
                  </q-checkbox>
                </div>

                <div class="col-md-4 col-sm-12">
                  <q-checkbox
                    dense
                    v-model="chartConfig.showBalanceInOutChart"
                    :label="$t('payments_balance_in_out_chart')"
                  >
                  </q-checkbox>
                </div>
                <div class="col-md-4 col-sm-12">
                  <q-checkbox
                    dense
                    v-model="chartConfig.showPaymentInOutChart"
                    :label="$t('payments_count_in_out_chart')"
                  >
                  </q-checkbox>
                </div>
              </div>
            </q-card-section>
          </q-card>
        </q-expansion-item>
        <q-separator></q-separator>
        <lnbits-wallet-api-docs></lnbits-wallet-api-docs>
      </q-list>
    </q-card-section>
  </q-card>
</template>
