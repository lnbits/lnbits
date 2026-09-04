<template id="page-admin">
  <div>
    <q-card flat bordered class="q-mb-md">
      <q-card-section class="row items-center q-col-gutter-md">
        <div class="col-12 col-md">
          <h1 class="text-h6 q-my-none" v-text="$t('admin_settings')"></h1>
          <div
            class="text-caption text-grey"
            v-text="$t('admin_settings_description')"
          ></div>
        </div>
        <div class="col-12 col-md-5">
          <q-input
            v-model.trim="settingsSearch"
            outlined
            dense
            clearable
            debounce="100"
            :placeholder="$t('search_settings')"
            aria-label="Search settings"
          >
            <template v-slot:prepend><q-icon name="search"></q-icon></template>
            <q-menu
              v-if="settingsSearch"
              :model-value="Boolean(settingsSearch)"
              fit
              no-focus
              no-parent-event
            >
              <q-list separator>
                <q-item
                  v-for="result in filteredSettingsSearch"
                  :key="`${result.tab}-${result.section}`"
                  clickable
                  v-close-popup
                  @click="selectSettingsSearchResult(result)"
                >
                  <q-item-section avatar>
                    <q-icon :name="result.icon" color="primary"></q-icon>
                  </q-item-section>
                  <q-item-section>
                    <q-item-label v-text="result.section"></q-item-label>
                    <q-item-label
                      caption
                      v-text="result.category"
                    ></q-item-label>
                  </q-item-section>
                </q-item>
                <q-item v-if="!filteredSettingsSearch.length">
                  <q-item-section
                    class="text-grey"
                    v-text="$t('no_settings_found')"
                  ></q-item-section>
                </q-item>
              </q-list>
            </q-menu>
          </q-input>
        </div>
        <div class="col-12 col-md-auto">
          <div class="row items-center q-gutter-sm">
            <q-icon
              :name="checkChanges ? 'edit' : 'check_circle'"
              :color="checkChanges ? 'warning' : 'positive'"
              size="18px"
            ></q-icon>
            <span
              class="text-caption"
              v-text="
                checkChanges ? $t('unsaved_changes') : $t('all_changes_saved')
              "
            ></span>
          </div>
        </div>
        <div class="col-12">
          <div class="row q-gutter-sm">
            <q-btn
              :label="$t('save')"
              color="primary"
              icon="save"
              unelevated
              @click="updateSettings"
              :loading="isSaving"
              :disabled="!checkChanges"
            ></q-btn>
            <q-btn
              v-if="isSuperUser"
              :label="$t('restart')"
              :color="needsRestart ? 'warning' : 'primary'"
              icon="restart_alt"
              outline
              @click="restartServer"
            >
              <q-tooltip v-if="needsRestart">
                <span v-text="$t('restart_tooltip')"></span>
              </q-tooltip>
            </q-btn>
            <q-space></q-space>
            <q-btn
              :label="$t('download_backup')"
              icon="download"
              flat
              @click="downloadBackup"
            ></q-btn>
            <q-btn
              v-if="isSuperUser"
              :label="$t('reset_defaults')"
              icon="restore"
              color="negative"
              flat
              @click="deleteSettings"
            >
              <q-tooltip>
                <span v-text="$t('reset_defaults_tooltip')"></span>
              </q-tooltip>
            </q-btn>
          </div>
        </div>
      </q-card-section>
    </q-card>

    <q-card flat bordered>
      <div
        v-if="
          $q.screen.lt.md &&
          !['wasm-runtime', 'wasm-limit-config'].includes(tab)
        "
        class="q-pa-md"
      >
        <q-select
          v-model="tab"
          :options="settingsNavigationItems"
          option-value="value"
          option-label="label"
          emit-value
          map-options
          outlined
          :label="$t('admin_settings')"
        >
          <template v-slot:prepend><q-icon name="tune"></q-icon></template>
        </q-select>
      </div>

      <div class="row items-stretch">
        <q-card-section v-if="$q.screen.gt.sm" class="col-md-2 q-pa-none">
          <nav class="q-py-md" aria-label="Settings categories">
            <div
              v-for="group in settingsNavigation"
              :key="group.label"
              class="q-mb-lg"
            >
              <div
                class="text-overline text-grey q-px-md"
                v-text="$t(group.label)"
              ></div>
              <q-list dense>
                <q-item
                  v-for="item in group.items"
                  :key="item.value"
                  clickable
                  v-ripple
                  class="q-py-xs"
                  :active="tab === item.value"
                  active-class="text-primary"
                  @click="tab = item.value"
                >
                  <q-item-section side>
                    <q-icon
                      :name="item.icon"
                      :color="tab === item.value ? 'primary' : undefined"
                      size="md"
                    ></q-icon>
                  </q-item-section>
                  <q-item-section>
                    <q-item-label
                      lines="1"
                      v-text="$t(item.label)"
                    ></q-item-label>
                  </q-item-section>
                </q-item>
              </q-list>
            </div>
          </nav>
        </q-card-section>

        <q-separator v-if="$q.screen.gt.sm" vertical></q-separator>

        <q-card-section class="col-12 col-md q-pa-none">
          <q-tab-panels
            v-model="tab"
            animated
            vertical
            transition-prev="jump-up"
            transition-next="jump-up"
            class="col-12"
          >
            <q-tab-panel name="funding" class="q-pa-md">
              <lnbits-admin-funding
                :active="tab === 'funding'"
                :is-super-user="isSuperUser"
                :settings="settings"
                :form-data="formData"
              ></lnbits-admin-funding>
            </q-tab-panel>
            <q-tab-panel name="fiat_providers" class="q-pa-md">
              <lnbits-admin-fiat-providers :form-data="formData" />
            </q-tab-panel>
            <q-tab-panel name="users" class="q-pa-md">
              <lnbits-admin-users :form-data="formData" />
            </q-tab-panel>
            <q-tab-panel name="server" class="q-pa-md">
              <lnbits-admin-server :form-data="formData" />
            </q-tab-panel>
            <q-tab-panel name="exchange_providers" class="q-pa-md">
              <lnbits-admin-exchange-providers :form-data="formData" />
            </q-tab-panel>
            <q-tab-panel name="extensions" class="q-pa-md">
              <lnbits-admin-extensions :form-data="formData" />
            </q-tab-panel>
            <q-tab-panel name="wasm-runtime" class="q-pa-md">
              <lnbits-admin-wasm-runtime :form-data="formData" />
            </q-tab-panel>
            <q-tab-panel name="wasm-limit-config" class="q-pa-md">
              <lnbits-admin-wasm-limit-config :form-data="formData" />
            </q-tab-panel>
            <q-tab-panel name="notifications" class="q-pa-md">
              <lnbits-admin-notifications :form-data="formData" />
            </q-tab-panel>
            <q-tab-panel name="security" class="q-pa-md">
              <lnbits-admin-security :form-data="formData" />
            </q-tab-panel>
            <q-tab-panel name="site_customisation" class="q-pa-md">
              <lnbits-admin-site-customisation :form-data="formData" />
            </q-tab-panel>
            <q-tab-panel name="audit" class="q-pa-md">
              <lnbits-admin-audit :form-data="formData" />
            </q-tab-panel>
            <q-tab-panel name="assets-config" class="q-pa-md">
              <lnbits-admin-assets-config :form-data="formData" />
            </q-tab-panel>
            <q-tab-panel name="blockexplorer" class="q-pa-md">
              <lnbits-admin-blockexplorer :form-data="formData" />
            </q-tab-panel>
          </q-tab-panels>
        </q-card-section>
      </div>
    </q-card>
  </div>
</template>
