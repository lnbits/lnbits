<template id="page-account">
  <div>
    <q-card flat bordered class="q-mb-md">
      <q-card-section class="row items-center q-col-gutter-md">
        <div class="col-12 col-md">
          <h1 class="text-h6 q-my-none" v-text="$t('my_account')"></h1>
          <div
            class="text-caption text-grey"
            v-text="$t('my_account_description')"
          ></div>
        </div>
        <div class="col-12 col-md-auto">
          <div class="row items-center q-gutter-sm">
            <q-icon
              :name="isUserTouched ? 'edit' : 'check_circle'"
              :color="isUserTouched ? 'warning' : 'positive'"
              size="18px"
            ></q-icon>
            <span
              class="text-caption"
              v-text="
                isUserTouched ? $t('unsaved_changes') : $t('all_changes_saved')
              "
            ></span>
          </div>
        </div>
        <div class="col-12">
          <q-btn
            @click="updateAccount"
            :label="$t('update_account')"
            icon="save"
            unelevated
            color="primary"
            :disable="!isUserTouched"
          ></q-btn>
        </div>
      </q-card-section>
    </q-card>

    <q-card flat bordered>
      <div v-if="$q.screen.lt.md" class="q-pa-md">
        <q-select
          v-model="tab"
          :options="accountNavigationItems"
          option-value="value"
          option-label="label"
          emit-value
          map-options
          outlined
          :label="$t('my_account')"
        >
          <template v-slot:prepend>
            <q-icon :name="activeAccountSection.icon"></q-icon>
          </template>
        </q-select>
      </div>

      <div class="row items-stretch">
        <q-card-section
          v-if="$q.screen.gt.sm"
          class="col-md-2 q-pa-none column"
        >
          <nav class="column col" aria-label="Account sections">
            <q-list dense class="q-py-md">
              <q-item
                v-for="item in accountNavigationItems"
                :key="item.value"
                clickable
                v-ripple
                class="q-py-xs"
                :active="tab === item.value"
                active-class="text-primary"
                @click="selectAccountSection(item.value)"
              >
                <q-item-section side>
                  <q-icon
                    :name="item.icon"
                    :color="tab === item.value ? 'primary' : undefined"
                    size="md"
                  ></q-icon>
                </q-item-section>
                <q-item-section>
                  <q-item-label lines="1" v-text="item.label"></q-item-label>
                </q-item-section>
              </q-item>
            </q-list>
            <q-space></q-space>
            <q-separator></q-separator>
            <q-list dense class="q-py-sm">
              <q-item clickable v-ripple class="q-py-xs" @click="utils.logout">
                <q-item-section side>
                  <q-icon name="logout" size="md"></q-icon>
                </q-item-section>
                <q-item-section>
                  <q-item-label lines="1" v-text="$t('logout')"></q-item-label>
                </q-item-section>
              </q-item>
            </q-list>
          </nav>
        </q-card-section>

        <q-separator v-if="$q.screen.gt.sm" vertical></q-separator>

        <q-card-section class="col-12 col-md q-pa-none">
          <q-card-section class="row items-start q-col-gutter-md">
            <div class="col-auto">
              <q-icon
                :name="activeAccountSection.icon"
                color="primary"
                size="24px"
              ></q-icon>
            </div>
            <div class="col">
              <div
                class="text-subtitle1"
                v-text="activeAccountSection.label"
              ></div>
              <div
                class="text-caption text-grey"
                v-text="activeAccountSection.description"
              ></div>
            </div>
            <div v-if="tab === 'user'" class="col-12 col-sm-auto text-right">
              <q-btn
                v-if="!credentialsData.show"
                @click="showUpdateCredentials()"
                :label="$t('change_password')"
                unelevated
                color="primary"
              ></q-btn>
              <q-btn
                v-else
                @click="credentialsData.show = false"
                :label="$t('back')"
                outline
                color="grey"
              ></q-btn>
            </div>
          </q-card-section>
          <q-separator></q-separator>
          <q-tab-panels v-if="g.user" v-model="tab">
            <q-tab-panel name="user">
              <div v-if="credentialsData.show">
                <q-card-section>
                  <div class="row items-center q-gutter-sm q-mb-md">
                    <q-icon
                      name="password"
                      color="primary"
                      size="20px"
                    ></q-icon>
                    <div class="text-subtitle1" v-text="$t('password')"></div>
                  </div>
                  <div class="row q-col-gutter-md">
                    <div class="col-12 col-md-6">
                      <q-input
                        v-model="credentialsData.username"
                        :label="$t('username')"
                        filled
                        dense
                        :readonly="hasUsername"
                      ></q-input>
                    </div>
                    <div v-if="g.user.hasPassword" class="col-12 col-md-6">
                      <q-input
                        v-model="credentialsData.oldPassword"
                        type="password"
                        autocomplete="off"
                        label="Old Password"
                        filled
                        dense
                        :rules="[
                          val =>
                            !val || val.length >= 8 || $t('invalid_password')
                        ]"
                      ></q-input>
                    </div>
                    <div class="col-12 col-md-6">
                      <q-input
                        v-model="credentialsData.newPassword"
                        type="password"
                        autocomplete="off"
                        :label="$t('password')"
                        filled
                        dense
                        :rules="[
                          val =>
                            !val || val.length >= 8 || $t('invalid_password')
                        ]"
                      ></q-input>
                    </div>
                    <div class="col-12 col-md-6">
                      <q-input
                        v-model="credentialsData.newPasswordRepeat"
                        type="password"
                        autocomplete="off"
                        :label="$t('password_repeat')"
                        filled
                        dense
                        :rules="[
                          val =>
                            !val || val.length >= 8 || $t('invalid_password')
                        ]"
                      ></q-input>
                    </div>
                    <div class="col-12 row justify-end">
                      <q-btn
                        @click="updatePassword"
                        :disable="disableUpdatePassword()"
                        unelevated
                        color="primary"
                        :label="$t('update_password')"
                      ></q-btn>
                    </div>
                  </div>
                </q-card-section>
                <q-separator></q-separator>
                <q-card-section>
                  <div class="row items-center q-gutter-sm q-mb-md">
                    <q-icon name="vpn_key" color="primary" size="20px"></q-icon>
                    <div class="text-subtitle1">
                      Nostr <span v-text="$t('pubkey')"></span>
                    </div>
                  </div>
                  <div class="row items-start q-col-gutter-md">
                    <div class="col-12 col-md">
                      <q-input
                        v-model="credentialsData.pubkey"
                        type="text"
                        label="Pubkey"
                        filled
                        dense
                      ></q-input>
                    </div>
                    <div class="col-12 col-md-auto row justify-end">
                      <q-btn
                        @click="updatePubkey"
                        unelevated
                        color="primary"
                        :label="$t('update_pubkey')"
                      ></q-btn>
                    </div>
                  </div>
                </q-card-section>
              </div>
              <div v-else>
                <q-card-section v-if="g.user.extra.picture">
                  <div class="row">
                    <div class="col">
                      <q-img
                        style="max-width: 100px"
                        :src="g.user.extra.picture"
                        class="float-right"
                      ></q-img>
                    </div>
                  </div>
                </q-card-section>

                <q-card-section>
                  <div class="row q-col-gutter-md">
                    <div class="col-12 col-md-6">
                      <q-input
                        v-model="g.user.id"
                        :label="$t('user_id')"
                        filled
                        dense
                        readonly
                        :type="showUserId ? 'text' : 'password'"
                        autocomplete="off"
                        ><q-btn
                          @click="showUserId = !showUserId"
                          dense
                          flat
                          :icon="showUserId ? 'visibility_off' : 'visibility'"
                          color="grey"
                        ></q-btn>
                      </q-input>
                    </div>
                    <div class="col-12 col-md-6">
                      <q-input
                        v-model="g.user.username"
                        :label="$t('username')"
                        filled
                        dense
                        :readonly="hasUsername"
                      >
                      </q-input>
                    </div>
                    <div class="col-12 col-md-6">
                      <q-input
                        v-model="g.user.pubkey"
                        :label="$t('pubkey')"
                        filled
                        dense
                        readonly
                      >
                      </q-input>
                    </div>
                    <div class="col-12 col-md-6">
                      <q-input
                        v-model="g.user.email"
                        :label="$t('email')"
                        filled
                        dense
                        readonly
                      >
                      </q-input>
                    </div>
                  </div>
                  <div v-if="!g.user.email" class="row">
                    <div
                      v-if="
                        'google-auth' in g.settings.authMethods ||
                        'github-auth' in g.settings.authMethods ||
                        'keycloak-auth' in g.settings.authMethods ||
                        'oidc-auth' in g.settings.authMethods
                      "
                      class="col q-pa-sm text-h6"
                    >
                      <span v-text="$t('verify_email')"></span>:
                    </div>
                    <div
                      v-if="'google-auth' in g.settings.authMethods"
                      class="col q-pa-sm"
                    >
                      <q-btn
                        :href="`/api/v1/auth/google?user_id=${g.user.id}`"
                        type="a"
                        outline
                        no-caps
                        rounded
                        color="grey"
                        class="full-width"
                      >
                        <q-avatar size="32px" class="q-mr-md">
                          <q-img
                            :src="'{{ static_url_for('static', 'images/google-logo.png') }}'"
                          ></q-img>
                        </q-avatar>
                        <div>Google</div>
                      </q-btn>
                    </div>
                    <div
                      v-if="'github-auth' in g.settings.authMethods"
                      class="col q-pa-sm"
                    >
                      <q-btn
                        :href="`/api/v1/auth/github?user_id=${g.user.id}`"
                        type="a"
                        outline
                        no-caps
                        color="grey"
                        rounded
                        class="full-width"
                      >
                        <q-avatar size="32px" class="q-mr-md">
                          <q-img
                            :src="'{{ static_url_for('static', 'images/github-logo.png') }}'"
                          ></q-img>
                        </q-avatar>
                        <div>GitHub</div>
                      </q-btn>
                    </div>
                    <div
                      v-if="'keycloak-auth' in g.settings.authMethods"
                      class="col q-pa-sm"
                    >
                      <q-btn
                        :href="`/api/v1/auth/keycloak?user_id=${g.user.id}`"
                        type="a"
                        outline
                        no-caps
                        color="grey"
                        rounded
                        class="full-width"
                      >
                        <q-avatar size="32px" class="q-mr-md">
                          <q-img
                            :src="
                                  g.settings.keycloakIcon
                                    ? g.settings.keycloakIcon
                                    : '{{ static_url_for('static', 'images/keycloak-logo.png') }}'
                                "
                          ></q-img>
                        </q-avatar>
                        <div
                          v-text="g.settings.keycloakOrg || 'Keycloak'"
                        ></div>
                      </q-btn>
                    </div>
                    <div
                      v-if="'oidc-auth' in g.settings.authMethods"
                      class="col q-pa-sm"
                    >
                      <q-btn
                        :href="`/api/v1/auth/oidc?user_id=${g.user.id}`"
                        type="a"
                        outline
                        no-caps
                        color="grey"
                        rounded
                        class="full-width"
                      >
                        <q-avatar size="32px" class="q-mr-md">
                          <q-img
                            :src="
                                  g.settings.oidcIcon
                                    ? g.settings.oidcIcon
                                    : '{{ static_url_for('static', 'images/generic-oidc-logo.svg') }}'
                                "
                          ></q-img>
                        </q-avatar>
                        <div v-text="g.settings.oidcOrg || 'OIDC'"></div>
                      </q-btn>
                    </div>
                  </div>
                </q-card-section>

                <q-card-section v-if="g.user.extra">
                  <div class="row q-col-gutter-md">
                    <div class="col-12 col-md-6">
                      <q-input
                        v-model="g.user.extra.first_name"
                        :label="$t('first_name')"
                        filled
                        dense
                      >
                      </q-input>
                    </div>
                    <div class="col-12 col-md-6">
                      <q-input
                        v-model="g.user.extra.last_name"
                        :label="$t('last_name')"
                        filled
                        dense
                      >
                      </q-input>
                    </div>
                    <div class="col-12 col-md-6">
                      <q-input
                        v-model="g.user.extra.provider"
                        :label="$t('auth_provider')"
                        filled
                        dense
                        readonly
                      >
                      </q-input>
                    </div>
                    <div class="col-12 col-md-6">
                      <q-input
                        v-model="g.user.extra.visible_wallet_count"
                        :label="$t('visible_wallet_count')"
                        filled
                        dense
                        type="number"
                      ></q-input>
                    </div>
                    <div class="col-12 col-md-6">
                      <q-input
                        v-model="g.user.external_id"
                        :label="$t('external_id')"
                        filled
                        dense
                        readonly
                      >
                      </q-input>
                    </div>
                    <div class="col-12 col-md-6">
                      <q-input
                        v-model="g.user.extra.picture"
                        :label="$t('picture')"
                        :hint="$t('user_picture_desc')"
                        filled
                        dense
                      >
                      </q-input>
                    </div>
                  </div>
                </q-card-section>
              </div>
            </q-tab-panel>
            <q-tab-panel name="theme">
              <q-btn
                v-if="g.user.admin"
                class="absolute-top-right"
                flat
                round
                icon="settings"
                to="/admin#site_customisation"
                ><q-tooltip v-text="$t('admin_settings')"></q-tooltip
              ></q-btn>
              <div class="row q-col-gutter-md q-mb-md">
                <div class="col-12 col-md-6">
                  <div
                    class="text-caption text-grey q-mb-sm"
                    v-text="$t('language')"
                  ></div>
                  <lnbits-language-dropdown
                    @language-changed="
                      siteCustomisationChanged({locale: $event})
                    "
                  />
                </div>
                <div class="col-12 col-md-6">
                  <div
                    class="text-caption text-grey q-mb-sm"
                    v-text="$t('color_scheme')"
                  ></div>
                  <q-btn
                    v-for="theme in themeOptions"
                    :key="theme.name"
                    @click="siteCustomisationChanged({themeChoice: theme.name})"
                    :color="theme.color"
                    dense
                    flat
                    icon="circle"
                    size="md"
                    ><q-tooltip><span v-text="theme.name"></span></q-tooltip>
                  </q-btn>
                </div>
              </div>
              <q-input
                v-model="g.bgimageChoice"
                :label="$t('background_image')"
                filled
                dense
                class="q-mb-md"
                @update:model-value="
                  siteCustomisationChanged({bgimageChoice: $event})
                "
              >
                <template v-slot:append>
                  <q-btn
                    dense
                    flat
                    round
                    icon="upload"
                    @click="$refs.backgroundImageInput.click()"
                  >
                    <q-tooltip>Upload background image</q-tooltip>
                  </q-btn>
                </template>
                <q-tooltip
                  ><span v-text="$t('background_image')"></span
                ></q-tooltip>
              </q-input>
              <input
                type="file"
                ref="backgroundImageInput"
                accept="image/*"
                style="display: none"
                @change="onBackgroundImageInput"
              />

              <div class="row q-col-gutter-md q-mb-md">
                <div class="col-12 col-sm-6 col-lg-4">
                  <q-toggle
                    dense
                    icon="gradient"
                    v-model="g.gradientChoice"
                    :label="$t('gradient_background')"
                    @update:model-value="
                      siteCustomisationChanged({gradientChoice: $event})
                    "
                  >
                    <q-tooltip
                      ><span v-text="$t('toggle_gradient')"></span
                    ></q-tooltip>
                  </q-toggle>
                </div>
                <div class="col-12 col-sm-6 col-lg-4">
                  <q-toggle
                    dense
                    icon="rounded_corner"
                    v-model="g.cardRoundedChoice"
                    :label="$t('rounded_ui')"
                    @update:model-value="
                      siteCustomisationChanged({cardRoundedChoice: $event})
                    "
                  >
                    <q-tooltip
                      ><span v-text="$t('toggle_rounded_ui')"></span
                    ></q-tooltip>
                  </q-toggle>
                </div>
                <div class="col-12 col-sm-6 col-lg-4">
                  <q-toggle
                    dense
                    icon="gradient"
                    v-model="g.cardGradientChoice"
                    :label="$t('card_gradient')"
                    @update:model-value="
                      siteCustomisationChanged({cardGradientChoice: $event})
                    "
                  >
                    <q-tooltip
                      ><span v-text="$t('toggle_card_gradient')"></span
                    ></q-tooltip>
                  </q-toggle>
                </div>
                <div class="col-12 col-sm-6 col-lg-4">
                  <q-toggle
                    dense
                    icon="blur_on"
                    v-model="g.cardShadowChoice"
                    :label="$t('card_shadow')"
                    @update:model-value="
                      siteCustomisationChanged({cardShadowChoice: $event})
                    "
                  >
                    <q-tooltip
                      ><span v-text="$t('toggle_card_shadow')"></span
                    ></q-tooltip>
                  </q-toggle>
                </div>
                <div class="col-12 col-sm-6 col-lg-4">
                  <q-toggle
                    dense
                    icon="menu_open"
                    v-model="g.burgerMenuChoice"
                    :label="$t('burger_menu_background')"
                    @update:model-value="
                      siteCustomisationChanged({burgerMenuChoice: $event})
                    "
                  >
                    <q-tooltip
                      ><span v-text="$t('toggle_burger_menu_background')"></span
                    ></q-tooltip>
                  </q-toggle>
                </div>
                <div class="col-12 col-sm-6 col-lg-4">
                  <q-toggle
                    dense
                    v-model="g.darkChoice"
                    :label="$t('toggle_darkmode')"
                    @update:model-value="
                      siteCustomisationChanged({darkChoice: $event})
                    "
                    :icon="$q.dark.isActive ? 'brightness_3' : 'wb_sunny'"
                  >
                    <q-tooltip
                      ><span v-text="$t('toggle_darkmode')"></span
                    ></q-tooltip>
                  </q-toggle>
                </div>
              </div>

              <div class="row q-col-gutter-md">
                <div class="col-12 col-md-6">
                  <q-select
                    v-model="g.borderChoice"
                    :options="borderOptions"
                    :label="$t('border_choices')"
                    filled
                    dense
                    @update:model-value="
                      siteCustomisationChanged({borderChoice: $event})
                    "
                  >
                    <q-tooltip
                      ><span v-text="$t('border_choices')"></span
                    ></q-tooltip>
                  </q-select>
                </div>
                <div class="col-12 col-md-6">
                  <q-select
                    v-model="g.reactionChoice"
                    :options="reactionOptions"
                    :label="$t('payment_reactions')"
                    filled
                    dense
                    @update:model-value="
                      siteCustomisationChanged({reactionChoice: $event})
                    "
                  >
                    <q-tooltip
                      ><span v-text="$t('payment_reactions')"></span
                    ></q-tooltip>
                  </q-select>
                </div>
              </div>

              <div class="row items-center justify-between q-mt-md">
                <div class="row items-center q-gutter-sm">
                  <span v-text="$t('notifications')"></span>
                  <lnbits-notifications-btn
                    v-if="g.user"
                    pubkey="g.settings.webpushPubkey"
                  ></lnbits-notifications-btn>
                </div>
                <q-btn
                  @click="resetThemeDefaults"
                  :label="$t('reset_defaults')"
                  unelevated
                  color="primary"
                ></q-btn>
              </div>
            </q-tab-panel>
            <q-tab-panel name="notifications">
              <q-card-section>
                <div class="row q-mb-md">
                  <div class="col-4">
                    <span v-text="$t('notifications_nostr_identifier')"></span>
                    <br />
                    <q-badge
                      v-if="!g.settings.nostrConfigured"
                      v-text="$t('not_connected')"
                    ></q-badge>
                  </div>
                  <div class="col-8">
                    <q-input
                      filled
                      dense
                      v-model="g.user.extra.notifications.nostr_identifier"
                      :hint="$t('notifications_nostr_identifier_desc')"
                    >
                    </q-input>
                  </div>
                </div>

                <div class="row q-mb-md">
                  <div class="col-4">
                    <span v-text="$t('notifications_chat_id')"></span>
                    <br />
                    <q-badge
                      v-if="!g.settings.telegramConfigured"
                      v-text="$t('not_connected')"
                    ></q-badge>
                  </div>
                  <div class="col-8">
                    <q-input
                      filled
                      dense
                      v-model="g.user.extra.notifications.telegram_chat_id"
                      :hint="$t('notifications_chat_id_desc')"
                    />
                  </div>
                </div>
                <q-separator class="q-mb-md"></q-separator>
                <div class="row q-mb-md">
                  <div class="col-4">
                    <span v-text="$t('notification_outgoing_payment')"></span>
                  </div>
                  <div class="col-8">
                    <q-input
                      filled
                      dense
                      type="number"
                      min="0"
                      step="1"
                      v-model="
                        g.user.extra.notifications.outgoing_payments_sats
                      "
                      :hint="$t('notification_outgoing_payment_desc')"
                    />
                  </div>
                </div>
                <div class="row q-mb-md">
                  <div class="col-4">
                    <span v-text="$t('notification_incoming_payment')"></span>
                  </div>
                  <div class="col-8">
                    <q-input
                      filled
                      dense
                      type="number"
                      min="0"
                      step="1"
                      v-model="
                        g.user.extra.notifications.incoming_payments_sats
                      "
                      :hint="$t('notification_incoming_payment_desc')"
                    />
                  </div>
                </div>
                <div class="row q-mb-md">
                  <div class="col-4">
                    <span v-text="$t('exclude_wallets')"></span>
                  </div>
                  <div class="col-8">
                    <q-select
                      filled
                      dense
                      emit-value
                      map-options
                      multiple
                      v-model="g.user.extra.notifications.excluded_wallets"
                      :options="g.user.walletOptions"
                      :label="$t('exclude_wallets')"
                      :hint="$t('notifications_excluded_wallets_desc')"
                      class="q-mt-sm"
                    >
                    </q-select>
                  </div>
                </div>
              </q-card-section>
            </q-tab-panel>
            <q-tab-panel name="api_acls">
              <div class="row q-mb-md">
                <q-badge v-if="g.user.admin">
                  <span v-text="$t('access_control_list_admin_warning')"></span>
                </q-badge>
              </div>

              <q-card-section>
                <div class="row q-mb-md q-gutter-y-md">
                  <div class="col-sm-12 col-md-6">
                    <q-select
                      v-model="selectedApiAcl.id"
                      emit-value
                      map-options
                      @update:model-value="handleApiACLSelected"
                      :options="
                        apiAcl.data.map(t => ({label: t.name, value: t.id}))
                      "
                      :label="$t('access_control_list')"
                      dense
                    >
                    </q-select>
                  </div>
                  <div class="col-sm-12 col-md-6">
                    <q-btn
                      @click="askPasswordAndRunFunction('newApiAclDialog')"
                      filled
                      outline
                      icon="add"
                      :label="$t('access_control_list')"
                      color="grey"
                      class="float-right"
                    ></q-btn>
                  </div>
                </div>
                <div v-if="selectedApiAcl.id">
                  <div class="row q-mb-md">
                    <div class="col-sm-12 col-md-6">
                      <q-select
                        :options="
                          selectedApiAcl.token_id_list.map(t => ({
                            label: t.name,
                            value: t.id
                          }))
                        "
                        v-model="apiAcl.selectedTokenId"
                        emit-value
                        map-options
                        :label="$t('api_tokens')"
                        dense
                      >
                      </q-select>
                    </div>

                    <div class="col-sm-12 col-md-6 q-pl-sm">
                      <q-btn
                        v-if="apiAcl.selectedTokenId"
                        @click="askPasswordAndRunFunction('deleteToken')"
                        icon="delete"
                        filled
                        color="negative"
                        class="float-left"
                      ></q-btn>
                      <q-btn
                        @click="askPasswordAndRunFunction('newTokenAclDialog')"
                        outline
                        icon="add"
                        :label="$t('api_token')"
                        filled
                        color="grey"
                        class="float-right"
                      ></q-btn>
                    </div>
                  </div>
                  <div
                    v-if="selectedApiToken && selectedApiToken.expires_at"
                    class="row items-center q-mb-md q-gutter-sm"
                  >
                    <span v-text="expiryAt"></span>
                    <span v-text="$t('status') + ':'"></span>
                    <q-badge
                      :color="tokenStatus.badgeColor"
                      :label="tokenStatus.status"
                    ></q-badge>
                  </div>
                  <div v-if="apiAcl.apiToken" class="row q-mb-md">
                    <div class="col-12">
                      <q-badge>
                        <span>Use this token in the HTTP</span>
                        <strong>
                          &nbsp;<code>Authorization</code>
                          &nbsp;
                        </strong>
                        <span> header.</span>
                      </q-badge>
                    </div>
                    <div class="col-12">
                      <table
                        class="full-width lnbits__table-bordered"
                        style="
                          border-collapse: collapse;
                          background-color: grey;
                        "
                      >
                        <thead>
                          <tr>
                            <th>
                              <span class="float-left">Header Name</span>
                            </th>
                            <th>
                              <span class="float-left">Header Value</span>
                            </th>
                          </tr>
                        </thead>
                        <tbody>
                          <tr>
                            <td>
                              <strong>Authorization</strong>
                            </td>
                            <td>
                              <div class="row q-pt-sm">
                                <div class="col-2 q-mt-sm">
                                  <strong>Bearer &nbsp;</strong>
                                </div>
                                <div class="col-10">
                                  <q-input
                                    v-model="apiAcl.apiToken"
                                    :label="$t('api_token_id')"
                                    filled
                                    dense
                                    readonly
                                    :type="
                                      selectedApiAcl.showId
                                        ? 'text'
                                        : 'password'
                                    "
                                    autocomplete="off"
                                    class="q-mb-md"
                                  >
                                    <q-btn
                                      @click="
                                        selectedApiAcl.showId =
                                          !selectedApiAcl.showId
                                      "
                                      dense
                                      flat
                                      :icon="
                                        selectedApiAcl.showId
                                          ? 'visibility_off'
                                          : 'visibility'
                                      "
                                      color="black"
                                    ></q-btn>

                                    <q-btn
                                      @click="utils.copyText(apiAcl.apiToken)"
                                      icon="content_copy"
                                      color="black"
                                      flat
                                      dense
                                    ></q-btn>
                                  </q-input>
                                </div>
                              </div>
                            </td>
                          </tr>
                        </tbody>
                      </table>
                    </div>
                    <div class="col-12">
                      <q-badge>
                        <span
                          >Please store this token. It cannot be later
                          retrieved, only revoked.</span
                        >
                      </q-badge>
                    </div>
                  </div>

                  <q-table
                    row-key="path"
                    :rows="selectedApiAcl.endpoints"
                    :columns="apiAcl.columns"
                    v-model:pagination="apiAcl.pagination"
                  >
                    <template v-slot:header="props">
                      <q-tr :props="props">
                        <q-th
                          v-for="col in props.cols"
                          :key="col.name"
                          :props="props"
                        >
                          <q-toggle
                            v-if="col.name == 'read'"
                            v-model="selectedApiAcl.allRead"
                            @update:model-value="handleAllEndpointsReadAccess()"
                            :label="$t('read')"
                            size="sm"
                          ></q-toggle>
                          <q-toggle
                            v-else-if="col.name == 'write'"
                            v-model="selectedApiAcl.allWrite"
                            @update:model-value="
                              handleAllEndpointsWriteAccess()
                            "
                            :label="$t('write')"
                            size="sm"
                          ></q-toggle>
                          <span v-else v-text="col.label"></span>
                        </q-th>
                      </q-tr>
                    </template>
                    <template v-slot:body="props">
                      <q-tr :props="props">
                        <q-td>
                          <span v-text="props.row.name"></span>
                        </q-td>
                        <q-td>
                          <span v-text="props.row.path"></span>
                        </q-td>
                        <q-td>
                          <q-toggle size="sm" v-model="props.row.read" />
                        </q-td>
                        <q-td>
                          <q-toggle size="sm" v-model="props.row.write" />
                        </q-td>
                      </q-tr>
                    </template>
                  </q-table>
                  <q-separator></q-separator>
                </div>

                <div v-if="selectedApiAcl.id" class="row q-mt-md">
                  <div class="col-sm-12 col-md-6">
                    <q-btn
                      @click="askPasswordAndRunFunction('updateApiACLs')"
                      :label="$t('update')"
                      filled
                      color="primary"
                    ></q-btn>
                  </div>
                  <div class="col-sm-12 col-md-6">
                    <q-btn
                      @click="askPasswordAndRunFunction('deleteApiACL')"
                      :label="$t('delete')"
                      icon="delete"
                      color="negative"
                      class="float-right"
                    >
                    </q-btn>
                  </div>
                </div>
              </q-card-section>
            </q-tab-panel>
            <q-tab-panel name="assets">
              <q-card-section>
                <div class="row">
                  <div class="col-md-2 col-sm-12">
                    <q-btn
                      color="primary"
                      :label="$t('upload')"
                      @click="$refs.imageInput.click()"
                      class="full-width"
                    ></q-btn>
                    <input
                      type="file"
                      ref="imageInput"
                      style="display: none"
                      @change="onImageInput"
                    />
                  </div>
                  <div class="col-md-4 col-sm-12">
                    <q-toggle
                      v-model="assetsUploadToPublic"
                      label="Visible for everyone (public)"
                    ></q-toggle>
                  </div>
                  <div class="col-md-6 col-sm-12">
                    <q-input
                      :label="$t('search')"
                      dense
                      class="full-width q-pb-xl"
                      v-model="assetsTable.search"
                    >
                      <template v-slot:before>
                        <q-icon name="search"> </q-icon>
                      </template>
                      <template v-slot:append>
                        <q-icon
                          v-if="assetsTable.search !== ''"
                          name="close"
                          @click="assetsTable.search = ''"
                          class="cursor-pointer"
                        >
                        </q-icon>
                      </template>
                    </q-input>
                  </div>
                </div>
              </q-card-section>
              <q-separator></q-separator>
              <q-card-section>
                <q-table
                  grid
                  grid-header
                  flat
                  bordered
                  :rows="assets"
                  :columns="assetsTable.columns"
                  v-model:pagination="assetsTable.pagination"
                  :loading="assetsTable.loading"
                  @request="getUserAssets"
                  row-key="id"
                  :filter="filter"
                  hide-header
                >
                  <template v-slot:item="props">
                    <div class="q-pa-xs col-xs-12 col-sm-6 col-md-4">
                      <q-card class="q-ma-sm wallet-list-card text-center">
                        <q-card-section>
                          <a
                            v-if="props.row.thumbnail_base64"
                            target="_blank"
                            style="color: inherit"
                            :href="`/api/v1/assets/${props.row.id}/data`"
                          >
                            <q-img
                              :src="
                                'data:image/png;base64,' +
                                props.row.thumbnail_base64
                              "
                              :alt="props.row.name"
                              loading="lazy"
                              style="height: 128px"
                              class="text-center cursor-pointer"
                            >
                            </q-img>
                          </a>
                          <q-icon v-else name="web_asset"></q-icon>
                        </q-card-section>
                        <q-separator></q-separator>

                        <q-card-section>
                          <div class="row items-center no-wrap q-col-gutter-sm">
                            <div class="col">
                              <q-btn-dropdown
                                color="grey"
                                dense
                                outline
                                no-caps
                                class="full-width"
                                :label="props.row.name"
                                :icon="props.row.is_public ? 'public' : ''"
                              >
                                <q-list>
                                  <q-item
                                    clickable
                                    v-close-popup
                                    @click="copyAssetLinkToClipboard(props.row)"
                                  >
                                    <q-item-section avatar>
                                      <q-avatar icon="content_copy" />
                                    </q-item-section>
                                    <q-item-section>
                                      <q-item-label>Copy Link</q-item-label>
                                      <q-item-label caption
                                        >Copy asset link to
                                        clipboard</q-item-label
                                      >
                                    </q-item-section>
                                  </q-item>

                                  <q-item
                                    clickable
                                    v-close-popup
                                    @click="toggleAssetPublicAccess(props.row)"
                                  >
                                    <q-item-section avatar>
                                      <q-avatar
                                        :icon="
                                          props.row.is_public
                                            ? 'public_off'
                                            : 'public'
                                        "
                                        text-color="primary"
                                      />
                                    </q-item-section>
                                    <q-item-section v-if="props.row.is_public">
                                      <q-item-label>Unpublish</q-item-label>
                                      <q-item-label caption
                                        >Make this asset private</q-item-label
                                      >
                                    </q-item-section>
                                    <q-item-section v-else>
                                      <q-item-label>Publish</q-item-label>
                                      <q-item-label caption
                                        >Make this asset public</q-item-label
                                      >
                                    </q-item-section>
                                  </q-item>

                                  <q-item
                                    clickable
                                    v-close-popup
                                    @click="deleteAsset(props.row)"
                                  >
                                    <q-item-section avatar>
                                      <q-avatar
                                        icon="delete"
                                        text-color="negative"
                                      />
                                    </q-item-section>
                                    <q-item-section>
                                      <q-item-label>Delete</q-item-label>
                                      <q-item-label caption
                                        >Permanently delete this
                                        asset</q-item-label
                                      >
                                    </q-item-section>
                                  </q-item>
                                </q-list>
                              </q-btn-dropdown>
                            </div>
                            <div class="col-auto">
                              <q-btn
                                type="a"
                                target="_blank"
                                rel="noopener noreferrer"
                                color="primary"
                                dense
                                flat
                                round
                                icon="image"
                                :href="`/api/v1/assets/${props.row.id}/data`"
                              >
                                <q-tooltip>Full image</q-tooltip>
                              </q-btn>
                            </div>
                            <div
                              class="col-auto"
                              v-if="props.row.thumbnail_base64"
                            >
                              <q-btn
                                type="a"
                                target="_blank"
                                rel="noopener noreferrer"
                                color="secondary"
                                dense
                                flat
                                round
                                icon="photo_size_select_small"
                                :href="`/api/v1/assets/${props.row.id}/thumbnail`"
                              >
                                <q-tooltip>Thumbnail</q-tooltip>
                              </q-btn>
                            </div>
                          </div>
                        </q-card-section>
                      </q-card>
                    </div>
                  </template>
                </q-table>
              </q-card-section>
            </q-tab-panel>
            <q-tab-panel name="labels">
              <q-card-section>
                <div class="row">
                  <div class="col-md-2 col-sm-12">
                    <q-btn
                      @click="openAddLabelDialog()"
                      :label="$t('add_label')"
                      color="primary"
                      class="full-width"
                    ></q-btn>
                  </div>
                  <div class="col-md-1 col-sm-12"></div>
                  <div class="col-md-9 col-sm-12">
                    <q-input
                      :label="$t('search')"
                      dense
                      class="full-width q-pb-xl"
                      v-model="labelsTable.search"
                    >
                      <template v-slot:before>
                        <q-icon name="search"> </q-icon>
                      </template>
                      <template v-slot:append>
                        <q-icon
                          v-if="labelsTable.search !== ''"
                          name="close"
                          @click="labelsTable.search = ''"
                          class="cursor-pointer"
                        >
                        </q-icon>
                      </template>
                    </q-input>
                  </div>
                </div>
              </q-card-section>
              <q-separator></q-separator>
              <q-card-section>
                <q-table
                  :rows="g.user.extra.labels"
                  :columns="labelsTable.columns"
                  v-model:pagination="labelsTable.pagination"
                  :loading="labelsTable.loading"
                  row-key="name"
                  :filter="labelsTable.search"
                >
                  <template v-slot:body="props">
                    <q-tr :props="props">
                      <q-td key="actions" :props="props">
                        <q-btn
                          @click="openEditLabelDialog(props.row)"
                          dense
                          flat
                          icon="edit"
                          color="primary"
                        ></q-btn>
                        <q-btn
                          @click="deleteUserLabel(props.row)"
                          dense
                          flat
                          icon="delete"
                          color="negative"
                          class="q-ml-md"
                        ></q-btn>
                      </q-td>
                      <q-td key="name" :props="props">
                        <span v-text="props.row.name"></span>
                      </q-td>
                      <q-td key="description" :props="props">
                        <span v-text="props.row.description"></span>
                      </q-td>
                      <q-td key="color" :props="props">
                        <q-badge
                          class="q-pa-sm"
                          :style="{
                            backgroundColor: props.row.color,
                            color: 'white'
                          }"
                        >
                          <span v-text="props.row.color"></span>
                        </q-badge>
                      </q-td>
                    </q-tr>
                  </template>
                </q-table>
              </q-card-section>
            </q-tab-panel>
          </q-tab-panels>
        </q-card-section>
      </div>
    </q-card>
  </div>

  <q-dialog v-model="apiAcl.showPasswordDialog" position="top">
    <q-card class="q-pa-md q-pt-md lnbits__dialog-card">
      <strong>User Password</strong>
      <div class="row q-mt-md q-col-gutter-md">
        <div class="col-12">
          <q-input
            v-model="apiAcl.password"
            type="password"
            autocomplete="off"
            dense
            filled
            label="Password"
            hint="User password is required for this action."
          >
          </q-input>
        </div>
      </div>
      <div class="row q-mt-lg">
        <q-btn
          v-close-popup
          flat
          color="grey"
          class="q-ml-auto"
          v-text="$t('cancel')"
        ></q-btn>
        <q-btn
          @click="runPasswordGuardedFunction()"
          :label="$t('ok')"
          color="primary"
        ></q-btn>
      </div>
    </q-card>
  </q-dialog>

  <q-dialog v-model="apiAcl.showNewAclDialog" position="top">
    <q-card class="q-pa-md q-pt-md lnbits__dialog-card">
      <strong>New API Access Control List</strong>
      <div class="row q-mt-md q-col-gutter-md">
        <div class="col-12">
          <q-input v-model="apiAcl.newAclName" dense filled label="ACL Name">
          </q-input>
        </div>
      </div>
      <div class="row q-mt-lg">
        <q-btn @click="addApiACL()" label="Create" color="primary"></q-btn>
        <q-btn
          v-close-popup
          flat
          color="grey"
          class="q-ml-auto"
          v-text="$t('close')"
        ></q-btn>
      </div>
    </q-card>
  </q-dialog>
  <q-dialog v-model="apiAcl.showNewTokenDialog" position="top">
    <q-card class="q-pa-md q-pt-md lnbits__dialog-card">
      <strong>New API Token</strong>
      <div class="row q-col-gutter-md q-mt-md">
        <div class="col-12">
          <q-input
            v-model="apiAcl.newTokenName"
            dense
            filled
            label="Token Name"
          >
          </q-input>
        </div>
        <div class="col-12">
          <q-input
            v-model="apiAcl.newTokenExpiry"
            dense
            filled
            label="Expiration"
            hit="Expiration time in minutes (default xxx)"
          >
            <template v-slot:prepend>
              <q-icon name="event" class="cursor-pointer">
                <q-popup-proxy
                  cover
                  transition-show="scale"
                  transition-hide="scale"
                >
                  <q-date
                    v-model="apiAcl.newTokenExpiry"
                    mask="YYYY-MM-DD HH:mm"
                  >
                    <div class="row items-center justify-end">
                      <q-btn v-close-popup label="Close" color="primary" flat />
                    </div>
                  </q-date>
                </q-popup-proxy>
              </q-icon>
            </template>

            <template v-slot:append>
              <q-icon name="access_time" class="cursor-pointer">
                <q-popup-proxy
                  cover
                  transition-show="scale"
                  transition-hide="scale"
                >
                  <q-time
                    v-model="apiAcl.newTokenExpiry"
                    mask="YYYY-MM-DD HH:mm"
                    format24h
                  >
                    <div class="row items-center justify-end">
                      <q-btn v-close-popup label="Close" color="primary" flat />
                    </div>
                  </q-time>
                </q-popup-proxy>
              </q-icon>
            </template>
          </q-input>
        </div>
      </div>
      <div class="row q-mt-lg">
        <q-btn
          @click="generateApiToken()"
          label="Create"
          color="primary"
        ></q-btn>
        <q-btn
          v-close-popup
          flat
          color="grey"
          class="q-ml-auto"
          v-text="$t('close')"
        ></q-btn>
      </div>
    </q-card>
  </q-dialog>
  <q-dialog v-model="labelsDialog.show" position="top">
    <q-card class="q-pa-md q-pt-md lnbits__dialog-card">
      <strong v-text="$t('label')"></strong>
      <div class="row q-mt-md q-col-gutter-md">
        <div class="col-12">
          <q-input
            v-model="labelsDialog.data.name"
            dense
            filled
            :label="$t('name')"
          >
          </q-input>
        </div>
        <div class="col-12">
          <q-input
            v-model="labelsDialog.data.description"
            dense
            filled
            type="textarea"
            rows="3"
            :label="$t('description')"
          >
          </q-input>
        </div>
        <div class="col-12">
          <q-input
            v-model="labelsDialog.data.color"
            filled
            dense
            class="my-input"
          >
            <template v-slot:append>
              <q-icon name="colorize" class="cursor-pointer">
                <q-popup-proxy
                  cover
                  transition-show="scale"
                  transition-hide="scale"
                >
                  <q-color
                    v-model="labelsDialog.data.color"
                    default-view="palette"
                  />
                </q-popup-proxy>
              </q-icon>
            </template>
          </q-input>
        </div>
      </div>
      <div class="row q-mt-lg">
        <q-btn
          v-close-popup
          flat
          color="grey"
          class="q-ml-auto"
          v-text="$t('cancel')"
        ></q-btn>
        <q-btn
          v-if="
            g.user.extra.labels.some(
              label => label.name === labelsDialog.data.name
            )
          "
          @click="updateUserLabel()"
          :disable="!labelsDialog.data.name || !labelsDialog.data.color"
          :label="$t('update_label')"
          color="primary"
        ></q-btn>
        <q-btn
          v-else
          @click="addUserLabel()"
          :disable="!labelsDialog.data.name || !labelsDialog.data.color"
          :label="$t('add_label')"
          color="primary"
        ></q-btn>
      </div>
    </q-card>
  </q-dialog>
</template>
