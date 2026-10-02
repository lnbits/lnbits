<template id="onchain-address-list">
  <div>
    <div class="row items-center no-wrap q-mb-md">
      <div class="col q-pr-lg">
        <q-select
          filled
          clearable
          dense
          emit-value
          v-model="selectedWallet"
          :options="accounts"
          :label="$t('onchain.wallet_account')"
        ></q-select>
      </div>
      <div class="col q-pr-lg">
        <q-select
          filled
          clearable
          dense
          emit-value
          multiple
          :options="filterOptions"
          v-model="filterValues"
          :label="$t('onchain.filter')"
        ></q-select>
      </div>
      <div class="col-auto">
        <q-input
          borderless
          dense
          debounce="300"
          v-model="addressesTable.filter"
          :placeholder="$t('onchain.search')"
        >
          <template v-slot:append>
            <q-icon name="search"></q-icon>
          </template>
        </q-input>
      </div>
    </div>
    <q-table
      style="height: 400px"
      flat
      dense
      :rows="getFilteredAddresses()"
      row-key="id"
      virtual-scroll
      :columns="addressesTableColumns"
      v-model:pagination="addressesTable.pagination"
      :filter="addressesTable.filter"
    >
      <template v-slot:body="props">
        <q-tr :props="props">
          <q-td auto-width>
            <q-btn
              size="sm"
              color="primary"
              round
              dense
              @click="props.row.expanded = !props.row.expanded"
              :icon="props.row.expanded ? 'remove' : 'add'"
            ></q-btn>
          </q-td>

          <q-td key="address" :props="props">
            <div>
              <a
                style="color: unset"
                :href="mempoolEndpoint + '/address/' + props.row.address"
                target="_blank"
                v-text="props.row.address"
              ></a>
              <q-badge
                v-if="props.row.branch_index === 1"
                color="primary"
                class="q-mr-md"
                outline
                v-text="$t('onchain.change')"
              >
              </q-badge>
              <q-btn
                v-if="props.row.gapLimitExceeded"
                color="yellow"
                icon="warning"
                :title="$t('onchain.gap_limit_exceeded_short')"
                @click="props.row.expanded = !props.row.expanded"
                outline
                class="q-ml-md"
                size="xs"
              >
              </q-btn>
            </div>
          </q-td>

          <q-td
            key="amount"
            :props="props"
            :class="
              props.row.amount > 0 ? 'text-green-13 text-weight-bold' : ''
            "
          >
            <div v-text="satBtc(props.row.amount)"></div>
          </q-td>

          <q-td key="note" :props="props">
            <div v-text="props.row.note"></div>
          </q-td>
        </q-tr>
        <q-tr v-show="props.row.expanded" :props="props">
          <q-td colspan="100%">
            <div class="row items-center q-mt-md q-mb-lg">
              <div class="col-2 q-pr-lg"></div>
              <div class="col-2 q-pr-lg">
                <q-btn
                  unelevated
                  dense
                  size="md"
                  icon="qr_code"
                  :color="$q.dark.isActive ? 'grey-7' : 'grey-5'"
                  @click="showAddressDetails(props.row)"
                  :label="$t('onchain.qr_code')"
                >
                </q-btn>
              </div>
              <div class="col-2 q-pr-lg">
                <q-btn
                  outline
                  color="grey"
                  icon="content_copy"
                  @click="copyText(props.row.address)"
                  class="q-ml-sm"
                  :label="$t('onchain.copy')"
                ></q-btn>
              </div>
              <div class="col-2 q-pr-lg">
                <q-btn
                  outline
                  dense
                  size="md"
                  icon="refresh"
                  color="grey"
                  @click="scanAddress(props.row)"
                  :label="$t('onchain.rescan')"
                >
                </q-btn>
              </div>
              <div class="col-2 q-pr-lg">
                <q-btn
                  outline
                  dense
                  size="md"
                  icon="history"
                  color="grey"
                  @click="searchInTab('history', props.row.address)"
                  :label="$t('onchain.history')"
                ></q-btn>
              </div>
              <div class="col-2 q-pr-lg">
                <q-btn
                  outline
                  dense
                  size="md"
                  color="grey"
                  @click="searchInTab('utxos', props.row.address)"
                  :label="$t('onchain.view_coins')"
                ></q-btn>
              </div>
            </div>

            <div class="row items-center no-wrap q-mb-md">
              <div
                class="col-2 q-pr-lg"
                v-text="$t('onchain.note_label')"
              ></div>
              <div class="col-8 q-pr-lg">
                <q-input
                  filled
                  dense
                  v-model.trim="props.row.note"
                  type="text"
                  :label="$t('onchain.note')"
                ></q-input>
              </div>
              <div class="col-2 q-pr-lg">
                <q-btn
                  outline
                  color="grey"
                  @click="updateNoteForAddress(props.row, props.row.note)"
                  :label="$t('onchain.update')"
                >
                </q-btn>
              </div>
            </div>

            <div
              v-if="props.row.error"
              class="row items-center no-wrap q-mb-md"
            >
              <div class="col-2 q-pr-lg"></div>
              <div class="col-10 q-pr-lg">
                <q-badge color="red">
                  <span v-text="props.row.error"></span>
                </q-badge>
              </div>
            </div>
            <div
              v-if="props.row.gapLimitExceeded"
              class="row items-center no-wrap q-mb-md"
            >
              <div class="col-2 q-pr-lg"></div>
              <div class="col-10 q-pr-lg">
                <q-badge
                  color="yellow"
                  text-color="black"
                  v-text="$t('onchain.gap_limit_exceeded')"
                ></q-badge>
              </div>
            </div>
          </q-td>
        </q-tr>
      </template>
    </q-table>
  </div>
</template>
