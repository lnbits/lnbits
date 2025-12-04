<template id="lnbits-admin-security">
  <q-card-section class="q-pa-none">
    <h6 class="q-my-none">
      <span v-text="$t('server_management')"></span>
    </h6>
    <div class="row">
      <div class="col-12 col-md-6">
        <p><span v-text="$t('base_url')"></span></p>
        <q-input
          filled
          v-model.number="formData.lnbits_baseurl"
          :label="$t('base_url_label')"
        ></q-input>
        <br />
      </div>
    </div>
    <h6 class="q-my-none q-mb-sm">
      <span v-text="$t('authentication')"></span>
    </h6>
    <div class="row q-col-gutter-sm">
      <div class="col-12 col-md-6">
        <q-input
          filled
          v-model="formData.auth_token_expire_minutes"
          type="number"
          :label="$t('auth_token_expiry_label')"
          :hint="$t('auth_token_expiry_hint')"
        >
        </q-input>
      </div>
      <div class="col-12 col-md-6">
        <q-input
          filled
          v-model="formData.auth_authentication_cache_minutes"
          type="number"
          :label="$t('auth_authentication_cache_label')"
          :hint="$t('auth_authentication_cache_hint')"
        >
        </q-input>
      </div>
      <div class="col-12 col-md-6">
        <q-select
          filled
          v-model="formData.auth_allowed_methods"
          multiple
          :hint="$t('auth_allowed_methods_hint')"
          :label="$t('auth_allowed_methods_label')"
          :options="formData.auth_all_methods"
          :option-label="
            option =>
              option.length > 25 ? option.substring(0, 22) + '...' : option
          "
        ></q-select>
      </div>
    </div>
  </q-card-section>
  <q-card-section
    v-if="formData.auth_allowed_methods?.includes('nostr-auth-nip98')"
    class="q-pl-xl"
  >
    <strong class="q-my-none q-mb-sm">Nostr Auth</strong>

    <div class="row">
      <div class="col-12">
        <q-input
          class="q-mb-sm"
          filled
          v-model="nostrAcceptedUrl"
          @keydown.enter="addNostrUrl"
          type="text"
          :label="$t('auth_nostr_label')"
          :hint="$t('auth_nostr_hint')"
        >
          <q-btn @click="addNostrUrl" dense flat icon="add"></q-btn>
        </q-input>
      </div>
      <div class="col-12">
        <q-chip
          v-for="url in formData.nostr_absolute_request_urls"
          :key="url"
          removable
          @remove="removeNostrUrl(url)"
          color="primary"
          text-color="white"
          :label="url"
          class="ellipsis"
        ></q-chip>
      </div>
    </div>
  </q-card-section>
  <q-card-section
    v-if="formData.auth_allowed_methods?.includes('google-auth')"
    class="q-pl-xl"
  >
    <strong class="q-my-none q-mb-sm">Google Auth</strong>

    <div class="row">
      <div class="col-12 col-md-6 q-pr-sm">
        <q-input
          filled
          v-model="formData.google_client_id"
          :label="$t('auth_google_ci_label')"
          :hint="$t('auth_google_ci_hint')"
        >
        </q-input>
      </div>
      <div class="col-12 col-md-6">
        <q-input
          filled
          v-model="formData.google_client_secret"
          type="password"
          :label="$t('auth_google_cs_label')"
        >
        </q-input>
      </div>
    </div>
  </q-card-section>
  <q-card-section
    v-if="formData.auth_allowed_methods?.includes('github-auth')"
    class="q-pl-xl"
  >
    <strong class="q-my-none q-mb-sm">GitHub Auth</strong>

    <div class="row">
      <div class="col-12 col-md-6 q-pr-sm">
        <q-input
          filled
          v-model="formData.github_client_id"
          :label="$t('auth_gh_client_id_label')"
          :hint="$t('auth_gh_client_id_hint')"
        >
        </q-input>
      </div>
      <div class="col-12 col-md-6">
        <q-input
          filled
          v-model="formData.github_client_secret"
          type="password"
          :label="$t('auth_gh_client_secret_label')"
        >
        </q-input>
      </div>
    </div>
  </q-card-section>
  <q-card-section
    v-if="formData.auth_allowed_methods?.includes('keycloak-auth')"
    class="q-pl-xl"
  >
    <strong class="q-my-none q-mb-sm">Keycloak Auth</strong>

    <div class="row q-col-gutter-sm q-col-gutter-y-md">
      <div class="col-12 col-md-4">
        <q-input
          filled
          v-model="formData.keycloak_discovery_url"
          :label="$t('auth_keycloak_label')"
        >
        </q-input>
      </div>
      <div class="col-12 col-md-4">
        <q-input
          filled
          v-model="formData.keycloak_client_id"
          :label="$t('auth_keycloak_ci_label')"
          :hint="$t('auth_keycloak_ci_hint')"
        >
        </q-input>
      </div>
      <div class="col-12 col-md-4">
        <q-input
          filled
          v-model="formData.keycloak_client_secret"
          type="password"
          :label="$t('auth_keycloak_cs_label')"
        >
        </q-input>
      </div>
      <div class="col-12 col-md-4">
        <q-input
          filled
          v-model="formData.keycloak_client_custom_org"
          :label="$t('auth_keycloak_custom_org_label')"
        >
        </q-input>
      </div>
      <div class="col-12 col-md-8">
        <q-input
          filled
          v-model="formData.keycloak_client_custom_icon"
          :label="$t('auth_keycloak_custom_icon_label')"
        >
        </q-input>
      </div>
    </div>
  </q-card-section>
  <q-separator></q-separator>
  <q-card-section class="q-pa-none">
    <br />
    <h6 class="q-my-none" v-text="$t('security_tools')"></h6>
    <div>
      <div class="row">
        <div v-if="serverlogEnabled" class="column" style="width: 100%">
          <div
            class="col bg-primary"
            style="padding-left: 5px; max-height: 20px; color: #fafafa"
            v-text="$t('server_logs')"
          ></div>
          <div class="col" style="background-color: #292929">
            <q-scroll-area
              ref="logScroll"
              style="padding: 10px; color: #fafafa; height: 320px"
            >
              <small v-for="log in logs"
                ><span v-text="log"></span><br
              /></small>
            </q-scroll-area>
          </div>
        </div>
        <q-btn
          @click="toggleServerLog"
          dense
          flat
          color="primary"
          :label="
            serverlogEnabled
              ? $t('disable_server_log')
              : $t('enable_server_log')
          "
        ></q-btn>
      </div>
      <br />
      <div class="row q-col-gutter-md">
        <div class="col-12 col-md-12">
          <p v-text="$t('ip_blocker')"></p>
          <div class="row q-col-gutter-md">
            <div class="col-12 col-md-6">
              <q-input
                filled
                v-model="formBlockedIPs"
                @keydown.enter="addBlockedIPs"
                type="text"
                :label="$t('enter_ip')"
                :hint="$t('block_access_hint')"
              >
                <q-btn
                  @click="addExtensionsManifest"
                  dense
                  flat
                  icon="add"
                ></q-btn>
              </q-input>
              <div>
                <q-chip
                  v-for="blocked_ip in formData.lnbits_blocked_ips"
                  :key="blocked_ip"
                  removable
                  @remove="removeBlockedIPs(blocked_ip)"
                  color="primary"
                  text-color="white"
                  :label="blocked_ip"
                  class="ellipsis"
                ></q-chip>
              </div>
              <br />
            </div>
            <div class="col-12 col-md-6">
              <q-input
                filled
                v-model="formAllowedIPs"
                @keydown.enter="addAllowedIPs"
                type="text"
                :label="$t('enter_ip')"
                :hint="$t('allow_access_hint')"
              >
                <q-btn
                  @click="addExtensionsManifest"
                  dense
                  flat
                  icon="add"
                ></q-btn>
              </q-input>
              <div>
                <q-chip
                  v-for="allowed_ip in formData.lnbits_allowed_ips"
                  :key="allowed_ip"
                  removable
                  @remove="removeAllowedIPs(allowed_ip)"
                  color="primary"
                  text-color="white"
                  :label="allowed_ip"
                  class="ellipsis"
                ></q-chip>
              </div>
              <br />
            </div>
          </div>
        </div>

        <div class="col-12 col-md-12">
          <p v-text="$t('rate_limiter')"></p>
          <div class="row q-col-gutter-md">
            <div class="col-12 col-md-6">
              <q-input
                filled
                type="number"
                v-model.number="formData.lnbits_rate_limit_no"
                :label="$t('number_of_requests')"
              ></q-input>
            </div>
            <div class="col-12 col-md-6">
              <q-select
                filled
                :options="[$t('second'), $t('minute'), $t('hour')]"
                v-model="formData.lnbits_rate_limit_unit"
                :label="$t('time_unit')"
              ></q-select>
            </div>
          </div>
        </div>

        <div class="col-12 col-md-12">
          <p v-text="$t('callback_url_rules')"></p>
          <div class="row q-col-gutter-md">
            <div class="col-12">
              <q-input
                filled
                v-model="formCallbackUrlRule"
                @keydown.enter="addCallbackUrlRule"
                type="text"
                :label="$t('enter_callback_url_rule')"
                :hint="$t('callback_url_rule_hint')"
              >
                <q-btn
                  @click="addCallbackUrlRule"
                  dense
                  flat
                  icon="add"
                ></q-btn>
              </q-input>
              <div>
                <q-chip
                  v-for="rule in formData.lnbits_callback_url_rules"
                  :key="rule"
                  removable
                  @remove="removeCallbackUrlRule(rule)"
                  color="primary"
                  text-color="white"
                  :label="rule"
                  class="ellipsis"
                ></q-chip>
              </div>
              <br />
            </div>
          </div>
        </div>
      </div>
    </div>
  </q-card-section>
</template>
