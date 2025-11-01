<template id="lnbits-wallet-details">
  <q-card>
    <q-card-section class="q-pb-xs">
      <div class="row items-center">
        <q-avatar
          size="lg"
          :icon="g.wallet.extra.icon"
          :text-color="$q.dark.isActive ? 'black' : 'grey-3'"
          :color="g.wallet.extra.color"
        >
        </q-avatar>
        <q-btn
          @click="icon.show = true"
          round
          color="grey-5"
          text-color="black"
          size="xs"
          icon="edit"
          style="position: relative; left: -15px; bottom: -10px"
        ></q-btn>
        <div class="text-subtitle1 q-mt-none q-mb-none">
          <span v-text="walletTitle"></span>
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
        <q-expansion-item
          v-if="g.wallet.lnurlwithdraw_full"
          group="extras"
          icon="crop_free"
          :label="$t('drain_funds')"
        >
          <q-card>
            <q-card-section>
              <lnbits-qrcode
                :value="'lightning:' + g.wallet.lnurlwithdraw_full"
                :href="'lightning:' + g.wallet.lnurlwithdraw_full"
              ></lnbits-qrcode>
              <p class="text-center" v-text="$t('drain_funds_desc')"></p>
            </q-card-section>
          </q-card>
        </q-expansion-item>
        <q-separator></q-separator>
        <q-expansion-item
          group="extras"
          icon="qr_code"
          v-if="stored_paylinks.length > 0"
          :label="$t('stored_paylinks')"
        >
          <q-card>
            <q-card-section>
              <div class="row flex" v-for="paylink in stored_paylinks">
                <q-btn
                  dense
                  flat
                  color="primary"
                  icon="send"
                  size="xs"
                  @click="sendToPaylink(paylink.lnurl)"
                >
                  <q-tooltip>
                    <span v-text="`send to: ${paylink.lnurl}`"></span>
                  </q-tooltip>
                </q-btn>
                <q-btn
                  dense
                  flat
                  color="secondary"
                  icon="content_copy"
                  size="xs"
                  @click="copyText(paylink.lnurl)"
                >
                  <q-tooltip>
                    <span v-text="`copy: ${paylink.lnurl}`"></span>
                  </q-tooltip>
                </q-btn>
                <span v-text="paylink.label" class="q-mr-xs q-ml-xs"></span>
                <q-btn dense flat color="primary" icon="edit" size="xs">
                  <q-popup-edit
                    @update:model-value="editPaylink()"
                    v-model="paylink.label"
                    v-slot="scope"
                  >
                    <q-input
                      dark
                      color="white"
                      v-model="scope.value"
                      dense
                      autofocus
                      counter
                      @keyup.enter="scope.set"
                    >
                      <template v-slot:append>
                        <q-icon name="edit" />
                      </template>
                    </q-input>
                  </q-popup-edit>
                  <q-tooltip>
                    <span v-text="$t('edit')"></span>
                  </q-tooltip>
                </q-btn>
                <span style="flex-grow: 1"></span>
                <q-btn
                  dense
                  flat
                  color="red"
                  icon="delete"
                  size="xs"
                  @click="deletePaylink(paylink.lnurl)"
                >
                  <q-tooltip>
                    <span v-text="$t('delete')"></span>
                  </q-tooltip>
                </q-btn>
                <span v-text="dateFromNow(paylink.last_used)"></span>
              </div>
            </q-card-section>
          </q-card>
        </q-expansion-item>
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
                  <q-input
                    filled
                    v-model.trim="updateWallet.name"
                    label="Name"
                    dense
                  />
                </div>
                <div class="col-4 q-pl-sm">
                  <q-btn
                    :disable="!updateWallet.name.length"
                    unelevated
                    class="q-mt-xs full-width"
                    color="primary"
                    :label="$t('update_name')"
                    dense
                    @click="updateWallet({name: updateWallet.name})"
                  ></q-btn>
                </div>
                <div class="col-2"></div>
              </div>
            </q-card-section>
            <q-card-section v-if="isSatsDenomination">
              <div class="row">
                <div class="col-6">
                  <q-select
                    filled
                    dense
                    v-model="updateWallet.currency"
                    type="text"
                    :disable="g.fiatTracking"
                    :options="g.currencies.filter(u => u !== 'sat')"
                    :label="$t('currency_settings')"
                  ></q-select>
                </div>
                <div class="col-4 q-pl-sm">
                  <q-btn
                    dense
                    color="primary"
                    class="q-mt-xs full-width"
                    @click="handleFiatTracking()"
                    :disable="updateWallet.currency == ''"
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
                    @click="saveChartsPreferences"
                    v-model="chartConfig.showBalance"
                    :label="$t('payments_balance_chart')"
                  >
                  </q-checkbox>
                </div>

                <div class="col-md-4 col-sm-12">
                  <q-checkbox
                    dense
                    @click="saveChartsPreferences"
                    v-model="chartConfig.showBalanceInOut"
                    :label="$t('payments_balance_in_out_chart')"
                  >
                  </q-checkbox>
                </div>
                <div class="col-md-4 col-sm-12">
                  <q-checkbox
                    dense
                    @click="saveChartsPreferences"
                    v-model="chartConfig.showPaymentCountInOut"
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
  <q-dialog v-model="icon.show" position="top">
    <q-card class="q-pa-lg q-pt-xl lnbits__dialog-card">
      <q-form @submit="setIcon" class="q-gutter-md">
        <div class="q-gutter-sm q-pa-sm flex flex-wrap justify-center">
          <!-- Loop through all icons -->
          <q-btn
            v-for="(thisIcon, index) in icon.options"
            :key="index"
            @click="setSelectedIcon(thisIcon)"
            round
            text-color="black"
            :color="
              icon.data.icon === thisIcon
                ? icon.data.color || 'primary'
                : 'grey-5'
            "
            size="md"
            :icon="thisIcon"
            class="q-mb-sm"
          ></q-btn>
        </div>
        <div class="q-pa-sm flex justify-between items-center">
          <div class="flex q-pl-lg">
            <!-- Color options -->
            <q-btn
              v-for="(color, index) in icon.colorOptions"
              :key="'color-' + index"
              @click="setSelectedColor(color)"
              round
              :color="color"
              size="xs"
              style="width: 24px; height: 24px; min-width: 24px; padding: 0"
              class="q-mr-xs"
            ></q-btn>
          </div>
          <q-btn
            unelevated
            color="primary"
            :disable="!icon.data.icon"
            type="submit"
          >
            Save Icon
          </q-btn>
        </div>
      </q-form>
    </q-card>
  </q-dialog>

  <q-card v-if="adsEnabled">
    <q-card-section>
      <h6 v-text="AD_SPACE_TITLE" class="text-subtitle1 q-mt-none q-mb-sm"></h6>
    </q-card-section>
    <q-card-section v-for="ad in ads" class="q-pa-none">
      <a
        style="display: inline-block"
        :href="ad[0]"
        class="q-ml-md q-mb-xs q-mr-md"
      >
        <img
          v-if="$q.dark.isActive"
          style="max-width: 100%; height: auto"
          :src="ad[1]"
        />
        <img v-else style="max-width: 100%; height: auto" :src="ad[2]" />
      </a>
    </q-card-section>
  </q-card>

  <div v-show="chartDataPointCount" class="col-12 col-md-5 q-gutter-y-md">
    <q-card v-if="chartConfig.showBalance">
      <q-card-section class="q-pa-none">
        <div style="height: 200px" class="q-pa-sm">
          <canvas ref="walletBalanceChart"></canvas>
        </div>
      </q-card-section>
    </q-card>
    <q-card v-if="chartConfig.showBalanceInOut">
      <q-card-section class="q-pa-none">
        <div style="height: 200px" class="q-pa-sm">
          <canvas ref="walletBalanceInOut"></canvas>
        </div>
      </q-card-section>
    </q-card>
    <q-card v-if="chartConfig.showPaymentCountInOut">
      <q-card-section class="q-pa-none">
        <div style="height: 200px" class="q-pa-sm">
          <canvas ref="walletPaymentsInOut"></canvas>
        </div>
      </q-card-section>
    </q-card>
  </div>
  <div v-if="hasChartActive && !chartDataPointCount">
    <q-card>
      <q-card-section> No chart data available</q-card-section>
    </q-card>
  </div>
</template>
