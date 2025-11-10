<template id="lnbits-wallet-not-receive">
  <q-form @submit="createInvoice" class="q-gutter-md">
    <p v-if="receive.lnurl" class="text-h6 text-center q-my-none">
      <b v-text="receive.lnurl.domain"></b> is requesting an invoice:
    </p>
    <q-input
      v-if="isSatsDenomination"
      filled
      dense
      v-model="receive.data.amount"
      :label="$t('amount') + '(' + LNBITS_DENOMINATION + ') *'"
      mask="#.##"
      fill-mask="0"
      reverse-fill-mask
      :min="receive.minMax[0]"
      :max="receive.minMax[1]"
      :readonly="receive.lnurl && receive.lnurl.fixed"
    ></q-input>
    <div v-else class="row">
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
          @click="swapBalancePriority"
          class="float-right"
          color="primary"
          flat
          dense
          icon="swap_vert"
        ></q-btn>
      </div>
      <q-input
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
        val => !val || val.length <= 512 || 'Please use maximum 512 characters'
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
</template>
