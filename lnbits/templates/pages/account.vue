<template id="page-account">
  <div class="row q-col-gutter-md q-mb-md">
    <div class="col-12">
      <q-card>
        <div class="q-pa-sm">
          <div class="row items-center justify-between q-gutter-xs">
            <div class="col">
              <q-btn @click="updateAccount" unelevated color="primary">
                <q-badge
                  v-if="isUserTouched"
                  color="negative"
                  size="xs"
                  floating
                ></q-badge>
                <span v-text="$t('update_account')"></span>
              </q-btn>
              <q-badge v-if="isUserTouched" class="q-ml-sm" color="primary">
                <span v-text="$t('must_save')"></span>
              </q-badge>
            </div>
          </div>
        </div>
      </q-card>
    </div>
  </div>

  <div class="row q-col-gutter-md q-mb-md">
    <div class="col-12">
      <q-card>
        <q-splitter>
          <template v-slot:before>
            <!-- todo: small screen as in settings -->
            <q-tabs v-model="tab" vertical active-color="primary">
              <q-tab
                name="user"
                icon="person"
                :label="$q.screen.gt.sm ? $t('account_settings') : ''"
              >
                <q-tooltip v-if="!$q.screen.gt.sm"
                  ><span v-text="$t('account_settings')"></span
                ></q-tooltip>
              </q-tab>

              <q-tab
                name="notifications"
                icon="notifications"
                :label="$q.screen.gt.sm ? $t('notifications') : ''"
              >
                <q-tooltip v-if="!$q.screen.gt.sm"
                  ><span v-text="$t('notifications')"></span
                ></q-tooltip>
              </q-tab>
              <q-tab
                name="theme"
                icon="palette"
                :label="$q.screen.gt.sm ? $t('look_and_feel') : ''"
              >
                <q-tooltip v-if="!$q.screen.gt.sm"
                  ><span v-text="$t('look_and_feel')"></span
                ></q-tooltip>
              </q-tab>
              <q-tab
                name="api_acls"
                icon="lock"
                :label="$q.screen.gt.sm ? $t('access_control_list') : ''"
              >
                <q-tooltip v-if="!$q.screen.gt.sm"
                  ><span v-text="$t('access_control_list')"></span
                ></q-tooltip>
              </q-tab>
              <q-tab
                name="assets"
                icon="perm_media"
                :label="$q.screen.gt.sm ? $t('assets') : ''"
              >
                <q-tooltip v-if="!$q.screen.gt.sm"
                  ><span v-text="$t('assets')"></span
                ></q-tooltip>
              </q-tab>
              <q-tab
                name="labels"
                icon="local_offer"
                :label="$q.screen.gt.sm ? $t('labels') : ''"
              >
                <q-tooltip v-if="!$q.screen.gt.sm"
                  ><span v-text="$t('labels')"></span
                ></q-tooltip>
              </q-tab>
            </q-tabs>
          </template>
          <template v-slot:after>
            <q-scroll-area style="height: 80vh">
              <q-tab-panels v-if="g.user" v-model="tab">
                <q-tab-panel name="user">
                  <div v-if="credentialsData.show">
                    <q-card-section>
                      <div class="row">
                        <div class="col">
                          <h4 class="q-my-none">
                            <span v-text="$t('password')"></span>
                          </h4>
                        </div>
                        <div class="col">
                          <q-img
                            v-if="g.user.extra.picture"
                            style="max-width: 100px"
                            :src="g.user.extra.picture"
                            class="float-right"
                          ></q-img>
                        </div>
                      </div>
                    </q-card-section>
                    <q-card-section>
                      <q-input
                        v-model="credentialsData.username"
                        :label="$t('username')"
                        filled
                        dense
                        :readonly="hasUsername"
                        class="q-mb-md"
                      ></q-input>
                      <q-input
                        v-if="g.user.has_password"
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
                      <q-input
                        v-model="credentialsData.newPasswordRepeat"
                        type="password"
                        autocomplete="off"
                        :label="$t('password_repeat')"
                        filled
                        dense
                        class="q-mb-md"
                        :rules="[
                          val =>
                            !val || val.length >= 8 || $t('invalid_password')
                        ]"
                      ></q-input>
                      <q-btn
                        @click="updatePassword"
                        :disable="disableUpdatePassword()"
                        unelevated
                        color="primary"
                        class="float-right"
                        :label="$t('update_password')"
                      >
                      </q-btn>
                    </q-card-section>
                    <q-separator class="q-mt-xl"></q-separator>
                    <q-card-section>
                      <div class="col q-mb-sm">
                        <h4 class="q-my-none">
                          Nostr <span v-text="$t('pubkey')"></span>
                        </h4>
                      </div>
                      <q-input
                        v-model="credentialsData.pubkey"
                        type="text"
                        label="Pubkey"
                        filled
                        dense
                      ></q-input>
                      <q-btn
                        @click="updatePubkey"
                        unelevated
                        color="primary"
                        class="q-mt-md float-right"
                        :label="$t('update_pubkey')"
                      >
                      </q-btn>
                    </q-card-section>
                    <q-separator class="q-mt-xl"></q-separator>
                    <q-card-section class="q-pb-lg">
                      <q-btn
                        @click="credentialsData.show = false"
                        :label="$t('back')"
                        outline
                        unelevated
                        color="grey"
                      ></q-btn>
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
                      <q-input
                        v-model="g.user.id"
                        :label="$t('user_id')"
                        filled
                        dense
                        readonly
                        :type="showUserId ? 'text' : 'password'"
                        class="q-mb-md"
                        ><q-btn
                          @click="showUserId = !showUserId"
                          dense
                          flat
                          :icon="showUserId ? 'visibility_off' : 'visibility'"
                          color="grey"
                        ></q-btn>
                      </q-input>
                      <q-input
                        v-model="g.user.username"
                        :label="$t('username')"
                        filled
                        dense
                        :readonly="hasUsername"
                        class="q-mb-md"
                      >
                      </q-input>
                      <q-input
                        v-model="g.user.pubkey"
                        :label="$t('pubkey')"
                        filled
                        dense
                        readonly
                        class="q-mb-md"
                      >
                      </q-input>
                      <q-input
                        v-model="g.user.email"
                        :label="$t('email')"
                        filled
                        dense
                        readonly
                        class="q-mb-md"
                      >
                      </q-input>
                      <div v-if="!g.user.email" class="row"></div>
                      <div v-if="!g.user.email" class="row">
                        {% if "google-auth" in LNBITS_AUTH_METHODS or
                        "github-auth" in LNBITS_AUTH_METHODS %}
                        <div class="col q-pa-sm text-h6">
                          <span v-text="$t('verify_email')"></span>:
                        </div>
                        {%endif%} {% if "google-auth" in LNBITS_AUTH_METHODS %}
                        <div class="col q-pa-sm">
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
                        {%endif%} {% if "github-auth" in LNBITS_AUTH_METHODS %}
                        <div class="col q-pa-sm">
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
                        {%endif%}
                      </div>
                    </q-card-section>

                    <q-card-section v-if="g.user.extra">
                      <q-input
                        v-model="g.user.extra.first_name"
                        :label="$t('first_name')"
                        filled
                        dense
                        class="q-mb-md"
                      >
                      </q-input>
                      <q-input
                        v-model="g.user.extra.last_name"
                        :label="$t('last_name')"
                        filled
                        dense
                        class="q-mb-md"
                      >
                      </q-input>
                      <q-input
                        v-model="g.user.extra.provider"
                        :label="$t('auth_provider')"
                        filled
                        dense
                        readonly
                        class="q-mb-md"
                      >
                      </q-input>
                      <q-input
                        v-model="g.user.external_id"
                        :label="$t('external_id')"
                        filled
                        dense
                        readonly
                        class="q-mb-md"
                      >
                      </q-input>

                      <q-input
                        v-model="g.user.extra.picture"
                        :label="$t('picture')"
                        :hint="$t('user_picture_desc')"
                        filled
                        dense
                        class="q-mb-md"
                      >
                      </q-input>
                    </q-card-section>
                    <q-separator></q-separator>
                    <q-card-section>
                      <q-btn
                        @click="showUpdateCredentials()"
                        :label="$t('change_password')"
                        filled
                        color="primary"
                        class="float-right q-mb-md"
                      ></q-btn>
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
                  <div class="row q-mb-md">
                    <div class="col-4">
                      <span v-text="$t('language')"></span>
                    </div>
                    <div class="col-8">
                      <lnbits-language-dropdown />
                    </div>
                  </div>
                  <div class="row q-mb-md">
                    <div class="col-4">
                      <span v-text="$t('visible_wallet_count')"></span>
                    </div>
                    <div class="col-8">
                      <q-input
                        v-model="g.user.extra.visible_wallet_count"
                        :label="$t('visible_wallet_count')"
                        filled
                        dense
                        type="number"
                        class="q-mb-md"
                      ></q-input>
                    </div>
                  </div>

                  <div class="row q-mb-md">
                    <div class="col-4">
                      <span v-text="$t('color_scheme')"></span>
                    </div>
                    <div class="col-8">
                      <q-btn
                        v-for="theme in themeOptions"
                        :key="theme.name"
                        @click="g.themeChoice = theme.name"
                        :color="theme.color"
                        dense
                        flat
                        icon="circle"
                        size="md"
                        ><q-tooltip
                          ><span v-text="theme.name"></span
                        ></q-tooltip>
                      </q-btn>
                    </div>
                  </div>
                  <div class="row q-mb-md">
                    <div class="col-4">
                      <span v-text="$t('background_image')"></span>
                    </div>
                    <div class="col-8">
                      <q-input
                        v-model="g.bgimageChoice"
                        :label="$t('background_image')"
                      >
                        <q-tooltip
                          ><span v-text="$t('background_image')"></span
                        ></q-tooltip>
                      </q-input>
                    </div>
                  </div>
                  <div class="row q-mb-md">
                    <div class="col-4">
                      <span v-text="$t('gradient_background')"></span>
                    </div>
                    <div class="col-8">
                      <q-toggle
                        dense
                        flat
                        round
                        icon="gradient"
                        v-model="g.gradientChoice"
                      >
                        <q-tooltip
                          ><span v-text="$t('toggle_gradient')"></span
                        ></q-tooltip>
                      </q-toggle>
                    </div>
                  </div>

                  <div class="row q-mb-md">
                    <div class="col-4">
                      <span v-text="$t('toggle_darkmode')"></span>
                    </div>
                    <div class="col-8">
                      <q-toggle
                        dense
                        flat
                        round
                        v-model="g.darkChoice"
                        :icon="$q.dark.isActive ? 'brightness_3' : 'wb_sunny'"
                        size="sm"
                      >
                        <q-tooltip
                          ><span v-text="$t('toggle_darkmode')"></span
                        ></q-tooltip>
                      </q-toggle>
                    </div>
                  </div>
                  <div class="row q-mb-md">
                    <div class="col-4">
                      <span v-text="$t('border_choices')"></span>
                    </div>
                    <div class="col-8">
                      <q-select
                        v-model="g.borderChoice"
                        :options="borderOptions"
                        label="Borders"
                      >
                        <q-tooltip
                          ><span v-text="$t('border_choices')"></span
                        ></q-tooltip>
                      </q-select>
                    </div>
                  </div>
                  <div class="row q-mb-md">
                    <div class="col-4">
                      <span v-text="$t('notifications')"></span>
                    </div>
                    <div class="col-8">
                      <lnbits-notifications-btn
                        v-if="g.user"
                        pubkey="{{ WEBPUSH_PUBKEY }}"
                      ></lnbits-notifications-btn>
                    </div>
                  </div>
                  <div class="row q-mb-md">
                    <div class="col-4">
                      <span v-text="$t('payment_reactions')"></span>
                    </div>
                    <div class="col-8">
                      <q-select
                        v-model="g.reactionChoice"
                        :options="reactionOptions"
                        label="Reactions"
                      >
                        <q-tooltip
                          ><span v-text="$t('payment_reactions')"></span
                        ></q-tooltip>
                      </q-select>
                    </div>
                  </div>
                </q-tab-panel>
                <q-tab-panel name="notifications">
                  <q-card-section>
                    <div class="row q-mb-md">
                      <div class="col-4">
                        <span
                          v-text="$t('notifications_nostr_identifier')"
                        ></span>
                        <br />
                        <q-badge
                          v-if="!LNBITS_NOSTR_CONFIGURED"
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
                          v-if="!LNBITS_TELEGRAM_CONFIGURED"
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
                        <span
                          v-text="$t('notification_outgoing_payment')"
                        ></span>
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
                        <span
                          v-text="$t('notification_incoming_payment')"
                        ></span>
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
                      <span
                        v-text="$t('access_control_list_admin_warning')"
                      ></span>
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
                            @click="
                              askPasswordAndRunFunction('newTokenAclDialog')
                            "
                            outline
                            icon="add"
                            :label="$t('api_token')"
                            filled
                            color="grey"
                            class="float-right"
                          ></q-btn>
                        </div>
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
                                          @click="
                                            utils.copyText(apiAcl.apiToken)
                                          "
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
                                @update:model-value="
                                  handleAllEndpointsReadAccess()
                                "
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
                                :href="`/api/v1/assets/${props.row.id}/binary`"
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
                              <q-btn-dropdown
                                color="grey"
                                dense
                                outline
                                no-caps
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
            </q-scroll-area>
          </template>
        </q-splitter>
      </q-card>
    </div>
  </div>

  <q-dialog v-model="apiAcl.showPasswordDialog" position="top">
    <q-card class="q-pa-md q-pt-md lnbits__dialog-card">
      <strong>User Password</strong>
      <div class="row q-mt-md q-col-gutter-md">
        <div class="col-12">
          <q-input
            v-model="apiAcl.password"
            type="password"
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
