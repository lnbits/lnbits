<template id="page-wallets">
  <div class="row q-col-gutter-md q-mb-md">
    <div class="col-12">
      <q-card>
        <div class="q-pa-sm q-pl-lg">
          <div class="row items-center justify-between q-gutter-xs">
            <div class="col">
              <q-btn
                @click="showAddWalletDialog.show = true"
                :label="$t('add_wallet')"
                color="primary"
              >
              </q-btn>
            </div>
            <div class="float-left">
              <q-input
                :label="$t('search_wallets')"
                dense
                class="float-right q-pr-xl"
                v-model="walletsTable.search"
              >
                <template v-slot:before>
                  <q-icon name="search"> </q-icon>
                </template>
                <template v-slot:append>
                  <q-icon
                    v-if="walletsTable.search !== ''"
                    name="close"
                    @click="walletsTable.search = ''"
                    class="cursor-pointer"
                  >
                  </q-icon>
                </template>
              </q-input>
            </div>
          </div>
        </div>
      </q-card>
    </div>
  </div>
  <div>
    <div>
      <div>
        <q-table
          grid
          grid-header
          flat
          bordered
          :rows="wallets"
          :columns="walletsTable.columns"
          v-model:pagination="walletsTable.pagination"
          :loading="walletsTable.loading"
          @request="getUserWallets"
          row-key="id"
          :filter="filter"
          hide-header
        >
          <template v-slot:item="props">
            <div class="q-pa-xs col-xs-12 col-sm-6 col-md-4">
              <q-card
                class="q-ma-sm cursor-pointer wallet-list-card"
                style="text-decoration: none"
                @click="goToWallet(props.row.id)"
              >
                <q-card-section>
                  <div class="row items-center">
                    <q-avatar
                      size="lg"
                      :text-color="$q.dark.isActive ? 'black' : 'grey-3'"
                      :color="props.row.extra.color"
                      :icon="props.row.extra.icon"
                    >
                    </q-avatar>

                    <div
                      class="text-h6 q-pl-md ellipsis"
                      class="text-bold"
                      v-text="props.row.name"
                    ></div>
                    <q-space> </q-space>
                    <q-btn
                      v-if="props.row.extra.pinned"
                      round
                      color="primary"
                      text-color="black"
                      size="xs"
                      icon="push_pin"
                      class="float-right"
                      style="transform: rotate(30deg)"
                    ></q-btn>
                  </div>

                  <div class="row items-center q-pt-sm">
                    <h6 class="q-my-none ellipsis full-width">
                      <strong
                        v-text="formatBalance(props.row.balance_msat / 1000)"
                      ></strong>
                    </h6>
                  </div>
                </q-card-section>
                <q-separator />

                <q-card-section class="text-left">
                  <small>
                    <strong>
                      <span v-text="$t('currency')"></span>
                    </strong>
                    <span v-text="props.row.currency || 'sat'"></span>
                  </small>
                  <br />
                  <small>
                    <strong>
                      <span v-text="$t('id')"></span>
                      :
                    </strong>
                    <span v-text="props.row.id"></span>
                  </small>
                </q-card-section>
              </q-card>
            </div>
          </template>
        </q-table>
      </div>
    </div>
  </div>

  <q-dialog
    v-model="showAddWalletDialog.show"
    persistent
    @hide="showAddWalletDialog = {show: false}"
  >
    <q-card style="min-width: 350px">
      <q-card-section>
        <div class="text-h6">
          <span v-text="$t('wallet_name')"></span>
        </div>
      </q-card-section>

      <q-card-section class="q-pt-none">
        <q-input
          dense
          v-model="showAddWalletDialog.name"
          autofocus
          @keyup.enter="submitAddWallet()"
        ></q-input>
      </q-card-section>

      <q-card-actions align="right" class="text-primary">
        <q-btn flat :label="$t('cancel')" v-close-popup></q-btn>
        <q-btn
          flat
          :label="$t('add_wallet')"
          v-close-popup
          @click="submitAddWallet()"
        ></q-btn>
      </q-card-actions>
    </q-card>
  </q-dialog>
</template>
