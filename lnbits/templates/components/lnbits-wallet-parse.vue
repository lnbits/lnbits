<template id="lnbits-wallet-parse">
  <div v-if="parse.invoice">
    <div class="column content-center text-center q-mb-md">
      <div v-if="!isFiatPriority">
        <h4 class="q-my-none text-bold">
          <span v-text="formatBalance(parse.invoice.sat)"></span>
        </h4>
      </div>
      <div v-else>
        <h4 class="q-my-none text-bold" v-text="parse.invoice.fiatAmount"></h4>
      </div>
      <div class="q-my-md absolute">
        <q-btn
          v-if="g.fiatTracking"
          @click="swapBalancePriority"
          flat
          dense
          icon="swap_vert"
          color="primary"
        ></q-btn>
      </div>
      <div v-if="g.fiatTracking">
        <div v-if="isFiatPriority">
          <h5 class="q-my-none text-bold">
            <span v-text="formatBalance(parse.invoice.sat)"></span>
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
        val => !val || val.length <= 512 || 'Please use maximum 512 characters'
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
                  @click="copyText(parse.invoice.hash)"
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
                  @click="copyText(parse.invoice.bolt11)"
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
        LNbits wallet or linked across websites. No other data will be shared
        with
        <span v-text="parse.lnurlauth.domain"></span>.
      </p>
      <p>
        Your public key for
        <b v-text="parse.lnurlauth.domain"></b> is:
      </p>
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
        <span v-text="LNBITS_DENOMINATION"></span>
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
        <b v-text="msatoshiFormat(parse.lnurlpay.minSendable)"></b>
        and
        <b v-text="msatoshiFormat(parse.lnurlpay.maxSendable)"></b>
        <span v-text="LNBITS_DENOMINATION"></span>
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
            :type="parse.lnurlpay.commentAllowed > 512 ? 'textarea' : 'text'"
            label="Comment (optional)"
            :maxlength="parse.lnurlpay.commentAllowed"
            ><template v-if="parse.data.internalMemo === null" v-slot:append>
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
                !val || val.length <= 512 || 'Please use maximum 512 characters'
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
</template>
