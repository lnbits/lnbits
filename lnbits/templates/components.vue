{% include('components/admin/funding.vue') %} {%
include('components/admin/funding_sources.vue') %} {%
include('components/admin/fiat_providers.vue') %} {%
include('components/admin/exchange_providers.vue') %} {%
include('components/admin/security.vue') %} {%
include('components/admin/users.vue') %} {%
include('components/admin/site_customisation.vue') %} {%
include('components/admin/audit.vue') %} {%
include('components/admin/extensions.vue') %} {%
include('components/admin/library.vue') %} {%
include('components/admin/notifications.vue') %} {%
include('components/admin/server.vue') %} {%
include('components/new_user_wallet.vue') %} {%
include('components/lnbits-footer.vue') %}

<template id="lnbits-wallet-list">
  <q-list
    v-if="g.user && g.user.wallets.length"
    dense
    class="lnbits-drawer__q-list"
  >
    <q-item
      v-for="walletRec in g.user.wallets.slice(
        0,
        g.user.extra.visible_wallet_count || 10
      )"
      :key="walletRec.id"
      clickable
      :active="g.wallet && g.wallet.id === walletRec.id"
      @click="selectWallet(walletRec)"
    >
      <q-item-section side>
        <q-avatar
          size="lg"
          :text-color="$q.dark.isActive ? 'black' : 'grey-3'"
          :class="g.wallet && g.wallet.id === walletRec.id ? '' : 'disabled'"
          :color="
            g.wallet && g.wallet.id === walletRec.id
              ? walletRec.extra.color
              : walletRec.extra.color
          "
          :icon="
            g.wallet && g.wallet.id === walletRec.id
              ? walletRec.extra.icon
              : walletRec.extra.icon
          "
        >
        </q-avatar>
      </q-item-section>
      <q-item-section
        style="max-width: 100px"
        class="q-my-none ellipsis full-width"
      >
        <q-item-label lines="1"
          ><span v-text="walletRec.name"></span
        ></q-item-label>
        <q-item-label class="q-my-none ellipsis full-width" caption>
          <strong v-text="formatBalance(walletRec.sat)"></strong>
        </q-item-label>
      </q-item-section>
      <q-item-section
        v-if="walletRec.walletType == 'lightning-shared'"
        side
        top
      >
        <q-icon name="group" :color="walletRec.extra.color" size="xs"></q-icon>
      </q-item-section>
    </q-item>
    <q-item
      v-if="g.user.hiddenWalletsCount > 0"
      clickable
      @click="goToWallets()"
    >
      <q-item-section side>
        <q-icon name="more_horiz" color="grey-5" size="md"></q-icon>
      </q-item-section>
      <q-item-section>
        <q-item-label
          lines="1"
          class="text-caption"
          v-text="$t('more_count', {count: g.user.hiddenWalletsCount})"
        ></q-item-label>
      </q-item-section>
    </q-item>
    <q-item clickable @click="createWallet()">
      <q-item-section side>
        <q-icon name="add" color="grey-5" size="md"></q-icon>
      </q-item-section>
      <q-item-section>
        <q-item-label
          lines="1"
          class="text-caption"
          v-text="$t('add_new_wallet')"
        ></q-item-label>
        <q-item-section v-if="g.user.walletInvitesCount" side>
          <q-badge>
            <span
              v-text="'Wallet Invite (' + g.user.walletInvitesCount + ')'"
            ></span>
          </q-badge>
        </q-item-section>
      </q-item-section>
    </q-item>
  </q-list>
</template>

<template id="lnbits-extension-list">
  <q-list
    v-if="
      (g.user && userExtensions && userExtensions.length > 0) || !!searchTerm
    "
    dense
    class="lnbits-drawer__q-list"
  >
    <q-item>
      <q-item-section>
        <q-input
          v-model="searchTerm"
          dense
          borderless
          :label="$t('extensions')"
        >
        </q-input>
      </q-item-section>
    </q-item>
    <q-item
      v-for="extension in userExtensions"
      :key="extension.code"
      clickable
      :active="extension.isActive"
      tag="a"
      :href="extension.url"
    >
      <q-item-section side>
        <q-avatar size="md">
          <q-img :src="extension.tile" style="max-width: 20px"></q-img>
        </q-avatar>
      </q-item-section>
      <q-item-section>
        <q-item-label lines="1"
          ><span v-text="extension.name"></span>
        </q-item-label>
      </q-item-section>
      <q-item-section side v-show="extension.isActive">
        <q-icon name="chevron_right" color="grey-5" size="md"></q-icon>
      </q-item-section>
    </q-item>
    <div class="lt-md q-mt-xl q-mb-xl"></div>
  </q-list>
</template>

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
          <span v-text="LNBITS_DENOMINATION"></span>
        </q-item-label>
      </q-item-section>
    </q-item>
    <q-item>
      <q-item-section>
        <q-item-label v-text="$t('fee')"></q-item-label>
        <q-item-label caption>
          <span v-text="(payment.fee / 1000).toFixed(3)"></span>
          <span v-text="LNBITS_DENOMINATION"></span>
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
            @click="copyText(payment.payment_hash)"
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
            @click="copyText(payment.bolt11)"
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
            @click="copyText(payment.preimage)"
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
        :label="$t('credit_label', {denomination: denomination})"
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
        :label="$t('credit_label', {denomination: denomination})"
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

<template id="lnbits-qrcode">
  <div
    class="qrcode__outer"
    :style="`margin: 13px auto; max-width: ${maxWidth}px`"
  >
    <div ref="qrWrapper" class="qrcode__wrapper">
      <a
        :href="href"
        :title="href === '' ? value : href"
        @click="clickQrCode"
        class="no-link full-width"
      >
        <qrcode-vue
          ref="qrCode"
          :value="value"
          :margin="margin"
          :size="size"
          level="Q"
          render-as="svg"
          class="rounded-borders q-mb-sm"
        >
          <q-tooltip :model-value="href === '' ? value : href"></q-tooltip>
        </qrcode-vue>
      </a>
      <img
        :src="logo"
        class="qrcode__image"
        alt="qrcode icon"
        style="pointer-events: none"
      />
    </div>
    <div
      v-if="showButtons"
      class="qrcode__buttons row q-gutter-x-sm items-center justify-end no-wrap full-width"
    >
      <q-btn
        v-if="nfc && nfcSupported"
        :disabled="nfcTagWriting"
        flat
        dense
        class="text-grey"
        icon="nfc"
        @click="writeNfcTag"
      >
        <q-tooltip>Write NFC Tag</q-tooltip>
      </q-btn>
      <q-btn flat dense class="text-grey" icon="download" @click="downloadSVG">
        <q-tooltip>Download SVG</q-tooltip>
      </q-btn>
      <q-btn
        flat
        dense
        class="text-grey"
        @click="copyText(value)"
        icon="content_copy"
      >
        <q-tooltip>Copy</q-tooltip>
      </q-btn>
    </div>
  </div>
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

<template id="payment-list">
  <div class="row items-center no-wrap">
    <div class="col" v-if="!mobileSimple || $q.screen.gt.sm">
      <q-input
        :label="$t('search_by_tag_memo_amount')"
        dense
        class="q-pr-xl"
        v-model="paymentsTable.search"
      >
        <template v-slot:before>
          <q-icon name="search"> </q-icon>
        </template>
        <template v-slot:append>
          <q-icon
            v-if="paymentsTable.search !== ''"
            name="close"
            @click="paymentsTable.search = ''"
            class="cursor-pointer"
          >
          </q-icon>
        </template>
      </q-input>
    </div>
    <div class="gt-sm col-auto">
      <q-btn icon="event" flat color="grey">
        <q-popup-proxy cover transition-show="scale" transition-hide="scale">
          <q-date v-model="searchDate" mask="YYYY-MM-DD" range />
          <div class="row">
            <div class="col-6">
              <q-btn
                label="Search"
                @click="searchByDate()"
                color="primary"
                flat
                class="float-left"
                v-close-popup
              />
            </div>
            <div class="col-6">
              <q-btn
                v-close-popup
                @click="clearDateSeach()"
                label="Clear"
                class="float-right"
                color="grey"
                flat
              />
            </div>
          </div>
        </q-popup-proxy>
        <q-badge
          v-if="searchDate?.to || searchDate?.from"
          class="q-mt-lg q-mr-md"
          color="primary"
          rounded
          floating
          style="border-radius: 6px"
        ></q-badge>
        <q-tooltip>
          <span v-text="$t('filter_date')"></span>
        </q-tooltip>
      </q-btn>
      <q-btn color="grey" icon="filter_alt" flat>
        <q-menu>
          <q-item dense>
            <q-checkbox
              v-model="searchStatus.success"
              @click="handleFilterChanged"
              label="Success Payments"
            ></q-checkbox>
          </q-item>
          <q-item dense>
            <q-checkbox
              v-model="searchStatus.pending"
              @click="handleFilterChanged"
              label="Pending Payments"
            ></q-checkbox>
          </q-item>
          <q-item dense>
            <q-checkbox
              v-model="searchStatus.failed"
              @click="handleFilterChanged"
              label="Failed Payments"
            ></q-checkbox>
          </q-item>
          <q-separator></q-separator>
          <q-item dense>
            <q-checkbox
              v-model="searchStatus.incoming"
              @click="handleFilterChanged"
              label="Incoming Payments"
            ></q-checkbox>
          </q-item>
          <q-item dense>
            <q-checkbox
              v-model="searchStatus.outgoing"
              @click="handleFilterChanged"
              label="Outgoing Payments"
            ></q-checkbox>
          </q-item>
        </q-menu>
        <q-tooltip>
          <span v-text="$t('filter_payments')"></span>
        </q-tooltip>
      </q-btn>
      <q-btn-dropdown
        dense
        outline
        persistent
        icon="archive"
        split
        class="q-mr-sm"
        color="grey"
        @click="exportCSV(false)"
      >
        <q-tooltip>
          <span v-text="$t('export_csv')"></span>
        </q-tooltip>
        <q-list>
          <q-item>
            <q-item-section>
              <q-input
                @keydown.enter="addFilterTag"
                filled
                dense
                v-model="exportTagName"
                type="text"
                label="Payment Tags"
                class="q-pa-sm"
              >
                <q-btn @click="addFilterTag" dense flat icon="add"></q-btn>
              </q-input>
            </q-item-section>
          </q-item>
          <q-item v-if="exportPaymentTagList.length">
            <q-item-section>
              <div>
                <q-chip
                  v-for="tag in exportPaymentTagList"
                  :key="tag"
                  removable
                  @remove="removeExportTag(tag)"
                  color="primary"
                  text-color="white"
                  :label="tag"
                ></q-chip>
              </div>
            </q-item-section>
          </q-item>

          <q-item>
            <q-item-section>
              <q-btn
                v-close-popup
                outline
                color="grey"
                @click="exportCSV(true)"
                :label="$t('export_csv_details')"
              ></q-btn>
            </q-item-section>
          </q-item>
        </q-list>
      </q-btn-dropdown>
    </div>
  </div>
  <div class="row q-my-md"></div>
  <q-table
    dense
    flat
    :rows="paymentsOmitter"
    :row-key="paymentTableRowKey"
    :columns="paymentsTable.columns"
    :no-data-label="$t('no_transactions')"
    :filter="paymentsTable.filter"
    :loading="paymentsTable.loading"
    :hide-header="mobileSimple"
    :hide-bottom="mobileSimple"
    v-model:pagination="paymentsTable.pagination"
    @request="fetchPayments"
  >
    <template v-slot:header="props">
      <q-tr :props="props" class="text-grey-5">
        <q-th auto-width></q-th>
        <q-th
          v-for="col in props.cols"
          :key="col.name"
          :props="props"
          v-text="col.label"
        ></q-th>
      </q-tr>
    </template>
    <template v-slot:body="props">
      <q-tr :props="props">
        <q-td auto-width class="text-center cursor-pointer">
          <q-icon
            v-if="props.row.isPaid"
            size="14px"
            :name="props.row.isOut ? 'call_made' : 'call_received'"
            :color="props.row.isOut ? 'pink' : 'green'"
            @click="props.expand = !props.expand"
          ></q-icon>
          <q-icon
            v-else-if="props.row.isFailed"
            name="warning"
            color="yellow"
            @click="props.expand = !props.expand"
          >
            <q-tooltip><span>failed</span></q-tooltip>
          </q-icon>
          <q-icon
            v-else
            name="downloading"
            color="grey"
            :style="
              props.row.isOut
                ? 'transform: rotate(225deg)'
                : 'transform: scaleX(-1) rotate(315deg)'
            "
            @click="props.expand = !props.expand"
          >
            <q-tooltip><span v-text="$t('pending')"></span></q-tooltip>
          </q-icon>
        </q-td>
        <q-td
          key="time"
          :props="props"
          style="white-space: normal; word-break: break-all"
        >
          <q-icon
            v-if="
              props.row.isIn &&
              props.row.isPending &&
              props.row.extra.hold_invoice
            "
            name="pause_presentation"
            color="grey"
            class="cursor-pointer q-mr-sm"
            @click="showHoldInvoiceDialog(props.row)"
          >
            <q-tooltip><span v-text="$t('hold_invoice')"></span></q-tooltip>
          </q-icon>
          <q-badge
            v-if="props.row.tag"
            color="yellow"
            text-color="black"
            class="q-mr-sm"
          >
            <a
              v-text="'#' + props.row.tag"
              class="inherit"
              :href="['/', props.row.tag].join('')"
            ></a>
          </q-badge>
          <span v-text="props.row.memo"></span>
          <span
            class="text-grey-5 q-ml-sm ellipsis"
            v-if="props.row.extra.internal_memo"
            v-text="`(${props.row.extra.internal_memo})`"
          ></span>
          <br />

          <i>
            <span class="text-grey-5" v-text="props.row.dateFrom"></span>
            <q-tooltip><span v-text="props.row.date"></span></q-tooltip>
          </i>
        </q-td>
        <q-td
          auto-width
          key="amount"
          v-if="denomination != 'sats'"
          :props="props"
          class="col1"
          v-text="parseFloat(String(props.row.fsat).replaceAll(',', '')) / 100"
        >
        </q-td>
        <q-td class="col2" auto-width key="amount" v-else :props="props">
          <span v-text="props.row.fsat"></span>
          <br />
          <i v-if="props.row.extra.wallet_fiat_currency">
            <span
              v-text="
                formatCurrency(
                  props.row.extra.wallet_fiat_amount,
                  props.row.extra.wallet_fiat_currency
                )
              "
            ></span>
            <br />
          </i>
          <i v-if="props.row.extra.fiat_currency">
            <span
              v-text="
                formatCurrency(
                  props.row.extra.fiat_amount,
                  props.row.extra.fiat_currency
                )
              "
            ></span>
          </i>
        </q-td>
        <q-dialog v-model="props.expand" :props="props" position="top">
          <q-card class="q-pa-sm q-pt-xl lnbits__dialog-card">
            <q-card-section>
              <q-list bordered separator>
                <q-expansion-item
                  expand-separator
                  :default-opened="!(props.row.isIn && props.row.isPending)"
                >
                  <template v-slot:header>
                    <q-item-section avatar>
                      <q-icon
                        :color="
                          props.row.isPaid && props.row.isIn
                            ? 'green'
                            : props.row.isPaid && props.row.isOut
                              ? 'pink'
                              : props.row.isFailed
                                ? 'yellow'
                                : 'grey'
                        "
                        :name="
                          props.row.isPaid && props.row.isIn
                            ? 'call_received'
                            : props.row.isPaid && props.row.isOut
                              ? 'call_made'
                              : props.row.isFailed
                                ? 'warning'
                                : 'settings_ethernet'
                        "
                      />
                    </q-item-section>

                    <q-item-section>
                      <q-item-label
                        v-text="
                          props.row.isIn && props.row.isPending
                            ? $t('invoice_waiting')
                            : props.row.isOut && props.row.isPending
                              ? $t('outgoing_payment_pending')
                              : props.row.isPaid && props.row.isIn
                                ? $t('payment_received')
                                : props.row.isPaid && props.row.isOut
                                  ? $t('payment_sent')
                                  : props.row.isFailed
                                    ? $t('payment_failed')
                                    : ''
                        "
                      ></q-item-label>
                    </q-item-section>
                    <q-item-section v-if="props.row.tag" side>
                      <q-badge
                        v-if="props.row.extra && !!props.row.extra.tag"
                        color="yellow"
                        text-color="black"
                      >
                        #<span v-text="props.row.tag"></span>
                      </q-badge>
                    </q-item-section>
                  </template>
                  <q-separator></q-separator>
                  <lnbits-payment-details
                    :payment="props.row"
                  ></lnbits-payment-details>
                </q-expansion-item>
              </q-list>

              <div
                v-if="props.row.isIn && props.row.isPending && props.row.bolt11"
              >
                <div v-if="props.row.extra.fiat_payment_request">
                  <lnbits-qrcode
                    :value="props.row.extra.fiat_payment_request"
                    :href="props.row.extra.fiat_payment_request"
                    :show-buttons="false"
                  ></lnbits-qrcode>
                </div>
                <div v-else>
                  <lnbits-qrcode
                    :value="'lightning:' + props.row.bolt11.toUpperCase()"
                    :href="'lightning:' + props.row.bolt11"
                  ></lnbits-qrcode>
                </div>
              </div>
              <div class="row q-mt-md">
                <q-btn
                  outline
                  color="grey"
                  @click="checkPayment(props.row.payment_hash)"
                  icon="refresh"
                  :label="$t('payment_check')"
                ></q-btn>
                <q-btn
                  v-close-popup
                  flat
                  color="grey"
                  class="q-ml-auto"
                  :label="$t('close')"
                ></q-btn>
              </div>
            </q-card-section>
          </q-card>
        </q-dialog>
        <q-dialog v-model="hodlInvoice.show" position="top">
          <q-card class="q-pa-sm q-pt-xl lnbits__dialog-card">
            <q-card-section>
              <q-item-label class="text-h6">
                <span v-text="$t('hold_invoice')"></span>
              </q-item-label>
              <q-item-label class="text-subtitle2">
                <span v-text="$t('hold_invoice_description')"></span>
              </q-item-label>
            </q-card-section>
            <q-card-section>
              <q-input
                filled
                :label="$t('preimage')"
                :hint="$t('preimage_hint')"
                v-model="hodlInvoice.preimage"
                dense
                autofocus
                @keyup.enter="settleHoldInvoice(hodlInvoice.preimage)"
              >
              </q-input>
            </q-card-section>
            <q-card-section class="row q-gutter-x-sm">
              <q-btn
                @click="settleHoldInvoice(hodlInvoice.preimage)"
                outline
                v-close-popup
                color="grey"
                :label="$t('settle_invoice')"
              >
              </q-btn>
              <q-btn
                v-close-popup
                outline
                color="grey"
                class="q-ml-sm"
                @click="cancelHoldInvoice(hodlInvoice.payment.payment_hash)"
                :label="$t('cancel_invoice')"
              ></q-btn>
              <q-btn
                v-close-popup
                flat
                color="grey"
                class="q-ml-auto"
                :label="$t('close')"
              ></q-btn>
            </q-card-section>
          </q-card>
        </q-dialog>
      </q-tr>
    </template>
  </q-table>
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
          :label="$t('name_your_wallet', {name: '{{ SITE_TITLE }} *'})"
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
              class="bg-primary"
              :src="`{{ static_url_for('static', 'images/logos/nostr.svg') }}`"
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
              :src="`{{ static_url_for('static', 'images/github-logo.png') }}`"
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
            <q-img
              :src="`{{ static_url_for('static', 'images/google-logo.png') }}`"
            ></q-img>
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
                : `{{ static_url_for('static', 'images/keycloak-logo.png') }}`
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
