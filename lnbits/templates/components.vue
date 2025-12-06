{% include('components/admin/funding.vue') %} {%
include('components/admin/funding_sources.vue') %} {%
include('components/admin/fiat_providers.vue') %} {%
include('components/admin/exchange_providers.vue') %} {%
include('components/admin/security.vue') %} {%
include('components/admin/users.vue') %} {%
include('components/admin/site_customisation.vue') %} {%
include('components/admin/audit.vue') %} {%
include('components/admin/extensions.vue') %} {%
include('components/admin/assets-config.vue') %} {%
include('components/admin/notifications.vue') %} {%
include('components/admin/server.vue') %} {%
include('components/lnbits-qrcode.vue') %} {%
include('components/lnbits-qrcode-scanner.vue') %} {%
include('components/lnbits-disclaimer.vue') %} {%
include('components/lnbits-footer.vue') %} {%
include('components/lnbits-header.vue') %} {%
include('components/lnbits-header-wallets.vue') %} {%
include('components/lnbits-drawer.vue') %} {%
include('components/lnbits-home-logos.vue') %} {%
include('components/lnbits-manage-extension-list.vue') %} {%
include('components/lnbits-manage-wallet-list.vue') %} {%
include('components/lnbits-language-dropdown.vue') %} {%
include('components/lnbits-payment-list.vue') %} {%
include('components/lnbits-wallet-icon.vue') %} {%
include('components/lnbits-wallet-new.vue') %} {%
include('components/lnbits-label-selector.vue') %} {%
include('components/lnbits-wallet-api-docs.vue') %} {%
include('components/lnbits-wallet-share.vue') %} {%
include('components/lnbits-wallet-charts.vue') %} {%
include('components/lnbits-wallet-paylinks.vue') %} {%
include('components/lnbits-wallet-extra.vue') %} {%
include('components/lnbits-error.vue') %}

<template id="lnbits-manage">
  <q-list v-if="g.user" dense class="lnbits-drawer__q-list">
    <q-item-label header v-text="$t('manage')"></q-item-label>
    <div v-if="g.user.admin">
      <q-item v-if="showAdmin" to="/admin">
        <q-item-section side>
          <q-icon
            name="settings"
            :color="isActive('/admin') ? 'primary' : 'grey-5'"
            size="md"
          ></q-icon>
        </q-item-section>
        <q-item-section>
          <q-item-label lines="1" v-text="$t('settings')"></q-item-label>
        </q-item-section>
        <q-item-section side v-show="isActive('/admin')">
          <q-icon name="chevron_right" color="grey-5" size="md"></q-icon>
        </q-item-section>
      </q-item>
      <q-item v-if="showNode" to="/node">
        <q-item-section side>
          <q-icon
            name="developer_board"
            :color="isActive('/node') ? 'primary' : 'grey-5'"
            size="md"
          ></q-icon>
        </q-item-section>
        <q-item-section>
          <q-item-label lines="1" v-text="$t('node')"></q-item-label>
        </q-item-section>
        <q-item-section side v-show="isActive('/node')">
          <q-icon name="chevron_right" color="grey-5" size="md"></q-icon>
        </q-item-section>
      </q-item>
      <q-item v-if="showUsers" to="/users">
        <q-item-section side>
          <q-icon
            name="groups"
            :color="isActive('/users') ? 'primary' : 'grey-5'"
            size="md"
          ></q-icon>
        </q-item-section>
        <q-item-section>
          <q-item-label lines="1" v-text="$t('users')"></q-item-label>
        </q-item-section>
        <q-item-section side v-show="isActive('/users')">
          <q-icon name="chevron_right" color="grey-5" size="md"></q-icon>
        </q-item-section>
      </q-item>
      <q-item v-if="showAudit" to="/audit">
        <q-item-section side>
          <q-icon
            name="playlist_add_check_circle"
            :color="isActive('/audit') ? 'primary' : 'grey-5'"
            size="md"
          ></q-icon>
        </q-item-section>
        <q-item-section>
          <q-item-label lines="1" v-text="$t('api_watch')"></q-item-label>
        </q-item-section>
        <q-item-section side v-show="isActive('/audit')">
          <q-icon name="chevron_right" color="grey-5" size="md"></q-icon>
        </q-item-section>
      </q-item>
    </div>
    <q-item to="/payments">
      <q-item-section side>
        <q-icon
          name="query_stats"
          :color="isActive('/payments') ? 'primary' : 'grey-5'"
          size="md"
        ></q-icon>
      </q-item-section>
      <q-item-section>
        <q-item-label lines="1" v-text="$t('payments')"></q-item-label>
      </q-item-section>
      <q-item-section side v-show="isActive('/payments')">
        <q-icon name="chevron_right" color="grey-5" size="md"></q-icon>
      </q-item-section>
    </q-item>
    <q-item v-if="showExtensions" to="/extensions">
      <q-item-section side>
        <q-icon
          name="extension"
          :color="isActive('/extensions') ? 'primary' : 'grey-5'"
          size="md"
        ></q-icon>
      </q-item-section>
      <q-item-section>
        <q-item-label lines="1" v-text="$t('extensions')"></q-item-label>
      </q-item-section>
      <q-item-section side v-show="isActive('/extensions')">
        <q-icon name="chevron_right" color="grey-5" size="md"></q-icon>
      </q-item-section>
    </q-item>
  </q-list>
</template>

<template id="lnbits-payment-details">
  <q-list separator>
    <q-item v-if="payment.tag">
      <q-item-section>
        <q-item-label v-text="$t('created')"></q-item-label>
        <q-item-label caption v-text="payment.date"></q-item-label>
      </q-item-section>
      <q-item-section side top>
        <q-item-label caption v-text="payment.dateFrom"></q-item-label>
      </q-item-section>
    </q-item>
    <q-item v-if="payment.expirydate">
      <q-item-section>
        <q-item-label v-text="$t('expiry')"></q-item-label>
        <q-item-label caption v-text="payment.expirydate"></q-item-label>
      </q-item-section>

      <q-item-section side top>
        <q-item-label caption v-text="payment.expirydateFrom"></q-item-label>
      </q-item-section>
    </q-item>
    <q-item>
      <q-item-section>
        <q-item-label v-text="$t('amount')"></q-item-label>
        <q-item-label caption>
          <span v-text="(payment.amount / 1000).toFixed(3)"></span>
          <span v-text="g.denomination"></span>
        </q-item-label>
      </q-item-section>
    </q-item>
    <q-item>
      <q-item-section>
        <q-item-label v-text="$t('fee')"></q-item-label>
        <q-item-label caption>
          <span v-text="(payment.fee / 1000).toFixed(3)"></span>
          <span v-text="g.denomination"></span>
        </q-item-label>
      </q-item-section>
    </q-item>
    <q-item>
      <q-item-section>
        <q-item-label v-text="$t('payment_hash')"></q-item-label>
        <q-item-label
          caption
          v-text="
            `${payment.payment_hash.slice(0, 12)}...${payment.payment_hash.slice(-12)}`
          "
        ></q-item-label>
      </q-item-section>
      <q-item-section side>
        <q-item-label>
          <q-icon
            name="content_copy"
            @click="utils.copyText(payment.payment_hash)"
            size="1em"
            color="grey"
            class="cursor-pointer"
          />
        </q-item-label>
        <q-tooltip>
          <span v-text="payment.payment_hash"></span>
        </q-tooltip>
      </q-item-section>
    </q-item>
    <q-item>
      <q-item-section>
        <q-item-label v-text="$t('Invoice')"></q-item-label>
        <q-item-label
          caption
          v-text="
            `${payment.bolt11.slice(0, 12)}...${payment.bolt11.slice(-12)}`
          "
        ></q-item-label>
      </q-item-section>
      <q-item-section side>
        <q-item-label>
          <q-icon
            name="content_copy"
            @click="utils.copyText(payment.bolt11)"
            size="1em"
            color="grey"
            class="cursor-pointer"
          />
        </q-item-label>
        <q-tooltip>
          <span v-text="payment.bolt11"></span>
        </q-tooltip>
      </q-item-section>
    </q-item>
    <q-item>
      <q-item-section>
        <q-item-label v-text="$t('memo')"></q-item-label>
        <q-item-label caption v-text="payment.memo"></q-item-label>
      </q-item-section>
    </q-item>
    <q-item v-if="payment.webhook">
      <q-item-section>
        <q-item-label v-text="$t('webhook')"></q-item-label>
        <q-item-label caption v-text="payment.webhook"></q-item-label>
      </q-item-section>
      <q-item-section side top>
        <q-item-label caption>
          <q-badge
            :color="webhookStatusColor"
            text-color="white"
            v-text="webhookStatusText"
          ></q-badge>
        </q-item-label>
      </q-item-section>
    </q-item>
    <q-item v-if="payment.preimage">
      <q-item-section>
        <q-item-label v-text="$t('payment_proof')"></q-item-label>
        <q-item-label
          caption
          v-text="
            `${payment.preimage.slice(0, 12)}...${payment.preimage.slice(-12)}`
          "
        ></q-item-label>
      </q-item-section>
      <q-item-section side>
        <q-item-label>
          <q-icon
            name="content_copy"
            @click="utils.copyText(payment.preimage)"
            size="1em"
            color="grey"
            class="cursor-pointer"
          />
        </q-item-label>
        <q-tooltip>
          <span v-text="payment.preimage"></span>
        </q-tooltip>
      </q-item-section>
    </q-item>

    <q-expansion-item
      expand-separator
      icon="info"
      header-class="text-grey-4"
      label="Extras"
      v-if="extras.length"
    >
      <template v-for="entry in extras">
        <q-item
          v-if="!!entry.value"
          key="entry.key"
          class="text-grey-4"
          style="white-space: normal; word-break: break-all"
        >
          <q-item-section>
            <q-item-label v-text="entry.key"></q-item-label>
            <q-item-label caption v-text="entry.value"></q-item-label>
          </q-item-section>
        </q-item>
      </template>
    </q-expansion-item>
  </q-list>
</template>

<template id="lnbits-dynamic-fields">
  <div v-if="formData">
    <div class="row q-mb-lg" v-for="o in options">
      <div class="col auto-width">
        <p v-if="o.options?.length" class="q-ml-xl">
          <span v-text="o.label || o.name"></span>
          <small v-if="o.description">
            (<span v-text="o.description"></span>)</small
          >
        </p>
        <lnbits-dynamic-fields
          v-if="o.options?.length"
          :options="o.options"
          v-model="formData[o.name]"
          @update:model-value="handleValueChanged"
          class="q-ml-xl"
        >
        </lnbits-dynamic-fields>
        <div v-else>
          <q-input
            v-if="o.type === 'number'"
            type="number"
            v-model="formData[o.name]"
            @update:model-value="handleValueChanged"
            :label="o.label || o.name"
            :hint="o.description"
            :rules="applyRules(o.required)"
            filled
            dense
          ></q-input>
          <q-input
            v-else-if="o.type === 'text'"
            type="textarea"
            rows="5"
            v-model="formData[o.name]"
            @update:model-value="handleValueChanged"
            :label="o.label || o.name"
            :hint="o.description"
            :rules="applyRules(o.required)"
            filled
            dense
          ></q-input>
          <q-input
            v-else-if="o.type === 'password'"
            v-model="formData[o.name]"
            @update:model-value="handleValueChanged"
            type="password"
            :label="o.label || o.name"
            :hint="o.description"
            :rules="applyRules(o.required)"
            filled
            dense
          ></q-input>
          <q-select
            v-else-if="o.type === 'select'"
            v-model="formData[o.name]"
            @update:model-value="handleValueChanged"
            :label="o.label || o.name"
            :hint="o.description"
            :options="o.values"
            :rules="applyRules(o.required)"
          ></q-select>
          <q-select
            v-else-if="o.isList"
            v-model.trim="formData[o.name]"
            @update:model-value="handleValueChanged"
            input-debounce="0"
            new-value-mode="add-unique"
            :label="o.label || o.name"
            :hint="o.description"
            :rules="applyRules(o.required)"
            filled
            multiple
            dense
            use-input
            use-chips
            hide-dropdown-icon
          ></q-select>
          <div v-else-if="o.type === 'bool'">
            <q-item tag="label" v-ripple>
              <q-item-section avatar top>
                <q-checkbox
                  v-model="formData[o.name]"
                  @update:model-value="handleValueChanged"
                />
              </q-item-section>
              <q-item-section>
                <q-item-label
                  ><span v-text="o.label || o.name"></span
                ></q-item-label>
                <q-item-label caption>
                  <span v-text="o.description"></span>
                </q-item-label>
              </q-item-section>
            </q-item>
          </div>
          <q-input
            v-else-if="o.type === 'hidden'"
            v-model="formData[o.name]"
            type="text"
            style="display: none"
            :rules="applyRules(o.required)"
          ></q-input>
          <div v-else-if="o.type === 'chips'">
            <lnbits-dynamic-chips
              v-model="formData[o.name]"
              @update:model-value="handleValueChanged"
            ></lnbits-dynamic-chips>
          </div>
          <q-input
            v-else
            v-model="formData[o.name]"
            @update:model-value="handleValueChanged"
            :hint="o.description"
            :label="o.label || o.name"
            :rules="applyRules(o.required)"
            filled
            dense
          ></q-input>
        </div>
      </div>
    </div>
  </div>
</template>

<template id="lnbits-dynamic-chips">
  <q-input
    filled
    v-model="chip"
    @keydown.enter.prevent="addChip"
    type="text"
    label="wss://...."
    hint="Add relays"
    class="q-mb-md"
  >
    <q-btn @click="addChip" dense flat icon="add"></q-btn>
  </q-input>
  <div>
    <q-chip
      v-for="(chip, i) in chips"
      :key="chip"
      removable
      @remove="removeChip(i)"
      color="primary"
      text-color="white"
      :label="chip"
    >
    </q-chip>
  </div>
</template>

<template id="lnbits-notifications-btn">
  <q-btn
    v-if="g.user.wallets"
    :disabled="!this.isSupported"
    dense
    flat
    round
    @click="toggleNotifications()"
    :icon="this.isSubscribed ? 'notifications_active' : 'notifications_off'"
    size="sm"
    type="a"
  >
    <q-tooltip v-if="this.isSupported && !this.isSubscribed"
      >Subscribe to notifications</q-tooltip
    >
    <q-tooltip v-if="this.isSupported && this.isSubscribed"
      >Unsubscribe from notifications</q-tooltip
    >
    <q-tooltip v-if="this.isSupported && this.isPermissionDenied">
      Notifications are disabled,<br />please enable or reset permissions
    </q-tooltip>
    <q-tooltip v-if="!this.isSupported"
      >Notifications are not supported</q-tooltip
    >
  </q-btn>
</template>

<template id="lnbits-update-balance">
  <q-btn
    v-if="admin && small_btn"
    flat
    round
    color="primary"
    size="sm"
    icon="add"
  >
    <q-popup-edit class="text-white" v-slot="scope" v-model="credit">
      <q-input
        filled
        :label="$t('credit_label', {denomination: g.denomination})"
        v-model="scope.value"
        dense
        autofocus
        @keyup.enter="updateBalance(scope)"
      >
        <template v-slot:append>
          <q-icon name="edit" />
        </template>
      </q-input>
    </q-popup-edit>
    <q-tooltip v-text="$t('credit_hint')"></q-tooltip>
  </q-btn>

  <q-btn
    v-if="admin && !small_btn"
    color="primary"
    :label="$t('credit_debit')"
    class="float-right q-mt-sm"
    size="sm"
  >
    <q-popup-edit class="text-white" v-slot="scope" v-model="credit">
      <q-input
        filled
        :label="$t('credit_label', {denomination: g.denomination})"
        v-model="scope.value"
        type="number"
        dense
        autofocus
        @keyup.enter="updateBalance(scope)"
      >
        <template v-slot:append>
          <q-icon name="edit" />
        </template>
      </q-input>
    </q-popup-edit>
    <q-tooltip v-text="$t('credit_hint')"></q-tooltip>
  </q-btn>
</template>

<template id="lnbits-qrcode-lnurl">
  <div class="qrcode_lnurl__wrapper">
    <q-tabs
      v-model="tab"
      dense
      class="text-grey"
      active-color="primary"
      indicator-color="primary"
      align="justify"
      inline-label
    >
      <q-tab name="bech32" icon="qr_code" label="bech32"></q-tab>
      <q-tab name="lud17" icon="link" label="url (lud17)"></q-tab>
    </q-tabs>
    <lnbits-qrcode :value="lnurl" nfc="true"></lnbits-qrcode>
  </div>
</template>

<template id="lnbits-lnurlpay-success-action">
  <div>
    <p
      class="q-mb-sm"
      v-text="success_action.message || success_action.description"
    ></p>
    <code
      v-if="decryptedValue"
      class="text-h6 q-mt-sm q-mb-none"
      v-text="decryptedValue"
    ></code>
    <p v-else-if="success_action.url" class="text-h6 q-mt-sm q-mb-none">
      <a
        target="_blank"
        style="color: inherit"
        :href="success_action.url"
        v-text="success_action.url"
      ></a>
    </p>
  </div>
</template>

<template id="lnbits-extension-rating">
  <div style="margin-bottom: 3px">
    <q-rating v-model="rating" size="1.5em" :max="5" color="primary"
      ><q-tooltip>
        <span v-text="$t('extension_rating_soon')"></span> </q-tooltip
    ></q-rating>
  </div>
</template>

<template id="lnbits-extension-settings-form">
  <q-form v-if="settings" @submit="updateSettings" class="q-gutter-md">
    <lnbits-dynamic-fields
      :options="options"
      v-model="settings"
    ></lnbits-dynamic-fields>
    <div class="row q-mt-lg">
      <q-btn v-close-popup unelevated color="primary" type="submit"
        >Update</q-btn
      >
      <q-btn v-close-popup unelevated color="danger" @click="resetSettings"
        >Reset</q-btn
      >
      <slot name="actions"></slot>
    </div>
  </q-form>
</template>

<template id="lnbits-extension-settings-btn-dialog">
  <q-btn
    v-if="options"
    unelevated
    @click="show = true"
    color="primary"
    icon="settings"
    class="float-right"
  >
    <q-dialog v-model="show" position="top">
      <q-card class="q-pa-lg q-pt-xl lnbits__dialog-card">
        <lnbits-extension-settings-form
          :options="options"
          :adminkey="adminkey"
          :endpoint="endpoint"
        >
          <template v-slot:actions>
            <q-btn
              v-close-popup
              flat
              color="grey"
              class="q-ml-auto"
              :label="$t('close')"
            ></q-btn>
          </template>
        </lnbits-extension-settings-form>
      </q-card>
    </q-dialog>
  </q-btn>
</template>

<template id="user-id-only">
  <div v-if="authAction === 'login' && authMethod === 'user-id-only'">
    <q-card-section class="q-pb-none">
      <div class="text-center text-h6">
        <span v-text="$t('login_with_user_id')"></span>
      </div>
    </q-card-section>
    <q-card-section>
      <q-form @submit="loginUsr" class="q-gutter-md">
        <q-input
          dense
          filled
          v-model="user"
          label="usr"
          type="password"
        ></q-input>
        <q-card-actions vertical align="center" class="q-pa-none">
          <q-btn
            color="primary"
            :disable="user == ''"
            type="submit"
            :label="$t('login')"
            class="full-width q-mb-sm"
          ></q-btn>
          <q-btn
            @click="showLogin('username-password')"
            outline
            color="grey"
            :label="$t('back')"
            class="full-width"
          ></q-btn>
        </q-card-actions>
      </q-form>
    </q-card-section>
  </div>
  <div v-if="authAction === 'register' && authMethod === 'user-id-only'">
    <q-card-section class="q-pb-none">
      <div class="text-center text-h6">
        <span v-text="$t('create_new_wallet')"></span>
      </div>
    </q-card-section>
    <q-card-section>
      <q-form @submit="createWallet" class="q-gutter-md">
        <q-input
          dense
          filled
          v-model="walletName"
          :label="$t('name_your_wallet', {name: SITE_TITLE + ' *'})"
        ></q-input>
        <q-card-actions vertical align="center" class="q-pa-none">
          <q-btn
            color="primary"
            :disable="walletName == ''"
            type="submit"
            :label="$t('add_new_wallet')"
            class="full-width q-mb-sm"
          ></q-btn>
          <q-btn
            @click="showLogin('username-password')"
            outline
            color="grey"
            :label="$t('back')"
            class="full-width"
          ></q-btn>
        </q-card-actions>
      </q-form>
    </q-card-section>
  </div>
  <q-card-section v-show="showInstantLogin">
    <div>
      <separator-text :text="$t('instant_access_question')"></separator-text>
      <div class="text-body2 text-center q-mt-md">
        <q-badge
          @click="showLogin('user-id-only')"
          color="primary"
          class="cursor-pointer"
          rounded
        >
          <strong>
            <q-icon name="account_circle" size="xs"></q-icon>
            <span v-text="$t('login_with_user_id')"></span> </strong
        ></q-badge>
        <div v-if="allowed_new_users" class="inline-block">
          <span v-text="$t('or')" class="q-mx-sm text-grey"></span>
          <q-badge
            @click="showRegister('user-id-only')"
            color="primary"
            class="cursor-pointer"
            rounded
          >
            <strong>
              <q-icon name="add" size="xs"></q-icon>
              <span v-text="$t('create_new_wallet')"></span>
            </strong>
          </q-badge>
        </div>
      </div>
    </div>
  </q-card-section>
</template>

<template id="username-password">
  <div v-if="authMethods.includes('username-password')">
    <q-card-section class="q-pb-none">
      <div class="text-center text-h6 q-mb-sm q-mt-none q-pt-none">
        <span
          v-if="authAction === 'login'"
          v-text="$t('login_to_account')"
        ></span>
        <span
          v-if="authAction === 'register'"
          v-text="$t('create_account')"
        ></span>
        <span
          v-if="authAction === 'reset'"
          v-text="$t('reset_password')"
        ></span>
      </div>
    </q-card-section>
    <!-- LOGIN -->
    <q-card-section v-if="authAction === 'login'">
      <q-form @submit="login" class="q-gutter-sm">
        <q-input
          dense
          filled
          v-model="username"
          name="username"
          :label="$t('username_or_email') + ' *'"
        ></q-input>
        <q-input
          dense
          filled
          v-model="password"
          name="password"
          :label="$t('password') + ' *'"
          type="password"
        ></q-input>
        <div class="row justify-end">
          <q-btn
            :disable="!username || !password"
            color="primary"
            type="submit"
            :label="$t('login')"
            class="full-width"
          ></q-btn>
        </div>
      </q-form>
    </q-card-section>
    <!-- REGISTER -->
    <q-card-section v-if="allowed_new_users && authAction === 'register'">
      <q-form @submit="register" class="q-gutter-sm">
        <q-input
          dense
          filled
          required
          v-model="username"
          :label="$t('username') + ' *'"
          :rules="[val => validateUsername(val) || $t('invalid_username')]"
        ></q-input>
        <q-input
          dense
          filled
          v-model="password"
          :label="$t('password') + ' *'"
          type="password"
          :rules="[val => !val || val.length >= 8 || $t('invalid_password')]"
        ></q-input>
        <q-input
          dense
          filled
          v-model="passwordRepeat"
          :label="$t('password_repeat') + ' *'"
          type="password"
          :rules="[val => !val || val.length >= 8 || $t('invalid_password')]"
        ></q-input>
        <div class="row justify-end">
          <q-btn
            unelevated
            color="primary"
            :disable="
              !password ||
              !passwordRepeat ||
              !username ||
              password !== passwordRepeat
            "
            type="submit"
            class="full-width"
            :label="$t('create_account')"
          ></q-btn>
        </div>
      </q-form>
    </q-card-section>
    <q-card-section v-else-if="!allowed_new_users && authAction === 'register'">
      <h5 class="text-center" v-text="$t('new_user_not_allowed')"></h5>
    </q-card-section>
    <slot></slot>
    <!-- RESET -->
    <q-card-section v-if="authAction === 'reset'">
      <q-form @submit="reset" class="q-gutter-sm">
        <q-input
          dense
          filled
          required
          :disable="true"
          v-model="reset_key"
          :label="$t('reset_key') + ' *'"
        ></q-input>
        <q-input
          dense
          filled
          v-model="password"
          :label="$t('password') + ' *'"
          type="password"
          :rules="[val => !val || val.length >= 8 || $t('invalid_password')]"
        ></q-input>
        <q-input
          dense
          filled
          v-model="passwordRepeat"
          :label="$t('password_repeat') + ' *'"
          type="password"
          :rules="[val => !val || val.length >= 8 || $t('invalid_password')]"
        ></q-input>
        <div class="row justify-end">
          <q-btn
            unelevated
            color="primary"
            :disable="
              !password ||
              !passwordRepeat ||
              !reset_key ||
              password !== passwordRepeat
            "
            type="submit"
            class="full-width"
            :label="$t('reset_password')"
          ></q-btn>
        </div>
      </q-form>
    </q-card-section>
  </div>
  <!-- OAUTH -->
  <q-card-section v-if="showOauth">
    <div v-if="authMethods.includes('username-password')">
      <separator-text :text="$t('signin_with_oauth_or')"></separator-text>
    </div>
    <q-card-section v-else class="q-pb-none">
      <div class="text-center text-h6">
        <span v-text="$t('signin_with_oauth')"></span>
      </div>
    </q-card-section>
    <div class="flex justify-center q-mt-md" style="gap: 1rem">
      <q-btn
        v-if="authMethods.includes('nostr-auth-nip98')"
        @click="signInWithNostr()"
        outline
        no-caps
        color="grey"
        padding="sm md"
      >
        <div class="row items-center no-wrap">
          <q-avatar size="32px">
            <q-img
              src="/static/images/logos/nostr.svg"
              class="bg-primary"
            ></q-img>
          </q-avatar>
        </div>
        <q-tooltip>
          <span v-text="$t('signin_with_nostr')"></span>
        </q-tooltip>
      </q-btn>
      <q-btn
        v-if="authMethods.includes('github-auth')"
        href="/api/v1/auth/github"
        type="a"
        outline
        no-caps
        color="grey"
        padding="sm md"
      >
        <div class="row items-center no-wrap">
          <q-avatar size="32px">
            <q-img
              src="/static/images/github-logo.png"
              :style="$q.dark.isActive ? 'filter: grayscale(1) invert(1)' : ''"
            ></q-img>
          </q-avatar>
        </div>
        <q-tooltip><span v-text="$t('signin_with_github')"></span></q-tooltip>
      </q-btn>
      <q-btn
        v-if="authMethods.includes('google-auth')"
        href="/api/v1/auth/google"
        type="a"
        outline
        no-caps
        color="grey"
        padding="sm md"
      >
        <div class="row items-center no-wrap">
          <q-avatar size="32px">
            <q-img src="/static/images/google-logo.png"></q-img>
          </q-avatar>
        </div>
        <q-tooltip>
          <span v-text="$t('signin_with_google')"></span>
        </q-tooltip>
      </q-btn>
      <q-btn
        v-if="authMethods.includes('keycloak-auth')"
        href="/api/v1/auth/keycloak"
        type="a"
        outline
        no-caps
        color="grey"
        class="btn-fixed-width"
      >
        <q-avatar size="32px" class="q-mr-md">
          <q-img
            :src="
              keycloakIcon
                ? keycloakIcon
                : 'lnbits/static/images/keycloak-logo.png'
            "
          ></q-img>
        </q-avatar>
        <div>
          <span
            v-text="
              $t('signin_with_custom_org', {
                custom_org: keycloakOrg
              })
            "
          ></span>
        </div>
      </q-btn>
    </div>
  </q-card-section>
</template>

<template id="separator-text">
  <div class="row fit no-wrap items-center">
    <q-separator class="col q-mr-sm"></q-separator>
    <div class="col-grow q-mx-sm">
      <span :class="`text-h6 text-${color}`" v-text="text"></span>
    </div>
    <q-separator class="col q-ml-sm"></q-separator>
  </div>
</template>

<template id="lnbits-data-fields">
  <q-table
    :rows="fields"
    row-key="name"
    :columns="fieldsTable.columns"
    v-model:pagination="fieldsTable.pagination"
  >
    <template v-slot:bottom-row>
      <q-tr>
        <q-td auto-width></q-td>
        <q-td colspan="100%">
          <q-btn
            @click="addField"
            icon="add"
            size="sm"
            color="primary"
            class="q-ml-xs"
            :label="$t('add_field')"
          />
        </q-td>
      </q-tr>
    </template>

    <template v-slot:header="props">
      <q-tr :props="props">
        <q-th auto-width></q-th>
        <q-th v-for="col in props.cols" :key="col.name" :props="props">
          <span v-text="col.label"></span>
          <q-icon
            v-if="col.name == 'optional'"
            name="info"
            size="xs"
            color="primary"
            class="cursor-pointer q-ml-xs q-mb-xs"
          >
            <q-tooltip>
              <ul>
                <li>
                  The field is optional. The field can be left blank by the
                  user.
                </li>
                <li>
                  The UI form will not require this field to be filled out.
                </li>
                <li>The DB table will allow NULL values for this field.</li>
                <li>Non optional fields must be filled out.</li>
              </ul>
            </q-tooltip>
          </q-icon>
          <q-icon
            v-else-if="col.name == 'editable'"
            name="info"
            size="xs"
            color="primary"
            class="cursor-pointer q-ml-xs q-mb-xs"
          >
            <q-tooltip>
              <ul>
                <li>The UI form will allow the field to be edited.</li>
              </ul>
            </q-tooltip>
          </q-icon>
          <q-icon
            v-else-if="col.name == 'sortable'"
            name="info"
            size="xs"
            color="primary"
            class="cursor-pointer q-ml-xs q-mb-xs"
          >
            <q-tooltip>
              <ul>
                <li>In the UI Table a column will be created for the field.</li>
                <li>The UI Table column will be sortable.</li>
              </ul>
            </q-tooltip>
          </q-icon>
          <q-icon
            v-else-if="col.name == 'searchable'"
            name="info"
            size="xs"
            color="primary"
            class="cursor-pointer q-ml-xs q-mb-xs"
          >
            <q-tooltip>
              <ul>
                <li>
                  The free text search will include this field when searching.
                </li>
              </ul>
            </q-tooltip>
          </q-icon>
        </q-th>
      </q-tr>
    </template>
    <template v-slot:body="props">
      <q-tr :props="props">
        <q-td>
          <q-btn
            v-if="props.row.readonly !== true"
            @click="removeField(props.row)"
            round
            icon="delete"
            size="sm"
            color="negative"
            class="q-ml-xs"
          >
          </q-btn>
        </q-td>
        <q-td full-width>
          <q-input
            dense
            filled
            v-model="props.row.name"
            :readonly="props.row.readonly === true"
            type="text"
          >
          </q-input>
        </q-td>
        <q-td>
          <q-select
            filled
            dense
            emit-value
            map-options
            v-model="props.row.type"
            :options="fieldTypes"
            :readonly="props.row.readonly === true"
          ></q-select>
        </q-td>
        <q-td>
          <q-input dense filled v-model="props.row.label" type="text">
          </q-input>
        </q-td>
        <q-td>
          <q-input dense filled v-model="props.row.hint" type="text"> </q-input>
        </q-td>
        <q-td>
          <q-toggle
            v-model="props.row.optional"
            :readonly="props.row.readonly === true"
            size="md"
            color="green"
          />
        </q-td>
        <q-td v-if="!hideAdvanced">
          <q-toggle
            v-if="props.row.type !== 'json'"
            :readonly="props.row.readonly === true"
            v-model="props.row.editable"
            size="md"
            color="green"
          />
        </q-td>
        <q-td v-if="!hideAdvanced">
          <q-toggle
            v-if="props.row.type !== 'json'"
            :readonly="props.row.readonly === true"
            v-model="props.row.sortable"
            size="md"
            color="green"
          />
        </q-td>
        <q-td v-if="!hideAdvanced">
          <q-toggle
            v-if="props.row.type !== 'json'"
            :readonly="props.row.readonly === true"
            v-model="props.row.searchable"
            size="md"
            color="green"
          />
        </q-td>
      </q-tr>
      <q-tr v-if="props.row.type === 'json'" :props="props">
        <q-td></q-td>
        <q-td></q-td>
        <q-td colspan="100%">
          <lnbits-data-fields
            :fields="props.row.fields"
            :hide-advanced="true"
          ></lnbits-data-fields>
        </q-td>
      </q-tr>
    </template>
  </q-table>
</template>
