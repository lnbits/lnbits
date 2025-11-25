<template id="page-extensions">
  <div class="row q-col-gutter-md q-mb-md">
    <div class="col-12">
      <q-card>
        <div>
          <div class="q-gutter-y-md">
            <q-tabs
              :model-value="tab"
              @update:model-value="handleTabChanged"
              active-color="primary"
              align="left"
            >
              <q-tab name="installed" :label="$t('installed')"></q-tab>
              <q-tab name="all" :label="$t('all')"></q-tab>
              <q-tab name="featured" :label="$t('featured')"></q-tab>
              <i
                v-if="!g.user.admin && tab != 'installed'"
                v-text="$t('only_admins_can_install')"
              ></i>
              <q-space></q-space>

              <q-input
                :label="$t('search_extensions')"
                :dense="dense"
                class="float-right q-pr-xl"
                v-model="searchTerm"
              >
                <template v-slot:before>
                  <q-icon name="search"> </q-icon>
                </template>
                <template v-slot:append>
                  <q-icon
                    v-if="searchTerm !== ''"
                    name="close"
                    @click="searchTerm = ''"
                    class="cursor-pointer"
                  >
                  </q-icon>
                </template>
              </q-input>
              <q-badge
                v-if="g.user.admin && updatableExtensions?.length"
                @click="showUpdateAllDialog = true"
                color="primary"
                class="float-right q-pa-sm q-mr-md cursor-pointer"
              >
                <span
                  v-text="
                    $t('new_version') + ` (${updatableExtensions?.length})`
                  "
                ></span>
              </q-badge>
              <q-btn
                v-if="extbuilderEnabled"
                flat
                no-caps
                icon="architecture"
                to="/extensions/builder"
                ><span v-text="$t('create_extension')"></span
              ></q-btn>
              <q-btn v-else disabled flat no-caps icon="architecture"
                ><span v-text="$t('create_extension')"></span>
                <q-tooltip
                  v-text="$t('only_admins_can_create_extensions')"
                ></q-tooltip>
              </q-btn>
              <q-btn
                v-if="g.user.admin"
                flat
                round
                icon="settings"
                to="/admin#extensions"
                ><q-tooltip v-text="$t('admin_settings')"></q-tooltip
              ></q-btn>
            </q-tabs>
          </div>
        </div>
      </q-card>
    </div>
  </div>
  <div class="row q-col-gutter-md">
    <div
      v-if="filteredExtensions"
      class="col-12 col-sm-6 col-md-6 col-lg-4"
      v-for="extension in filteredExtensions"
      :key="extension.id + extension.hash"
    >
      <q-card>
        <q-card-section>
          <div class="row">
            <div class="col-3">
              <q-img
                @click="
                  showExtensionDetails(extension.id, extension.details_link)
                "
                v-if="extension.icon"
                :src="extension.icon"
                spinner-color="white"
                style="cursor: pointer; max-width: 100%"
              >
                <q-tooltip>
                  <span v-text="extension.shortDescription"></span>
                </q-tooltip>
              </q-img>
              <div v-else>
                <q-icon
                  class="gt-sm"
                  name="extension"
                  color="primary"
                  size="70px"
                ></q-icon>
                <q-icon
                  class="lt-md"
                  name="extension"
                  color="primary"
                  size="35px"
                ></q-icon>
              </div>
            </div>
            <div class="col-9 q-pl-md">
              <q-badge
                v-if="extension.isInstalled"
                @click="showManageExtension(extension)"
                class="float-right"
                color="transparent"
                style="cursor: pointer"
              >
                <span v-text="extension.installedRelease.version"></span>
                <q-tooltip
                  ><span v-text="extension.installedRelease.version"></span
                ></q-tooltip>
              </q-badge>
              <div
                v-if="extension.name"
                class="text-h5"
                style="cursor: pointer"
                @click="
                  showExtensionDetails(extension.id, extension.details_link)
                "
                v-text="extension.name"
              ></div>
              <div style="justify-content: space-between; display: flex">
                <lnbits-extension-rating :rating="0" />
                <q-btn-group size="xs" style="margin: 5px 0">
                  <q-btn
                    v-if="extension.hasFreeRelease"
                    color="green"
                    size="xs"
                    :label="$t('free')"
                  >
                    <q-tooltip>
                      <span v-text="$t('extension_has_free_release')"></span>
                    </q-tooltip>
                  </q-btn>
                  <q-btn
                    v-if="extension.hasPaidRelease || extension.paidFeatures"
                    color="primary"
                    size="xs"
                    :label="$t('paid')"
                  >
                    <q-tooltip>
                      <span
                        v-if="extension.hasPaidRelease"
                        v-text="$t('extension_has_paid_release')"
                      ></span>
                      <br
                        v-if="
                          extension.hasPaidRelease && extension.paidFeatures
                        "
                      />
                      <span
                        v-if="extension.paidFeatures"
                        v-text="extension.paidFeatures"
                      ></span>
                    </q-tooltip>
                  </q-btn>
                </q-btn-group>
              </div>
              <div style="justify-content: space-between; display: flex">
                <q-toggle
                  size="xs"
                  v-if="
                    extension.isAvailable &&
                    extension.isInstalled &&
                    g.user.admin
                  "
                  :label="
                    extension.isActive ? $t('activated') : $t('deactivated')
                  "
                  color="secondary"
                  v-model="extension.isActive"
                  @update:model-value="toggleExtension(extension)"
                  ><q-tooltip>
                    &nbsp;
                    <span
                      v-text="$t('activate_extension_details')"
                    ></span> </q-tooltip
                ></q-toggle>
                <q-badge
                  v-if="hasNewVersion(extension)"
                  @click="showManageExtension(extension)"
                  color="primary"
                  class="float-right"
                  style="cursor: pointer; margin: 5px 0"
                >
                  <span v-text="$t('new_version')"></span>
                  <q-tooltip
                    ><span v-text="extension.latestRelease.version"></span
                  ></q-tooltip>
                </q-badge>
              </div>
              <div>
                <p
                  style="
                    overflow: hidden;
                    white-space: nowrap;
                    text-overflow: ellipsis;
                  "
                  v-text="extension.shortDescription"
                ></p>
                <q-tooltip
                  ><span v-text="extension.shortDescription"></span
                ></q-tooltip>
              </div>
            </div>
          </div>
          <div
            id="dependencies"
            class="row q-pt-sm"
            v-if="extension.dependencies?.length"
          >
            <div class="col">
              <small v-text="$t('extension_depends_on')"></small>
              <q-badge
                v-for="dep in extension.dependencies"
                :key="dep"
                color="orange"
              >
                <small v-text="dep"></small>
              </q-badge>
            </div>
          </div>
        </q-card-section>
        <q-separator></q-separator>
        <q-card-actions style="min-height: 52px">
          <div class="col-10">
            <div v-if="!extension.inProgress">
              <q-btn
                v-if="
                  g.user.extensions.includes(extension.id) &&
                  extension.isActive &&
                  extension.isInstalled
                "
                flat
                color="primary"
                type="a"
                :href="extension.id + '/'"
                :label="$t('open')"
              ></q-btn>
              <q-btn
                v-if="
                  g.user.extensions.includes(extension.id) &&
                  extension.isActive &&
                  extension.isInstalled
                "
                flat
                color="grey-5"
                @click="disableExtension(extension)"
                :label="$t('disable')"
              ></q-btn>
              <q-badge
                v-if="extension.isAdminOnly && !g.user.admin"
                v-text="$t('admin_only')"
              >
              </q-badge>

              <q-btn
                v-else-if="
                  extension.isInstalled &&
                  extension.isActive &&
                  !g.user.extensions.includes(extension.id)
                "
                flat
                color="primary"
                @click="enableExtensionForUser(extension)"
                :label="
                  $t(extension.isPaymentRequired ? 'pay_to_enable' : 'enable')
                "
              >
                <q-tooltip>
                  <span v-text="$t('enable_extension_details')">
                  </span> </q-tooltip
              ></q-btn>

              <q-btn
                @click="showManageExtension(extension)"
                flat
                color="primary"
                v-if="g.user.admin"
                :label="$t('manage')"
                ><q-tooltip
                  ><span v-text="$t('manage_extension_details')"></span
                ></q-tooltip>
              </q-btn>
            </div>
            <div v-else>
              <q-spinner-bars color="primary" size="2.55em"></q-spinner-bars>
            </div>
          </div>

          <div class="col-2">
            <div v-if="extension.details_link" class="float-right">
              <q-btn
                @click="
                  showExtensionDetails(extension.id, extension.details_link)
                "
                flat
                :label="$t('more')"
              >
                <q-tooltip>
                  <span v-text="extension.shortDescription"></span>
                </q-tooltip>
              </q-btn>
            </div>
          </div>
        </q-card-actions>
      </q-card>
    </div>
  </div>

  <q-dialog v-model="showUninstallDialog" position="top">
    <q-card class="q-pa-lg">
      <h6 class="q-my-md text-primary" v-text="$t('warning')"></h6>
      <p>
        <span v-text="$t('extension_uninstall_warning')"></span><br />
        <span v-text="$t('confirm_continue')"></span>
      </p>

      <div class="row q-mt-lg">
        <q-checkbox
          v-model="uninstallAndDropDb"
          value="false"
          label="Cleanup database tables"
        >
          <q-tooltip class="bg-grey-8" anchor="bottom left" self="top left"
            ><span v-text="$t('extension_db_drop_info')"></span>
          </q-tooltip>
        </q-checkbox>
      </div>
      <div class="row q-mt-lg">
        <q-btn
          outline
          color="grey"
          @click="uninstallExtension()"
          v-text="$t('uninstall_confirm')"
        ></q-btn>
        <q-btn
          v-close-popup
          flat
          color="grey"
          class="q-ml-auto"
          v-text="$t('cancel')"
        ></q-btn>
      </div>
    </q-card>
  </q-dialog>

  <q-dialog v-model="showDropDbDialog" position="top">
    <q-card v-if="selectedExtension" class="q-pa-lg">
      <h6 class="q-my-md text-primary" v-text="$t('warning')"></h6>
      <p><span v-text="$t('extension_db_drop_warning')"></span><br /></p>
      <q-input
        v-model="dropDbExtensionId"
        :label="selectedExtension.id"
      ></q-input>
      <br />
      <p v-text="$t('confirm_continue')"></p>

      <div class="row q-mt-lg">
        <q-btn
          :disable="dropDbExtensionId !== selectedExtension.id"
          outline
          color="red"
          @click="dropExtensionDb()"
          v-text="$t('confirm')"
        ></q-btn>
        <q-btn
          v-close-popup
          flat
          color="grey"
          class="q-ml-auto"
          v-text="$t('cancel')"
        ></q-btn>
      </div>
    </q-card>
  </q-dialog>

  <q-dialog v-model="showManageExtensionDialog" position="top">
    <q-card v-if="selectedRelease" class="q-pa-lg lnbits__dialog-card">
      <q-card-section>
        <div v-if="selectedRelease.paymentRequest">
          <lnbits-qrcode
            :value="'lightning:' + selectedRelease.paymentRequest.toUpperCase()"
            :href="'lightning:' + selectedRelease.paymentRequest"
          ></lnbits-qrcode>
        </div>
        <div v-else>
          <q-spinner-bars color="primary" size="2.55em"></q-spinner-bars>
        </div>
      </q-card-section>

      <div class="row q-mt-lg">
        <div class="col">
          <q-btn
            v-if="selectedRelease.paymentRequest"
            outline
            color="grey"
            @click="utils.copyText(selectedRelease.paymentRequest)"
            :label="$t('copy_invoice')"
          ></q-btn>
        </div>
        <div class="col">
          <q-btn
            v-close-popup
            flat
            color="grey"
            class="float-right q-ml-lg"
            v-text="$t('close')"
          ></q-btn>
        </div>
      </div>
    </q-card>
    <q-card v-else class="q-pa-lg lnbits__dialog-card">
      <q-tabs
        v-model="manageExtensionTab"
        active-color="primary"
        align="justify"
      >
        <q-tab
          name="releases"
          :label="$t('releases')"
          @update="val => (manageExtensionTab = val.name)"
        ></q-tab>

        <q-tab
          v-if="selectedExtension && selectedExtension.isInstalled"
          name="sell"
          :label="$t('sell')"
          @update="val => (manageExtensionTab = val.name)"
        ></q-tab>
      </q-tabs>

      <div
        v-show="manageExtensionTab === 'releases'"
        class="col-12 col-md-5 q-gutter-y-md q-mt-md"
        v-if="selectedExtensionRepos"
      >
        <q-card
          flat
          bordered
          class="my-card"
          v-for="repoName of Object.keys(selectedExtensionRepos)"
          :key="repoName"
        >
          <q-expansion-item
            :key="repoName"
            group="repos"
            :caption="repoName"
            :content-inset-level="0.5"
            :default-opened="selectedExtensionRepos[repoName].isInstalled"
          >
            <template v-slot:header>
              <q-item-section avatar>
                <q-avatar
                  :icon="
                    selectedExtensionRepos[repoName].isInstalled
                      ? 'download_done'
                      : 'download'
                  "
                  :text-color="
                    selectedExtensionRepos[repoName].isInstalled ? 'green' : ''
                  "
                />
              </q-item-section>

              <q-item-section>
                <div class="row">
                  <div class="col-10">
                    <span v-text="$t('repository')"></span>
                    <br />
                    <small v-text="repoName"></small>
                    <q-tooltip
                      ><span
                        v-text="selectedExtensionRepos[repoName].repo"
                      ></span
                    ></q-tooltip>
                  </div>
                  <div class="col-2"></div>
                </div>
              </q-item-section>
            </template>

            <q-card-section class="q-pa-none">
              <q-separator></q-separator>

              <q-list>
                <q-expansion-item
                  v-for="release of selectedExtensionRepos[repoName].releases"
                  :key="release.version"
                  group="releases"
                  @click="getGitHubReleaseDetails(release)"
                  :icon="getReleaseIcon(release)"
                  :label="release.description"
                  :caption="release.version"
                  :content-inset-level="0.5"
                  :header-class="getReleaseIconColor(release)"
                >
                  <div v-if="release.inProgress">
                    <q-spinner-bars
                      color="primary"
                      size="2.55em"
                    ></q-spinner-bars>
                  </div>
                  <div v-else-if="release.error">
                    <q-icon
                      class="gt-sm"
                      name="error"
                      color="pink"
                      size="70px"
                    ></q-icon>
                    <span v-text="$t('release_details_error')"></span>
                  </div>
                  <q-card class="no-border" v-else>
                    <q-card-section v-if="release.is_version_compatible">
                      <span
                        v-if="release.requiresPayment && !release.paid_sats"
                        v-text="$t('extension_cost', {cost: release.cost_sats})"
                        class="q-mb-lg"
                      ></span>
                      <span
                        v-if="release.requiresPayment && release.paid_sats"
                        class="q-mb-lg"
                        v-text="
                          $t('extension_paid_sats', {
                            paid_sats: release.paid_sats
                          })
                        "
                      ></span>
                      <div
                        v-if="
                          !release.requiresPayment ||
                          (release.requiresPayment && release.paid_sats)
                        "
                      >
                        <q-btn
                          v-if="!release.isInstalled"
                          @click="installExtension(release)"
                          color="primary unelevated mt-lg pt-lg"
                          :label="$t('install')"
                        ></q-btn>
                      </div>

                      <div v-if="release.requiresPayment && !release.paid_sats">
                        <div v-if="!release.payment_hash">
                          <q-input
                            filled
                            dense
                            v-model.number="release.paidAmount"
                            type="number"
                            :min="release.cost_sats"
                            suffix="sat"
                            class="q-mt-sm"
                          >
                          </q-input>
                          <q-select
                            filled
                            dense
                            emit-value
                            map-options
                            v-model="release.wallet"
                            :options="g.user.walletOptions"
                            :label="$t('wallet_required')"
                            class="q-mt-sm"
                          >
                          </q-select>
                          <q-btn
                            unelevated
                            color="primary"
                            @click="payAndInstall(release)"
                            :disabled="!release.wallet"
                            class="q-mt-sm"
                            :label="$t('pay_from_wallet')"
                          ></q-btn>

                          <q-btn
                            unelevated
                            color="primary"
                            @click="showInstallQRCode(release)"
                            class="q-mt-sm float-right"
                            :label="$t('show_qr')"
                          ></q-btn>
                        </div>
                        <div v-else>
                          <br />
                          <span
                            class="q-mb-lg q-mt-lg"
                            v-text="
                              'There is a previous pending invoice for this release.'
                            "
                          ></span>
                          <br />
                          <q-btn
                            unelevated
                            @click="installExtension(release)"
                            color="primary"
                            class="q-mt-sm"
                            :label="$t('retry_install')"
                          ></q-btn>
                          <q-btn
                            unelevated
                            @click="clearHangingInvoice(release)"
                            color="primary"
                            class="q-mt-sm float-right"
                            :label="$t('new_payment')"
                          ></q-btn>
                        </div>
                      </div>

                      <div>
                        <q-btn
                          v-if="release.isInstalled"
                          @click="showUninstall()"
                          :label="$t('uninstall')"
                          flat
                          color="red"
                        ></q-btn>
                      </div>

                      <a
                        v-if="release.html_url"
                        class="text-secondary float-right"
                        :href="release.html_url"
                        target="_blank"
                        rel="noopener noreferrer"
                        style="color: inherit"
                        v-text="$t('release_notes')"
                      ></a>
                    </q-card-section>
                    <q-card-section v-else>
                      <span
                        v-text="$t('extension_required_lnbits_version')"
                      ></span>
                      <span class="q-mr-sm">:</span>
                      <ul>
                        <li v-if="release.min_lnbits_version">
                          <span v-text="$t('min_version')"></span>
                          <span class="q-mr-sm">:</span>
                          <strong>
                            <span v-text="release.min_lnbits_version"></span>
                          </strong>
                        </li>
                        <li v-if="release.max_lnbits_version">
                          <span v-text="$t('max_version')"></span>
                          <span class="q-mr-sm">:</span>
                          <strong>
                            <span v-text="release.max_lnbits_version"></span>
                          </strong>
                        </li>
                      </ul>
                    </q-card-section>
                    <q-card v-if="release.warning">
                      <q-card-section>
                        <div class="text-h6">
                          <q-badge
                            color="yellow"
                            text-color="black"
                            v-text="$t('warning')"
                          >
                          </q-badge>
                        </div>
                        <div class="text-subtitle2">
                          <span v-text="release.warning"></span>
                        </div>
                      </q-card-section>
                    </q-card>

                    <q-separator></q-separator> </q-card
                ></q-expansion-item>
              </q-list>
            </q-card-section>
          </q-expansion-item>
        </q-card>
        <div class="row q-mt-lg">
          <q-btn
            v-if="selectedExtension?.isInstalled"
            @click="showUninstall()"
            flat
            color="red"
            v-text="$t('uninstall')"
          ></q-btn>
          <q-btn
            v-else-if="selectedExtension?.hasDatabaseTables"
            @click="showDropDb()"
            flat
            color="red"
            :label="$t('drop_db')"
          ></q-btn>
          <q-btn
            v-close-popup
            flat
            color="grey"
            class="q-ml-auto"
            v-text="$t('close')"
          ></q-btn>
        </div>
      </div>
      <q-spinner-bars v-else color="primary" size="2.55em"></q-spinner-bars>
      <div
        v-if="selectedExtension"
        v-show="manageExtensionTab === 'sell'"
        class="col-12 col-md-5 q-gutter-y-md q-mt-md"
      >
        <q-toggle
          v-model="selectedExtension.payToEnable.required"
          :label="$t('sell_require')"
          color="secondary"
          style="max-height: 21px"
        ></q-toggle>
        <q-select
          v-if="selectedExtension.payToEnable.required"
          filled
          dense
          emit-value
          map-options
          v-model="selectedExtension.payToEnable.wallet"
          :options="g.user.walletOptions"
          label="Wallet *"
          class="q-mt-md"
        ></q-select>
        <q-input
          v-if="selectedExtension.payToEnable.required"
          filled
          dense
          v-model.number="selectedExtension.payToEnable.amount"
          :label="$t('amount_sats')"
          type="number"
          min="1"
          class="q-mt-md"
        >
        </q-input>
        <div class="row q-mt-lg">
          <q-btn
            @click="updatePayToInstallData(selectedExtension)"
            flat
            color="green"
            v-text="$t('update_payment')"
          ></q-btn>

          <q-btn
            v-close-popup
            flat
            color="grey"
            class="q-ml-auto"
            v-text="$t('close')"
          ></q-btn>
        </div>
      </div>
    </q-card>
  </q-dialog>

  <q-dialog v-model="showPayToEnableDialog" position="top">
    <q-card v-if="selectedExtension" class="q-pa-md">
      <q-card-section>
        <p>
          <span
            v-text="
              $t('sell_info', {
                name: selectedExtension.name,
                amount: selectedExtension.payToEnable.amount
              })
            "
          ></span>
        </p>
        <p>
          <span v-text="$t('already_paid_question')"></span>
          <q-badge
            @click="enableExtension(selectedExtension)"
            color="primary"
            class="cursor-pointer"
            rounded
          >
            <strong> <span v-text="$t('recheck')"></span> </strong
          ></q-badge>
        </p>
      </q-card-section>
      <q-card-section v-if="selectedExtension.payToEnable.showQRCode">
        <div class="row q-mt-lg">
          <div v-if="selectedExtension.payToEnable.paymentRequest" class="col">
            <lnbits-qrcode
              :value="
                'lightning:' +
                selectedExtension.payToEnable.paymentRequest.toUpperCase()
              "
              :href="
                'lightning:' + selectedExtension.payToEnable.paymentRequest
              "
            ></lnbits-qrcode>
          </div>
          <div v-else class="col">
            <q-spinner-bars color="primary" size="2.55em"></q-spinner-bars>
          </div>
        </div>
        <div class="row q-mt-lg">
          <div class="col">
            <q-btn
              v-if="selectedExtension.payToEnable.paymentRequest"
              outline
              color="grey"
              @click="
                utils.copyText(selectedExtension.payToEnable.paymentRequest)
              "
              :label="$t('copy_invoice')"
            ></q-btn>
          </div>
          <div class="col">
            <q-btn
              v-close-popup
              flat
              color="grey"
              class="float-right q-ml-lg"
              v-text="$t('close')"
            ></q-btn>
          </div>
        </div>
      </q-card-section>

      <q-card-section v-else>
        <div class="row q-mt-lg">
          <div class="col">
            <div>
              <q-input
                filled
                dense
                type="number"
                v-model.number="selectedExtension.payToEnable.paidAmount"
                :min="selectedExtension.payToEnable.amount"
                suffix="sat"
                class="q-mt-sm"
              >
              </q-input>
              <q-select
                filled
                dense
                v-model="selectedExtension.payToEnable.paymentWallet"
                emit-value
                map-options
                :options="g.user.walletOptions"
                :label="$t('wallet_required')"
                class="q-mt-sm"
              >
              </q-select>
              <q-separator class="q-mb-lg"></q-separator>
              <q-btn
                unelevated
                color="primary"
                class="q-mt-sm"
                @click="payAndEnable(selectedExtension)"
                :disabled="!selectedExtension.payToEnable.paymentWallet"
                :label="$t('pay_from_wallet')"
              ></q-btn>

              <q-btn
                unelevated
                @click="showEnableQRCode(selectedExtension)"
                color="primary"
                class="q-mt-sm float-right"
                :label="$t('show_qr')"
              ></q-btn>
            </div>
          </div>
        </div>
      </q-card-section>
    </q-card>
  </q-dialog>

  <q-dialog v-model="showExtensionDetailsDialog" position="top">
    <q-card
      v-if="selectedExtensionDetails"
      class="q-pa-sm"
      style="width: 800px; max-width: 95vw"
    >
      <q-card-section>
        <div class="row">
          <div class="col-2 gt-md">
            <q-img
              :src="selectedExtensionDetails.icon"
              style="width: 100px"
              type="image"
            ></q-img>
          </div>
          <div class="col-9 q-pl-md gt-xs">
            <h3 class="q-my-sm" v-text="selectedExtensionDetails.name"></h3>
            <h6
              class="q-my-sm"
              v-text="selectedExtensionDetails.short_description"
            ></h6>
          </div>
          <div class="col-9 q-pl-md lt-sm">
            <h5 class="q-my-sm" v-text="selectedExtensionDetails.name"></h5>
            <p
              class="q-my-sm"
              v-text="selectedExtensionDetails.short_description"
            ></p>
          </div>
          <div class="col-1">
            <q-btn
              v-close-popup
              flat
              color="grey"
              class="float-right q-ml-lg"
              v-text="$t('close')"
            ></q-btn>
          </div>
        </div>
        <div v-if="selectedExtensionDetails.images?.length" class="row q-my-lg">
          <div class="col q-pr-md">
            <q-carousel
              navigation-position="top"
              swipeable
              animated
              v-model="slide"
              v-model:fullscreen="fullscreen"
              thumbnails
              infinite
              :autoplay="autoplay"
              arrows
              transition-prev="slide-right"
              transition-next="slide-left"
              @mouseenter="autoplay = false"
              @mouseleave="autoplay = true"
              height="300px"
            >
              <template v-slot:control>
                <q-carousel-control position="bottom-right" :offset="[18, 18]">
                  <q-btn
                    push
                    round
                    dense
                    color="white"
                    text-color="primary"
                    :icon="fullscreen ? 'fullscreen_exit' : 'fullscreen'"
                    @click="fullscreen = !fullscreen"
                  ></q-btn>
                </q-carousel-control>
              </template>
              <q-carousel-slide
                v-for="(image, i) of selectedExtensionDetails.images"
                :img-src="image.uri"
                :key="i"
                :name="i"
              >
                <q-video
                  v-if="image.link"
                  class="absolute-full"
                  :src="image.link"
                />
              </q-carousel-slide>
            </q-carousel>
          </div>
        </div>

        <div class="row">
          <div class="col-sm-12 col-md-8 q-pr-sm">
            <div v-html="selectedExtensionDetails.description_md"></div>
          </div>
          <div class="col-sm-12 col-md-4 q-pl-sm">
            <lnbits-extension-rating
              :rating="0"
              size="2.5em"
            ></lnbits-extension-rating>
            <div class="q-mt-md">
              <b>
                <span v-text="$t('contributors')"></span>
              </b>
              <small>
                <div
                  v-for="contributor of selectedExtensionDetails.contributors"
                >
                  <a
                    :href="contributor.uri"
                    target="_blank"
                    rel="noopener noreferrer"
                    style="color: var(--q-primary); text-decoration: none"
                  >
                    <span
                      v-text="
                        (contributor.name || contributor) +
                        ' - ' +
                        (contributor.role || 'dev')
                      "
                    ></span>
                  </a>
                </div>
              </small>
            </div>
            <div class="q-pt-md">
              <div>
                <q-btn
                  size="sm"
                  color="primary"
                  label="Repo"
                  type="a"
                  :href="selectedExtensionDetails.repo"
                  target="_blank"
                  rel="noopener noreferrer"
                  ><q-tooltip>repository</q-tooltip></q-btn
                >
              </div>
              <div class="q-pt-lg">
                <div>
                  <b>
                    <span v-text="$t('license')"></span>
                  </b>
                  <q-badge
                    color="primary"
                    v-text="selectedExtensionDetails.license"
                  ></q-badge>
                </div>
                <br />
              </div>
            </div>
          </div>
        </div>
      </q-card-section>
    </q-card>
  </q-dialog>
  <q-dialog v-model="showUpdateAllDialog" position="top">
    <q-card class="q-pa-md q-pt-md lnbits__dialog-card">
      <div class="row">
        <div class="col-12">
          <h6 class="q-my-md" v-text="$t('update')"></h6>
        </div>
      </div>
      <div v-if="updatableExtensions?.length > 1" class="row">
        <div class="col-12">
          <q-btn
            outline
            color="grey"
            @click="selectAllUpdatableExtensionss()"
            v-text="$t('select_all')"
          ></q-btn>
        </div>
      </div>

      <q-virtual-scroll :items="updatableExtensions" style="max-height: 400px">
        <template v-slot="{item, index}">
          <div class="row">
            <div class="q-col">
              <q-checkbox
                v-model="item.selectedForUpdate"
                :disable="item.isUpgraded"
                value="false"
                :label="item.name + ` (v${item.latestRelease?.version})`"
              >
                <q-spinner-bars
                  v-if="item.inProgress"
                  color="primary"
                  size="1.5em"
                  class="q-ml-md"
                ></q-spinner-bars>
              </q-checkbox>
            </div>
          </div>
        </template>
      </q-virtual-scroll>
      <div class="row q-mt-lg">
        <q-btn
          @click="updateSelectedExtensions()"
          outline
          color="grey"
          v-text="$t('update')"
        ></q-btn>

        <q-btn
          v-close-popup
          flat
          color="grey"
          class="q-ml-auto"
          v-text="$t('cancel')"
        ></q-btn>
      </div>
    </q-card>
  </q-dialog>
</template>
