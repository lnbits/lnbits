<template id="page-admin">
  <div class="row q-col-gutter-md q-mb-md">
    <div class="col-12">
      <q-card>
        <div class="q-pa-sm">
          <div class="row items-center justify-between q-gutter-xs">
            <div class="col">
              <q-btn
                :label="$t('save')"
                color="primary"
                @click="updateSettings"
                :disabled="!checkChanges"
              >
                <q-tooltip v-if="checkChanges">
                  <span v-text="$t('save_tooltip')"></span>
                </q-tooltip>

                <q-badge
                  v-if="checkChanges"
                  color="red"
                  rounded
                  floating
                  style="padding: 6px; border-radius: 6px"
                />
              </q-btn>

              <q-btn
                v-if="isSuperUser"
                :label="$t('restart')"
                color="primary"
                @click="restartServer"
                class="q-ml-md"
              >
                <q-tooltip v-if="needsRestart">
                  <span v-text="$t('restart_tooltip')"></span>
                </q-tooltip>

                <q-badge
                  v-if="needsRestart"
                  color="red"
                  rounded
                  floating
                  style="padding: 6px; border-radius: 6px"
                />
              </q-btn>

              <q-btn
                :label="$t('download_backup')"
                flat
                @click="downloadBackup"
              ></q-btn>

              <q-btn
                flat
                v-if="isSuperUser"
                :label="$t('reset_defaults')"
                color="primary"
                @click="deleteSettings"
                class="float-right"
              >
                <q-tooltip>
                  <span v-text="$t('reset_defaults_tooltip')"></span>
                </q-tooltip>
              </q-btn>
            </div>
            <div></div>
          </div>
        </div>
      </q-card>
    </div>
  </div>

  <div class="row q-col-gutter-md justify-center">
    <div class="col q-gutter-y-md">
      <q-card>
        <!-- Mobile: Dropdown menu at top -->
        <div v-if="$q.screen.lt.md" class="q-px-md q-pt-md">
          <q-select
            v-model="tab"
            :options="[
              {value: 'funding', label: $t('funding')},
              {value: 'security', label: $t('security')},
              {value: 'server', label: $t('payments')},
              {value: 'exchange_providers', label: $t('exchanges')},
              {value: 'fiat_providers', label: $t('fiat_providers')},
              {value: 'users', label: $t('users')},
              {value: 'extensions', label: $t('extensions')},
              {value: 'notifications', label: $t('notifications')},
              {value: 'audit', label: $t('audit')},
              {value: 'library', label: $t('Library')},
              {value: 'site_customisation', label: $t('site_customisation')}
            ]"
            option-value="value"
            option-label="label"
            emit-value
            map-options
            filled
            dense
          >
          </q-select>
        </div>

        <q-splitter>
          <template v-slot:before>
            <q-tabs v-model="tab" vertical active-color="primary">
              <q-tab
                name="funding"
                icon="account_balance_wallet"
                :label="$q.screen.gt.sm ? $t('funding') : null"
                @update="val => (tab = val.name)"
                ><q-tooltip v-if="!$q.screen.gt.sm"
                  ><span v-text="$t('funding')"></span></q-tooltip
              ></q-tab>
              <q-tab
                name="security"
                icon="security"
                :label="$q.screen.gt.sm ? $t('security') : null"
                @update="val => (tab = val.name)"
                ><q-tooltip v-if="!$q.screen.gt.sm"
                  ><span v-text="$t('security')"></span></q-tooltip
              ></q-tab>
              <q-tab
                name="server"
                icon="price_change"
                :label="$q.screen.gt.sm ? $t('payments') : null"
                @update="val => (tab = val.name)"
                ><q-tooltip v-if="!$q.screen.gt.sm"
                  ><span v-text="$t('payments')"></span></q-tooltip
              ></q-tab>
              <q-tab
                name="exchange_providers"
                icon="show_chart"
                :label="$q.screen.gt.sm ? $t('exchanges') : null"
                ><q-tooltip v-if="!$q.screen.gt.sm"
                  ><span v-text="$t('exchanges')"></span></q-tooltip
              ></q-tab>
              <q-tab
                name="fiat_providers"
                icon="credit_score"
                :label="$q.screen.gt.sm ? $t('fiat_providers') : null"
                ><q-tooltip v-if="!$q.screen.gt.sm"
                  ><span v-text="$t('fiat_providers')"></span></q-tooltip
              ></q-tab>
              <q-tab
                name="users"
                icon="group"
                :label="$q.screen.gt.sm ? $t('users') : null"
                @update="val => (tab = val.name)"
                ><q-tooltip v-if="!$q.screen.gt.sm"
                  ><span v-text="$t('users')"></span></q-tooltip
              ></q-tab>

              <q-tab
                name="extensions"
                icon="extension"
                :label="$q.screen.gt.sm ? $t('extensions') : null"
                @update="val => (tab = val.name)"
                ><q-tooltip v-if="!$q.screen.gt.sm"
                  ><span v-text="$t('extensions')"></span></q-tooltip
              ></q-tab>

              <q-tab
                name="notifications"
                icon="notifications"
                :label="$q.screen.gt.sm ? $t('notifications') : null"
                @update="val => (tab = val.name)"
                ><q-tooltip v-if="!$q.screen.gt.sm"
                  ><span v-text="$t('notifications')"></span></q-tooltip
              ></q-tab>
              <q-tab
                name="audit"
                icon="playlist_add_check_circle"
                :label="$q.screen.gt.sm ? $t('audit') : null"
                @update="val => (tab = val.name)"
                ><q-tooltip v-if="!$q.screen.gt.sm"
                  ><span v-text="$t('audit')"></span></q-tooltip
              ></q-tab>
              <q-tab
                name="library"
                icon="image"
                :label="$q.screen.gt.sm ? $t('library') : null"
                @update="val => (tab = val.name)"
                ><q-tooltip v-if="!$q.screen.gt.sm"
                  ><span v-text="$t('library')"></span></q-tooltip
              ></q-tab>
              <q-tab
                style="word-break: break-all"
                name="site_customisation"
                icon="language"
                :label="$q.screen.gt.sm ? $t('site_customisation') : null"
                @update="val => (tab = val.name)"
                ><q-tooltip v-if="!$q.screen.gt.sm"
                  ><span v-text="$t('site_customisation')"></span></q-tooltip
              ></q-tab>
            </q-tabs>
          </template>

          <template v-slot:after>
            <q-form name="settings_form" id="settings_form">
              <q-scroll-area style="height: 100vh">
                <q-tab-panels
                  v-model="tab"
                  animated
                  vertical
                  scroll
                  transition-prev="jump-up"
                  transition-next="jump-up"
                >
                  <q-tab-panel name="funding">
                    <lnbits-admin-funding
                      :is-super-user="isSuperUser"
                      :settings="settings"
                      :form-data="formData"
                    ></lnbits-admin-funding>
                  </q-tab-panel>
                  <q-tab-panel name="fiat_providers">
                    <lnbits-admin-fiat-providers :form-data="formData" />
                  </q-tab-panel>
                  <q-tab-panel name="users">
                    <lnbits-admin-users :form-data="formData" />
                  </q-tab-panel>
                  <q-tab-panel name="server">
                    <lnbits-admin-server :form-data="formData" />
                  </q-tab-panel>
                  <q-tab-panel name="exchange_providers">
                    <lnbits-admin-exchange-providers :form-data="formData" />
                  </q-tab-panel>
                  <q-tab-panel name="extensions">
                    <lnbits-admin-extensions :form-data="formData" />
                  </q-tab-panel>
                  <q-tab-panel name="notifications">
                    <lnbits-admin-notifications :form-data="formData" />
                  </q-tab-panel>
                  <q-tab-panel name="security">
                    <lnbits-admin-security :form-data="formData" />
                  </q-tab-panel>
                  <q-tab-panel name="site_customisation">
                    <lnbits-admin-site-customisation :form-data="formData" />
                  </q-tab-panel>
                  <q-tab-panel name="audit">
                    <lnbits-admin-audit :form-data="formData" />
                  </q-tab-panel>
                  <q-tab-panel name="library">
                    <lnbits-admin-library :form-data="formData" />
                  </q-tab-panel>
                </q-tab-panels>
              </q-scroll-area>
            </q-form>
          </template>
        </q-splitter>
      </q-card>
    </div>
  </div>
</template>
