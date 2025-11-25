<template id="page-wallet">
  <div class="row q-col-gutter-md" style="margin-bottom: 6rem">
    <div class="col-12 col-md-7 q-gutter-y-md wallet-wrapper">
      <q-card class="wallet-card">
        <q-card-section>
          <div class="row q-gutter-sm">
            <div v-if="g.fiatTracking" class="col-auto">
              <q-btn
                @click="g.isFiatPriority = !g.isFiatPriority"
                style="height: 50px"
                class="q-mt-lg"
                color="primary"
                flat
                dense
                icon="swap_vert"
              ></q-btn>
            </div>
            <div class="col">
              <div
                v-if="!g.isFiatPriority || !g.fiatTracking"
                class="column"
                :class="{
                  'q-pt-sm': g.fiatTracking,
                  'q-pt-lg': !g.fiatTracking
                }"
                style="height: 100px"
              >
                <div class="col-7">
                  <div class="row">
                    <div class="col-auto">
                      <div class="text-h3 q-my-none full-width">
                        <strong
                          v-text="
                            utils.formatBalance(g.wallet.sat, g.denomination)
                          "
                          class="text-no-wrap"
                          :style="{
                            fontSize: 'clamp(0.75rem, 10vw, 3rem)',
                            display: 'inline-block',
                            maxWidth: '100%'
                          }"
                        ></strong>
                      </div>
                    </div>
                    <div class="col-auto">
                      <lnbits-update-balance
                        v-if="$q.screen.lt.lg"
                        :wallet_id="g.wallet.id"
                        :callback="updateBalanceCallback"
                        :small_btn="true"
                      ></lnbits-update-balance>
                    </div>
                  </div>
                </div>
                <div class="col-2">
                  <div v-if="g.fiatTracking">
                    <span
                      class="text-h5 text-italic"
                      v-text="formattedFiatAmount"
                      style="opacity: 0.75"
                    ></span>
                  </div>
                </div>
              </div>

              <div
                class="column"
                v-if="g.isFiatPriority && g.fiatTracking"
                :class="{
                  'q-pt-sm': g.fiatTracking,
                  'q-pt-lg': !g.fiatTracking
                }"
                style="height: 100px"
              >
                <div class="col-7">
                  <div class="row">
                    <div class="col-auto">
                      <div
                        v-if="g.fiatTracking"
                        class="text-h3 q-my-none text-no-wrap"
                      >
                        <strong v-text="formattedFiatAmount"></strong>
                      </div>
                    </div>
                    <div class="col-auto">
                      <lnbits-update-balance
                        v-if="$q.screen.lt.lg"
                        :wallet_id="g.wallet.id"
                        :callback="updateBalanceCallback"
                        :small_btn="true"
                      ></lnbits-update-balance>
                    </div>
                  </div>
                </div>
                <div class="col-2">
                  <span
                    class="text-h5 text-italic"
                    style="opacity: 0.75"
                    v-text="
                      utils.formatBalance(
                        g.wallet.sat,
                        g.denomination,
                        g.denomination
                      )
                    "
                  >
                  </span>
                </div>
              </div>

              <div
                class="absolute-right q-pa-md"
                v-if="$q.screen.gt.md && g.fiatTracking && g.isSatsDenomination"
              >
                <div class="text-bold text-italic">BTC Price</div>
                <span
                  class="text-bold text-italic"
                  v-text="formattedExchange"
                ></span>
              </div>
              <q-btn
                v-if="$q.screen.lt.md"
                @click="g.mobileSimple = !g.mobileSimple"
                color="primary"
                class="q-ml-xl absolute-right"
                dense
                size="sm"
                style="height: 20px; margin-top: 75px"
                flat
                :icon="g.mobileSimple ? 'unfold_more' : 'unfold_less'"
                :label="g.mobileSimple ? $t('more') : $t('less')"
              ></q-btn>
            </div>
          </div>
          <div
            v-if="!$q.screen.lt.md"
            class="lnbits-wallet-buttons row q-gutter-md"
          >
            <div class="col">
              <q-btn
                unelevated
                color="primary"
                class="q-mr-md"
                @click="showReceiveDialog"
                :label="$t('receive')"
                :disable="!this.g.wallet.canReceivePayments"
                icon="file_download"
              ></q-btn>
              <q-btn
                unelevated
                color="primary"
                class="q-mr-md"
                @click="showParseDialog"
                :disable="!this.g.wallet.canSendPayments"
                :label="$t('send')"
                icon="file_upload"
              ></q-btn>
              <q-btn
                unelevated
                color="secondary"
                icon="qr_code_scanner"
                :disable="
                  !this.g.wallet.canReceivePayments &&
                  !this.g.wallet.canSendPayments
                "
                @click="showCamera"
              >
                <q-tooltip
                  ><span v-text="$t('camera_tooltip')"></span
                ></q-tooltip>
              </q-btn>
              <lnbits-update-balance
                v-if="$q.screen.gt.md"
                :wallet_id="this.g.wallet.id"
                :callback="updateBalanceCallback"
                :small_btn="false"
              ></lnbits-update-balance>
            </div>
          </div>
        </q-card-section>
      </q-card>
      <q-card class="wallet-card">
        <q-card-section>
          <lnbits-payment-list
            :wallet="g.wallet"
            :payment-filter="paymentFilter"
          ></lnbits-payment-list>
        </q-card-section>
      </q-card>
    </div>
    <div
      v-if="!g.mobileSimple || !$q.screen.lt.md"
      class="col-12 col-md-5 q-gutter-y-md"
    >
      <lnbits-wallet-extra
        @update-wallet="updateWallet"
        @send-lnurl="handleSendLnurl"
        :chart-config="chartConfig"
      ></lnbits-wallet-extra>
      <q-card class="lnbits-wallet-ads" v-if="AD_SPACE_ENABLED">
        <q-card-section class="text-subtitle1">
          <span v-text="AD_SPACE_TITLE"></span>
          <a :href="ad[0]" class="lnbits-ad" v-for="ad in g.ads">
            <q-img class="q-mb-xs" v-if="$q.dark.isActive" :src="ad[1]"></q-img>
            <q-img class="q-mb-xs" v-else :src="ad[2]"></q-img>
          </a>
        </q-card-section>
      </q-card>
      <lnbits-wallet-charts
        :payment-filter="paymentFilter"
        :chart-config="chartConfig"
      ></lnbits-wallet-charts>
    </div>
  </div>

  <q-dialog v-model="receive.show" position="top" @hide="onReceiveDialogHide">
    <q-card
      v-if="!receive.paymentReq"
      class="q-pa-lg q-pt-xl lnbits__dialog-card"
    >
      <q-form @submit="createInvoice" class="q-gutter-md">
        <p v-if="receive.lnurl" class="text-h6 text-center q-my-none">
          <b v-text="receive.lnurl.domain"></b> is requesting an invoice:
        </p>
        <q-input
          v-if="!g.isSatsDenomination"
          filled
          dense
          v-model="receive.data.amount"
          :label="$t('amount') + '(' + denomination + ') *'"
          mask="#.##"
          fill-mask="0"
          reverse-fill-mask
          :min="receive.minMax[0]"
          :max="receive.minMax[1]"
          :readonly="receive.lnurl && receive.lnurl.fixed"
        ></q-input>
        <div v-else>
          <div class="row">
            <div class="col-10">
              <q-select
                filled
                dense
                v-model="receive.unit"
                type="text"
                :label="$t('unit')"
                :options="receive.units"
              ></q-select>
            </div>
            <div class="col-2">
              <q-btn
                v-if="g.fiatTracking"
                @click="g.isFiatPriority = !g.isFiatPriority"
                class="float-right"
                color="primary"
                flat
                dense
                icon="swap_vert"
              ></q-btn>
            </div>
          </div>
          <q-input
            class="q-mt-md"
            ref="setAmount"
            filled
            :pattern="receive.unit === 'sat' ? '\\d*' : '\\d*\\.?\\d*'"
            inputmode="numeric"
            dense
            v-model.number="receive.data.amount"
            :label="$t('amount') + ' (' + receive.unit + ') *'"
            :min="receive.minMax[0]"
            :max="receive.minMax[1]"
            :readonly="receive.lnurl && receive.lnurl.fixed"
          ></q-input>
        </div>
        <q-input
          v-if="has_holdinvoice"
          filled
          dense
          v-model="receive.data.payment_hash"
          :label="$t('hold_invoice_payment_hash')"
        ></q-input>
        <q-input
          filled
          dense
          type="textarea"
          rows="2"
          v-model="receive.data.memo"
          :label="$t('memo')"
        >
          <template v-if="receive.data.internalMemo === null" v-slot:append>
            <q-icon
              name="add_comment"
              @click.stop.prevent="receive.data.internalMemo = ''"
              class="cursor-pointer"
            ></q-icon>
            <q-tooltip>
              <span v-text="$t('internal_memo')"></span>
            </q-tooltip>
          </template>
        </q-input>
        <q-input
          v-if="receive.data.internalMemo !== null"
          autogrow
          filled
          dense
          v-model="receive.data.internalMemo"
          class="q-mb-lg"
          :label="$t('internal_memo')"
          :hint="$t('internal_memo_hint_receive')"
          :rules="[
            val =>
              !val || val.length <= 512 || 'Please use maximum 512 characters'
          ]"
          ><template v-slot:append>
            <q-icon
              name="cancel"
              @click.stop.prevent="receive.data.internalMemo = null"
              class="cursor-pointer"
            /> </template
        ></q-input>
        <div v-if="g.user.fiat_providers?.length" class="q-mt-md">
          <q-list bordered dense class="rounded-borders">
            <q-item-label dense header>
              <span v-text="$t('select_payment_provider')"></span>
            </q-item-label>
            <q-separator></q-separator>
            <q-item
              :active="!receive.fiatProvider"
              @click="receive.fiatProvider = ''"
              active-class="bg-teal-1 text-grey-8 text-weight-bold"
              clickable
              v-ripple
            >
              <q-item-section avatar>
                <q-avatar square>
                  <img src="/static/images/logos/lnbits.png" />
                </q-avatar>
              </q-item-section>
              <q-item-section>
                <span
                  v-text="$t('pay_with', {provider: 'Lightning Network'})"
                ></span>
              </q-item-section>
            </q-item>
            <q-separator></q-separator>
            <q-item
              :active="receive.fiatProvider === 'stripe'"
              @click="receive.fiatProvider = 'stripe'"
              active-class="bg-teal-1 text-grey-8 text-weight-bold"
              clickable
              v-ripple
            >
              <q-item-section avatar>
                <q-avatar>
                  <img src="/static/images/stripe_logo.ico" />
                </q-avatar>
              </q-item-section>
              <q-item-section>
                <span v-text="$t('pay_with', {provider: 'Stripe'})"></span>
              </q-item-section>
            </q-item>
          </q-list>
        </div>

        <div v-if="receive.status == 'pending'" class="row q-mt-lg">
          <q-btn
            unelevated
            color="primary"
            :disable="receive.data.amount == null || receive.data.amount <= 0"
            type="submit"
          >
            <span
              v-if="receive.lnurl"
              v-text="`${$t('withdraw_from')} ${receive.lnurl.domain}`"
            ></span>
            <span v-else v-text="$t('create_invoice')"></span>
          </q-btn>
          <q-btn
            v-close-popup
            flat
            color="grey"
            class="q-ml-auto"
            :label="$t('cancel')"
          ></q-btn>
        </div>
        <q-spinner-bars
          v-if="receive.status == 'loading'"
          color="primary"
          size="2.55em"
        ></q-spinner-bars>
      </q-form>
    </q-card>
    <q-card
      v-else-if="receive.paymentReq && receive.lnurl == null"
      class="q-pa-lg q-pt-xl lnbits__dialog-card"
    >
      <lnbits-qrcode
        v-if="receive.fiatPaymentReq"
        :show-buttons="false"
        :href="receive.fiatPaymentReq"
        :value="receive.fiatPaymentReq"
      >
      </lnbits-qrcode>
      <lnbits-qrcode
        v-else
        :href="'lightning:' + receive.paymentReq"
        :value="'lightning:' + receive.paymentReq"
      >
      </lnbits-qrcode>
      <div class="text-center">
        <h3 class="q-my-md">
          <span v-text="formattedAmount"></span>
        </h3>
        <h5 v-if="receive.unit != 'sat'" class="q-mt-none q-mb-sm">
          <span v-text="formattedSatAmount"></span>
        </h5>
        <div v-if="!receive.fiatPaymentReq">
          <q-chip v-if="hasNfc" outline square color="positive">
            <q-avatar icon="nfc" color="positive" text-color="white"></q-avatar>
            <span v-text="$t('nfc_supported')"></span>
          </q-chip>
        </div>
      </div>
      <div class="row q-mt-lg">
        <q-btn
          v-close-popup
          flat
          color="grey"
          class="q-ml-auto"
          :label="$t('close')"
        ></q-btn>
      </div>
    </q-card>
  </q-dialog>

  <q-dialog v-model="parse.show" @hide="closeParseDialog" position="top">
    <q-card class="q-pa-lg q-pt-xl lnbits__dialog-card">
      <div v-if="parse.invoice">
        <div class="column content-center text-center q-mb-md">
          <div v-if="!g.isFiatPriority">
            <h4 class="q-my-none text-bold">
              <span
                v-text="utils.formatBalance(parse.invoice.sat, g.denomination)"
              ></span>
            </h4>
          </div>
          <div v-else>
            <h4
              class="q-my-none text-bold"
              v-text="parse.invoice.fiatAmount"
            ></h4>
          </div>
          <div class="q-my-md absolute">
            <q-btn
              v-if="g.fiatTracking"
              @click="g.isFiatPriority = !g.isFiatPriority"
              flat
              dense
              icon="swap_vert"
              color="primary"
            ></q-btn>
          </div>
          <div v-if="g.fiatTracking">
            <div v-if="g.isFiatPriority">
              <h5 class="q-my-none text-bold">
                <span
                  v-text="
                    utils.formatBalance(parse.invoice.sat, g.denomination)
                  "
                ></span>
              </h5>
            </div>
            <div v-else style="opacity: 0.75">
              <div class="text-h5 text-italic">
                <span
                  v-text="parse.invoice.fiatAmount"
                  style="opacity: 0.75"
                ></span>
              </div>
            </div>
          </div>
        </div>
        <q-separator></q-separator>
        <h6 class="text-center" v-text="parse.invoice.description"></h6>
        <q-input
          autogrow
          filled
          dense
          v-model="parse.data.internalMemo"
          :label="$t('internal_memo')"
          :hint="$t('internal_memo_hint_pay')"
          class="q-mb-lg"
          :rules="[
            val =>
              !val || val.length <= 512 || 'Please use maximum 512 characters'
          ]"
          ><template v-if="parse.data.internalMemo" v-slot:append>
            <q-icon
              name="cancel"
              @click.stop.prevent="parse.data.internalMemo = null"
              class="cursor-pointer" /></template
        ></q-input>
        <q-list separator bordered dense class="q-mb-md">
          <q-expansion-item expand-separator icon="info" label="Details">
            <q-list separator>
              <q-item>
                <q-item-section>
                  <q-item-label v-text="$t('created')"></q-item-label>
                  <q-item-label
                    caption
                    v-text="parse.invoice.createdDate"
                  ></q-item-label>
                </q-item-section>

                <q-item-section side top>
                  <q-item-label
                    caption
                    v-text="parse.invoice.createdDateFrom"
                  ></q-item-label>
                </q-item-section>
              </q-item>
              <q-item>
                <q-item-section>
                  <q-item-label v-text="$t('expire_date')"></q-item-label>
                  <q-item-label
                    caption
                    v-text="parse.invoice.expireDate"
                  ></q-item-label>
                </q-item-section>
                <q-item-section side top>
                  <q-item-label
                    caption
                    v-text="parse.invoice.expireDateFrom"
                  ></q-item-label>
                </q-item-section>
              </q-item>
              <q-item>
                <q-item-section>
                  <q-item-label v-text="$t('payment_hash')"></q-item-label>
                  <q-item-label
                    caption
                    v-text="
                      `${parse.invoice.hash.slice(0, 12)}...${parse.invoice.hash.slice(-12)}`
                    "
                  ></q-item-label>
                </q-item-section>
                <q-item-section side>
                  <q-item-label>
                    <q-icon
                      name="content_copy"
                      @click="utils.copyText(parse.invoice.hash)"
                      size="1em"
                      color="grey"
                      class="cursor-pointer"
                    />
                  </q-item-label>
                  <q-tooltip>
                    <span v-text="parse.invoice.hash"></span>
                  </q-tooltip>
                </q-item-section>
              </q-item>
              <q-item>
                <q-item-section>
                  <q-item-label v-text="$t('Invoice')"></q-item-label>
                  <q-item-label
                    caption
                    v-text="
                      `${parse.invoice.bolt11.slice(0, 12)}...${parse.invoice.bolt11.slice(-12)}`
                    "
                  ></q-item-label>
                </q-item-section>
                <q-item-section side>
                  <q-item-label>
                    <q-icon
                      name="content_copy"
                      @click="utils.copyText(parse.invoice.bolt11)"
                      size="1em"
                      color="grey"
                      class="cursor-pointer"
                    />
                  </q-item-label>
                  <q-tooltip>
                    <span v-text="parse.invoice.bolt11"></span>
                  </q-tooltip>
                </q-item-section>
              </q-item>
            </q-list>
          </q-expansion-item>
        </q-list>
        <div v-if="canPay" class="row q-mt-lg">
          <q-btn
            unelevated
            color="primary"
            @click="payInvoice"
            :label="$t('pay')"
          ></q-btn>
          <q-btn
            v-close-popup
            flat
            color="grey"
            class="q-ml-auto"
            :label="$t('cancel')"
          ></q-btn>
        </div>
        <div v-else class="row q-mt-lg">
          <q-btn
            :label="$t('not_enough_funds')"
            unelevated
            disabled
            color="yellow"
            text-color="black"
          ></q-btn>
          <q-btn
            v-close-popup
            flat
            color="grey"
            class="q-ml-auto"
            :label="$t('cancel')"
          ></q-btn>
        </div>
      </div>
      <div v-else-if="parse.lnurlauth">
        <q-form @submit="authLnurl" class="q-gutter-md">
          <p class="q-my-none text-h6">
            Authenticate with <b v-text="parse.lnurlauth.domain"></b>?
          </p>
          <q-separator class="q-my-sm"></q-separator>
          <p>
            For every website and for every LNbits wallet, a new keypair will be
            deterministically generated so your identity can't be tied to your
            LNbits wallet or linked across websites. No other data will be
            shared with
            <span v-text="parse.lnurlauth.domain"></span>.
          </p>
          <p>Your public key for <b v-text="parse.lnurlauth.domain"></b> is:</p>
          <p class="q-mx-xl">
            <code class="text-wrap" v-text="parse.lnurlauth.pubkey"></code>
          </p>
          <div class="row q-mt-lg">
            <q-btn
              unelevated
              color="primary"
              type="submit"
              :label="$t('login')"
            ></q-btn>
            <q-btn
              :label="$t('cancel')"
              v-close-popup
              flat
              color="grey"
              class="q-ml-auto"
            ></q-btn>
          </div>
        </q-form>
      </div>
      <div v-else-if="parse.lnurlpay">
        <q-form @submit="payLnurl" class="q-gutter-md">
          <p v-if="parse.lnurlpay.fixed" class="q-my-none text-h6">
            <b v-text="parse.lnurlpay.domain"></b> is requesting
            <span v-text="msatoshiFormat(parse.lnurlpay.maxSendable)"></span>
            <span v-text="denomination"></span>
            <span v-if="parse.lnurlpay.commentAllowed > 0">
              <br />
              and a
              <span v-text="parse.lnurlpay.commentAllowed"></span>-char comment
            </span>
          </p>
          <p v-else class="q-my-none text-h6 text-center">
            <b v-text="parse.lnurlpay.targetUser || parse.lnurlpay.domain"></b>
            is requesting <br />
            between
            <b v-text="msatoshiFormat(parse.lnurlpay.minSendable)"></b> and
            <b v-text="msatoshiFormat(parse.lnurlpay.maxSendable)"></b>
            <span v-text="denomination"></span>
            <span v-if="parse.lnurlpay.commentAllowed > 0">
              <br />
              and a
              <span v-text="parse.lnurlpay.commentAllowed"></span>-char comment
            </span>
          </p>
          <q-separator class="q-my-sm"></q-separator>
          <div class="row">
            <p
              class="col text-justify text-italic"
              v-text="parse.lnurlpay.description"
            ></p>
            <p class="col-4 q-pl-md" v-if="parse.lnurlpay.image">
              <q-img :src="parse.lnurlpay.image" />
            </p>
          </div>
          <div class="row">
            <div class="col q-mb-lg">
              <q-select
                filled
                dense
                v-if="!parse.lnurlpay.fixed"
                v-model="parse.data.unit"
                type="text"
                :label="$t('unit')"
                :options="receive.units"
              ></q-select>
              <br />
              <q-input
                ref="setAmount"
                filled
                dense
                v-model.number="parse.data.amount"
                :label="$t('amount') + ' (' + parse.data.unit + ') *'"
                :mask="parse.data.unit == 'sat' ? '#' : ''"
                :step="parse.data.unit == 'sat' ? '1' : '0.01'"
                fill-mask="0"
                reverse-fill-mask
                :min="parse.lnurlpay.minSendable / 1000"
                :max="parse.lnurlpay.maxSendable / 1000"
                :readonly="parse.lnurlpay && parse.lnurlpay.fixed"
              ></q-input>
            </div>
            <div class="col-8 q-pl-md" v-if="parse.lnurlpay.commentAllowed > 0">
              <q-input
                filled
                dense
                v-model="parse.data.comment"
                :type="
                  parse.lnurlpay.commentAllowed > 512 ? 'textarea' : 'text'
                "
                label="Comment (optional)"
                :maxlength="parse.lnurlpay.commentAllowed"
                ><template
                  v-if="parse.data.internalMemo === null"
                  v-slot:append
                >
                  <q-icon
                    name="add_comment"
                    @click.stop.prevent="parse.data.internalMemo = ''"
                    class="cursor-pointer"
                  ></q-icon>
                  <q-tooltip>
                    <span v-text="$t('internal_memo')"></span>
                  </q-tooltip> </template
              ></q-input>
              <br />
              <q-input
                v-if="parse.data.internalMemo !== null"
                autogrow
                filled
                dense
                v-model="parse.data.internalMemo"
                :label="$t('internal_memo')"
                :hint="$t('internal_memo_hint_pay')"
                class=""
                :rules="[
                  val =>
                    !val ||
                    val.length <= 512 ||
                    'Please use maximum 512 characters'
                ]"
                ><template v-slot:append>
                  <q-icon
                    name="cancel"
                    @click.stop.prevent="parse.data.internalMemo = null"
                    class="cursor-pointer"
                  /> </template
              ></q-input>
            </div>
          </div>
          <div class="row q-mt-lg">
            <q-btn unelevated color="primary" type="submit">Send</q-btn>
            <q-btn
              :label="$t('cancel')"
              v-close-popup
              flat
              color="grey"
              class="q-ml-auto"
            ></q-btn>
          </div>
        </q-form>
      </div>
      <div v-else>
        <q-form
          v-if="!parse.camera.show"
          @submit="decodeRequest"
          class="q-gutter-md"
        >
          <q-input
            filled
            dense
            v-model.trim="parse.data.request"
            type="textarea"
            :label="$t('paste_invoice_label')"
            ref="textArea"
          >
          </q-input>
          <div class="row q-mt-lg">
            <q-btn
              unelevated
              color="primary"
              :disable="parse.data.request == ''"
              type="submit"
              :label="$t('read')"
            ></q-btn>
            <q-icon
              name="content_paste"
              color="grey"
              class="q-mt-xs q-ml-sm q-mr-auto"
              v-if="parse.copy.show"
              @click="pasteToTextArea"
            >
              <q-tooltip>
                <span v-text="$t('paste_from_clipboard')"></span>
              </q-tooltip>
            </q-icon>
            <q-btn
              v-close-popup
              flat
              color="grey"
              class="q-ml-auto"
              :label="$t('cancel')"
            ></q-btn>
          </div>
        </q-form>
        <div v-else>
          <q-responsive :ratio="1">
            <qrcode-stream
              @detect="decodeQR"
              @camera-on="onInitQR"
              class="rounded-borders"
            ></qrcode-stream>
          </q-responsive>
          <div class="row q-mt-lg">
            <q-btn
              :label="$t('cancel')"
              @click="closeCamera"
              flat
              color="grey"
              class="q-ml-auto"
            >
            </q-btn>
          </div>
        </div>
      </div>
    </q-card>
  </q-dialog>

  <q-dialog v-model="parse.camera.show" position="top">
    <q-card class="q-pa-lg q-pt-xl">
      <div class="text-center q-mb-lg">
        <qrcode-stream
          @detect="decodeQR"
          @camera-on="onInitQR"
          class="rounded-borders"
        ></qrcode-stream>
      </div>
      <div class="row q-mt-lg">
        <q-btn
          @click="closeCamera"
          flat
          color="grey"
          class="q-ml-auto"
          :label="$t('cancel')"
        ></q-btn>
      </div>
    </q-card>
  </q-dialog>

  <div
    class="lt-md fixed-bottom left-0 right-0 bg-primary text-white shadow-2 z-top"
  >
    <q-tabs active-class="px-0" indicator-color="transparent" align="justify">
      <q-tab
        icon="file_download"
        @click="showReceiveDialog"
        :label="$t('receive')"
      >
      </q-tab>

      <q-tab @click="showParseDialog" icon="file_upload" :label="$t('send')">
      </q-tab>
    </q-tabs>
    <q-btn
      round
      size="35px"
      unelevated
      icon="qr_code_scanner"
      @click="showCamera"
      class="text-white bg-primary z-top vertical-bottom absolute-center absolute"
    >
    </q-btn>
  </div>
</template>
