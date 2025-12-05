<template id="page-users">
  <div class="row q-col-gutter-md justify-center">
    <div class="col">
      <div v-if="paymentPage.show">
        <div class="row q-mb-lg">
          <div class="col">
            <q-btn
              icon="arrow_back_ios"
              @click="paymentPage.show = false"
              :label="$t('back')"
            ></q-btn>
          </div>
        </div>
        <q-card class="q-pa-md">
          <q-card-section>
            <lnbits-payment-list :wallet="paymentsWallet" />
          </q-card-section>
        </q-card>
      </div>
      <div v-else-if="activeWallet.show">
        <div class="row q-col-gutter-md q-mb-md">
          <div class="col-12">
            <q-card>
              <div class="q-pa-sm">
                <div class="row">
                  <div class="q-pa-xs">
                    <q-btn
                      icon="arrow_back_ios"
                      @click="backToUsersPage()"
                      :label="$t('back')"
                    ></q-btn>
                  </div>
                  <div class="q-pa-xs">
                    <q-btn
                      @click="createWalletDialog.show = true"
                      :label="$t('create_new_wallet')"
                      color="primary"
                    ></q-btn>
                  </div>
                  <div class="q-pa-xs">
                    <q-btn
                      @click="deleteAllUserWallets(activeWallet.userId)"
                      :label="$t('delete_all_wallets')"
                      icon="delete"
                      color="negative"
                    ></q-btn>
                  </div>
                </div>
              </div>
            </q-card>
          </div>
        </div>
        <q-card class="q-pa-md">
          <h2 class="text-h6 q-mb-md">Wallets</h2>
          <q-table :rows="wallets" :columns="walletTable.columns">
            <template v-slot:header="props">
              <q-tr :props="props">
                <q-th auto-width v-if="g.user.super_user"></q-th>
                <q-th auto-width></q-th>
                <q-th
                  auto-width
                  v-for="col in props.cols"
                  v-text="col.label"
                  :key="col.name"
                  :props="props"
                ></q-th>
              </q-tr>
            </template>
            <template v-slot:body="props">
              <q-tr :props="props">
                <q-td auto-width v-if="g.user.super_user">
                  <lnbits-update-balance
                    :wallet_id="props.row.id"
                    @credit-value="handleBalanceUpdate"
                    class="q-mr-md"
                  ></lnbits-update-balance>
                </q-td>
                <q-td auto-width>
                  <q-btn
                    round
                    icon="menu"
                    size="sm"
                    color="secondary"
                    @click="showPayments(props.row.id)"
                  >
                    <q-tooltip>Show Payments</q-tooltip>
                  </q-btn>

                  <q-btn
                    round
                    v-if="!props.row.deleted"
                    icon="vpn_key"
                    size="sm"
                    color="primary"
                    class="q-ml-xs"
                    @click="utils.copyText(props.row.adminkey)"
                  >
                    <q-tooltip>Copy Admin Key</q-tooltip>
                  </q-btn>
                  <q-btn
                    round
                    v-if="!props.row.deleted"
                    icon="vpn_key"
                    size="sm"
                    color="secondary"
                    class="q-ml-xs"
                    @click="utils.copyText(props.row.inkey)"
                  >
                    <q-tooltip>Copy Invoice Key</q-tooltip>
                  </q-btn>

                  <q-btn
                    round
                    icon="delete"
                    size="sm"
                    color="negative"
                    class="q-ml-xs"
                    @click="
                      deleteUserWallet(
                        props.row.user,
                        props.row.id,
                        props.row.deleted
                      )
                    "
                  >
                    <q-tooltip>Delete Wallet</q-tooltip>
                  </q-btn>
                  <q-btn
                    round
                    v-if="props.row.deleted"
                    icon="toggle_off"
                    size="sm"
                    color="secondary"
                    class="q-ml-xs"
                    @click="undeleteUserWallet(props.row.user, props.row.id)"
                  >
                    <q-tooltip>Undelete Wallet</q-tooltip>
                  </q-btn>
                  <q-btn
                    icon="link"
                    size="sm"
                    flat
                    class="cursor-pointer q-mr-xs"
                    @click="copyWalletLink(props.row.id)"
                  >
                    <q-tooltip>Copy Wallet Link</q-tooltip>
                  </q-btn>
                </q-td>
                <q-td auto-width>
                  <span
                    v-text="props.row.name"
                    v-if="!props.row.editable"
                    :class="
                      props.row.deleted ? 'text-strike' : 'cursor-pointer'
                    "
                    @click="props.row.editable = true && !props.row.deleted"
                  ></span>
                  <q-input
                    v-else
                    @keydown.enter="updateWallet(props.row)"
                    v-model="props.row.name"
                    size="xs"
                    flat
                    dense
                  >
                    <template v-slot:append>
                      <q-btn
                        @click="updateWallet(props.row)"
                        round
                        dense
                        size="xs"
                        flat
                        icon="send"
                      />
                    </template>
                  </q-input>
                </q-td>
                <q-td auto-width>
                  <q-btn
                    icon="content_copy"
                    size="sm"
                    flat
                    class="cursor-pointer q-mr-xs"
                    @click="utils.copyText(props.row.id)"
                  >
                    <q-tooltip>Copy Wallet ID</q-tooltip>
                  </q-btn>

                  <span
                    v-text="props.row.id"
                    :class="props.row.deleted ? 'text-strike' : ''"
                  ></span>
                </q-td>

                <q-td auto-width v-text="props.row.currency"></q-td>
                <q-td
                  auto-width
                  v-text="formatSat(props.row.balance_msat)"
                ></q-td>
              </q-tr>
            </template>
          </q-table>
        </q-card>
      </div>
      <div v-if="activeUser.show" class="row">
        <div class="col-12 col-md-6">
          <div class="row q-mb-lg">
            <div class="col">
              <q-btn
                icon="arrow_back_ios"
                @click="backToUsersPage()"
                :label="$t('back')"
              ></q-btn>
              <q-btn
                v-if="activeUser.data.id"
                @click="updateUser()"
                color="primary"
                :label="$t('update_account')"
                class="q-ml-md"
              ></q-btn>
              <q-btn
                v-else
                @click="createUser()"
                :label="$t('create_account')"
                color="primary"
                class="float-right"
              ></q-btn>
            </div>
          </div>
          <q-card v-if="activeUser.show" class="q-pa-md">
            <q-card-section>
              <div class="text-h6">
                <span
                  v-if="activeUser.data.id"
                  v-text="$t('update_account')"
                ></span>
                <span v-else v-text="$t('create_account')"></span>
              </div>
            </q-card-section>
            <q-card-section>
              <q-input
                v-if="activeUser.data.id"
                v-model="activeUser.data.id"
                :label="$t('user_id')"
                filled
                dense
                readonly
                :type="activeUser.data.showUserId ? 'text' : 'password'"
                class="q-mb-md"
                ><q-btn
                  @click="
                    activeUser.data.showUserId = !activeUser.data.showUserId
                  "
                  dense
                  flat
                  :icon="
                    activeUser.data.showUserId ? 'visibility_off' : 'visibility'
                  "
                  color="grey"
                ></q-btn>
              </q-input>
              <q-input
                v-model="activeUser.data.username"
                :label="$t('username')"
                filled
                dense
                class="q-mb-md"
              >
              </q-input>
              <q-toggle
                size="xs"
                v-if="!activeUser.data.id"
                color="secondary"
                :label="$t('set_password')"
                v-model="activeUser.setPassword"
              >
                <q-tooltip v-text="$t('set_password_tooltip')"></q-tooltip>
              </q-toggle>

              <q-input
                v-if="activeUser.setPassword"
                v-model="activeUser.data.password"
                :type="activeUser.data.showPassword ? 'text' : 'password'"
                autocomplete="off"
                :label="$t('password')"
                filled
                dense
                :rules="[
                  val => !val || val.length >= 8 || $t('invalid_password')
                ]"
              >
                <q-btn
                  @click="
                    activeUser.data.showPassword = !activeUser.data.showPassword
                  "
                  dense
                  flat
                  :icon="
                    activeUser.data.showPassword
                      ? 'visibility_off'
                      : 'visibility'
                  "
                  color="grey"
                ></q-btn>
              </q-input>
              <q-input
                v-if="activeUser.setPassword"
                v-model="activeUser.data.password_repeat"
                :type="activeUser.data.showPassword ? 'text' : 'password'"
                type="password"
                autocomplete="off"
                :label="$t('password_repeat')"
                filled
                dense
                class="q-mb-md"
                :rules="[
                  val => !val || val.length >= 8 || $t('invalid_password')
                ]"
              >
                <q-btn
                  @click="
                    activeUser.data.showPassword = !activeUser.data.showPassword
                  "
                  dense
                  flat
                  :icon="
                    activeUser.data.showPassword
                      ? 'visibility_off'
                      : 'visibility'
                  "
                  color="grey"
                ></q-btn>
              </q-input>

              <q-input
                v-model="activeUser.data.pubkey"
                :label="'Nostr ' + $t('pubkey')"
                filled
                dense
                class="q-mb-md"
              >
                <q-tooltip v-text="$t('nostr_pubkey_tooltip')"></q-tooltip>
              </q-input>
              <q-input
                v-model="activeUser.data.email"
                :label="$t('email')"
                filled
                dense
                class="q-mb-md"
              >
              </q-input>
            </q-card-section>

            <q-card-section v-if="activeUser.data.extra">
              <q-input
                v-model="activeUser.data.extra.first_name"
                :label="$t('first_name')"
                filled
                dense
                class="q-mb-md"
              >
              </q-input>
              <q-input
                v-model="activeUser.data.extra.last_name"
                :label="$t('last_name')"
                filled
                dense
                class="q-mb-md"
              >
              </q-input>
              <q-input
                v-model="activeUser.data.extra.provider"
                :label="$t('auth_provider')"
                filled
                dense
                class="q-mb-md"
              >
              </q-input>
              <q-input
                v-model="activeUser.data.external_id"
                :label="$t('external_id')"
                filled
                dense
                class="q-mb-md"
              >
              </q-input>
              <q-input
                v-model="activeUser.data.extra.picture"
                :label="$t('picture')"
                filled
                dense
                class="q-mb-md"
              >
              </q-input>
              <q-select
                filled
                dense
                v-model="activeUser.data.extensions"
                multiple
                label="User extensions"
                :options="g.extensions"
              ></q-select>
            </q-card-section>
            <q-card-section v-if="activeUser.data.id">
              <q-btn
                @click="resetPassword(activeUser.data.id)"
                :disable="activeUser.data.is_super_user"
                :label="$t('reset_password')"
                icon="refresh"
                color="primary"
              >
                <q-tooltip>Generate and copy password reset url</q-tooltip>
              </q-btn>
              <q-btn
                @click="deleteUser(activeUser.data.id)"
                :disable="activeUser.data.is_super_user"
                :label="$t('delete')"
                icon="delete"
                color="negative"
                class="float-right"
              >
                <q-tooltip>Delete User</q-tooltip></q-btn
              >
            </q-card-section>
          </q-card>
        </div>
      </div>
      <div v-else-if="activeWallet.show">
        <q-dialog v-model="createWalletDialog.show" position="top">
          <q-card class="q-pa-md q-pt-md lnbits__dialog-card">
            <strong>Create Wallet</strong>
            <div class="row">
              <div class="col-12">
                <div class="row q-mt-lg">
                  <div class="col">
                    <q-input
                      v-model="createWalletDialog.data.name"
                      :label="$t('name_your_wallet')"
                      filled
                      dense
                      class="q-mb-md"
                    >
                    </q-input>
                  </div>
                </div>
                <div class="row q-mt-lg">
                  <div class="col">
                    <q-select
                      filled
                      dense
                      v-model="createWalletDialog.data.currency"
                      :options="{{ currencies | safe }}"
                    ></q-select>
                  </div>
                </div>
                <div class="row q-mt-lg">
                  <q-btn
                    v-close-popup
                    @click="createWallet()"
                    unelevated
                    color="primary"
                    type="submit"
                    >Create</q-btn
                  >
                  <q-btn v-close-popup flat color="grey" class="q-ml-auto"
                    >Cancel</q-btn
                  >
                </div>
              </div>
            </div>
          </q-card>
        </q-dialog>
      </div>
      <div v-else>
        <div class="row q-col-gutter-md q-mb-md">
          <div class="col-12">
            <q-card>
              <div class="q-pa-sm">
                <div class="row items-center justify-between q-gutter-xs">
                  <div class="col">
                    <q-btn
                      @click="showAccountPage()"
                      :label="$t('create_account')"
                      color="primary"
                    >
                    </q-btn>
                  </div>
                  <div>
                    <q-btn
                      v-if="g.user.admin"
                      flat
                      round
                      icon="settings"
                      to="/admin#users"
                    >
                      <q-tooltip v-text="$t('admin_settings')"></q-tooltip>
                    </q-btn>
                  </div>
                </div>
              </div>
            </q-card>
          </div>
        </div>

        <q-card class="q-pa-md">
          <q-table
            row-key="id"
            :rows="users"
            :columns="usersTable.columns"
            v-model:pagination="usersTable.pagination"
            :no-data-label="$t('no_users')"
            :filter="usersTable.search"
            :loading="usersTable.loading"
            @request="fetchUsers"
          >
            <template v-slot:header="props">
              <q-tr :props="props">
                <q-th auto-width>
                  <q-btn-dropdown color="primary" icon="sort" flat dense>
                    <q-list>
                      <template
                        class="full-width"
                        v-for="column in usersTable.sortFields"
                        :key="column.name"
                      >
                        <q-item
                          @click="sortByColumn(column.name)"
                          clickable
                          v-ripple
                          v-close-popup
                          dense
                        >
                          <q-item-section>
                            <q-item-label lines="1" class="full-width"
                              ><span v-text="column.label"></span
                            ></q-item-label>
                          </q-item-section>
                          <q-item-section side>
                            <template
                              v-if="
                                usersTable.pagination.sortBy === column.name
                              "
                            >
                              <q-icon
                                v-if="usersTable.pagination.descending"
                                name="arrow_downward"
                              ></q-icon>
                              <q-icon v-else name="arrow_upward"></q-icon>
                            </template>
                          </q-item-section>
                        </q-item>
                      </template>
                    </q-list>
                  </q-btn-dropdown>
                </q-th>
                <q-th v-for="col in props.cols" :key="col.name" :props="props">
                  <q-input
                    v-if="
                      [
                        'user',
                        'username',
                        'email',
                        'pubkey',
                        'wallet_id'
                      ].includes(col.name)
                    "
                    v-model="searchData[col.name]"
                    @keydown.enter="searchUserBy(col.name)"
                    dense
                    type="text"
                    filled
                    :label="col.label"
                  >
                    <template v-slot:append>
                      <q-icon
                        name="search"
                        @click="searchUserBy(col.name)"
                        class="cursor-pointer"
                      />
                    </template>
                  </q-input>

                  <span v-else v-text="col.label"></span>
                </q-th>
              </q-tr>
            </template>
            <template v-slot:body="props">
              <q-tr auto-width :props="props">
                <q-td>
                  <q-btn
                    @click="showAccountPage(props.row.id)"
                    round
                    icon="edit"
                    size="sm"
                    color="secondary"
                    class="q-ml-xs"
                  >
                    <q-tooltip>
                      <span v-text="$t('update_account')"></span>
                    </q-tooltip>
                  </q-btn>
                </q-td>
                <q-td>
                  <q-toggle
                    size="xs"
                    v-if="!props.row.is_super_user"
                    color="secondary"
                    v-model="props.row.is_admin"
                    @update:model-value="toggleAdmin(props.row.id)"
                  >
                    <q-tooltip>Toggle Admin</q-tooltip>
                  </q-toggle>
                  <q-btn
                    round
                    v-if="props.row.is_super_user"
                    icon="verified"
                    size="sm"
                    color="secondary"
                    class="q-ml-xs"
                  >
                    <q-tooltip>Super User</q-tooltip>
                  </q-btn>
                </q-td>

                <q-td>
                  <q-btn
                    icon="list"
                    size="sm"
                    color="secondary"
                    :label="props.row.wallet_count"
                    @click="fetchWallets(props.row.id)"
                  >
                  </q-btn>
                  <q-btn
                    v-if="users.length == 1 && searchData.wallet_id"
                    round
                    icon="menu"
                    size="sm"
                    color="secondary"
                    class="q-ml-sm"
                    @click="showWalletPayments(searchData.wallet_id)"
                  >
                    <q-tooltip>Show Payments</q-tooltip>
                  </q-btn>
                </q-td>

                <q-td>
                  <q-btn
                    icon="content_copy"
                    size="sm"
                    flat
                    class="cursor-pointer q-mr-xs"
                    @click="utils.copyText(props.row.id)"
                  >
                    <q-tooltip>Copy User ID</q-tooltip>
                  </q-btn>
                  <span v-text="shortify(props.row.id)"></span>
                </q-td>
                <q-td v-text="props.row.username"></q-td>

                <q-td v-text="props.row.email"></q-td>

                <q-td>
                  <q-btn
                    v-if="props.row.pubkey"
                    icon="content_copy"
                    size="sm"
                    flat
                    class="cursor-pointer q-mr-xs"
                    @click="utils.copyText(props.row.pubkey)"
                  >
                    <q-tooltip>Copy Public Key</q-tooltip>
                  </q-btn>
                  <span v-text="shortify(props.row.pubkey)"></span>
                </q-td>
                <q-td v-text="formatSat(props.row.balance_msat)"></q-td>

                <q-td v-text="props.row.transaction_count"></q-td>

                <q-td v-text="utils.formatDate(props.row.last_payment)"></q-td>
              </q-tr>
            </template>
          </q-table>
        </q-card>
      </div>
    </div>
  </div>
</template>
