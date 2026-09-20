<template id="page-onchain">
  <div v-if="g.user.wallets.length" class="row q-col-gutter-md onchain-wallet">
    <div class="col-12 col-md-7 q-gutter-y-md">
      <q-card class="wallet-card">
        <q-card-section>
          <template v-if="selectedWallet">
            <div class="row items-center q-mb-sm">
              <q-btn
                v-if="hasFiatRate"
                flat
                dense
                icon="swap_vert"
                aria-label="Switch balance currency"
                @click="g.isFiatPriority = !g.isFiatPriority"
              ></q-btn>
              <div class="col">
                <div class="text-h3 text-weight-bold onchain-balance">
                  {{
                    g.isFiatPriority && hasFiatRate
                      ? selectedFiat
                      : balanceLabel
                  }}
                </div>
                <div
                  v-if="hasFiatRate"
                  class="text-h5 text-italic"
                  style="opacity: 0.75"
                >
                  {{ g.isFiatPriority ? balanceLabel : selectedFiat }}
                </div>
              </div>
              <div
                v-if="hasFiatRate && $q.screen.gt.sm"
                class="text-right text-bold text-italic"
              >
                BTC Price<br />{{
                  utils.formatCurrency(g.exchangeRate, g.wallet.currency)
                }}
              </div>
            </div>
            <div
              class="text-caption text-grey q-mb-md"
              role="status"
              aria-live="polite"
            >
              {{ walletKindLabel }} ·
              {{
                scan.scanning
                  ? 'Updating balance…'
                  : syncError
                    ? 'Update failed — balance may be out of date'
                    : lastSynced
                      ? 'Updated ' + lastSynced
                      : 'Balance has not been checked'
              }}
              <span v-if="pendingBalance">
                · {{ formatAmount(pendingBalance) }} pending</span
              >
            </div>
            <q-banner
              v-if="
                selectedWallet.wallet_kind === 'hot' &&
                !selectedWallet.backup_confirmed
              "
              rounded
              class="bg-orange-2 text-black q-mb-md"
            >
              Back up your recovery phrase before receiving or sending bitcoin.
              <template v-slot:action
                ><q-btn
                  flat
                  label="Back up wallet"
                  @click="$refs.hotWallet.openBackup(selectedWallet)"
                ></q-btn
              ></template>
            </q-banner>
            <div class="row items-center q-gutter-sm onchain-wallet-actions">
              <q-btn
                unelevated
                color="primary"
                icon="file_download"
                label="Receive"
                :loading="receiving"
                :disable="!canTransact"
                @click="receiveBitcoin"
              ></q-btn>
              <q-btn
                unelevated
                color="primary"
                icon="file_upload"
                label="Send"
                :disable="!canTransact || !selectedUtxos.length"
                @click="goToPaymentView"
              ></q-btn>
              <q-space></q-space>
              <q-btn
                flat
                round
                dense
                icon="refresh"
                aria-label="Refresh wallet"
                :loading="scan.scanning"
                :disable="showPayment"
                @click="scanAllAddresses"
                ><q-tooltip>Refresh balance and activity</q-tooltip></q-btn
              >
            </div>
          </template>
          <div v-else class="q-py-xl text-center">
            <q-icon
              name="account_balance_wallet"
              size="48px"
              color="primary"
            ></q-icon>
            <h2 class="text-h6 q-mb-sm">
              Bitcoin, alongside your Lightning wallets
            </h2>
            <p>
              Create a server wallet, connect a hardware wallet, or follow an
              existing wallet.
            </p>
            <q-btn
              color="primary"
              unelevated
              label="Set up wallet"
              @click="$refs.walletList.openSetup()"
              :disable="
                !config.isLoaded ||
                $refs.walletList?.loading ||
                $refs.walletList?.fetchError
              "
            ></q-btn>
          </div>
          <q-linear-progress
            v-if="scan.scanning"
            class="q-mt-md"
            indeterminate
          ></q-linear-progress>
          <q-banner v-if="syncError" class="q-mt-md" dense
            >Could not finish checking the blockchain. Showing the last known
            balances and activity.</q-banner
          >
        </q-card-section>
      </q-card>

      <q-banner v-if="lastBroadcastTxId" rounded class="q-mb-md">
        Payment broadcast successfully.
        <template v-slot:action
          ><q-btn
            flat
            color="primary"
            label="View transaction"
            tag="a"
            :href="mempoolHostname + '/tx/' + lastBroadcastTxId"
            target="_blank"
            rel="noopener noreferrer"
          ></q-btn
          ><q-btn
            flat
            round
            icon="close"
            aria-label="Dismiss payment confirmation"
            @click="lastBroadcastTxId = null"
          ></q-btn
        ></template>
      </q-banner>
      <q-card v-if="selectedWallet && !showPayment">
        <q-tabs v-model="tab" active-color="primary" align="left" no-caps>
          <q-tab name="history" label="Activity"></q-tab>
          <q-tab name="addresses" label="Addresses"></q-tab>
          <q-tab name="utxos" label="Coins"></q-tab>
        </q-tabs>
        <q-separator></q-separator>
        <q-tab-panels v-model="tab">
          <q-tab-panel name="history" class="q-pa-md">
            <div class="row items-center no-wrap q-mb-lg">
              <div class="col q-pr-md">
                <q-input
                  dense
                  clearable
                  v-model="historyFilter"
                  label="Search by transaction, address or amount"
                  aria-label="Search transactions"
                  ><template v-slot:before
                    ><q-icon name="search"></q-icon></template
                ></q-input>
              </div>
              <q-btn
                outline
                dense
                color="grey"
                icon="archive"
                aria-label="Export transactions as CSV"
                :disable="!activity.length"
                @click="exportActivity"
                ><q-tooltip>Export CSV</q-tooltip></q-btn
              >
            </div>
            <q-table
              dense
              flat
              class="onchain-activity-table"
              :rows="activity"
              :columns="activityColumns"
              row-key="txId"
              v-model:pagination="activityPagination"
              :rows-per-page-options="[10, 25, 50, 0]"
            >
              <template v-slot:header="props">
                <q-tr :props="props">
                  <q-th auto-width></q-th>
                  <q-th
                    v-for="col in props.cols"
                    :key="col.name"
                    :props="props"
                    >{{ col.label }}</q-th
                  >
                </q-tr>
              </template>
              <template v-slot:body="props">
                <q-tr :props="props">
                  <q-td auto-width class="text-center">
                    <q-icon
                      size="14px"
                      :name="
                        props.row.confirmed
                          ? props.row.amount < 0
                            ? 'call_made'
                            : 'call_received'
                          : 'schedule'
                      "
                      :color="
                        props.row.confirmed
                          ? props.row.amount < 0
                            ? 'pink'
                            : 'green'
                          : 'grey'
                      "
                      ><q-tooltip>{{
                        props.row.confirmed
                          ? 'Confirmed'
                          : 'Pending confirmation'
                      }}</q-tooltip></q-icon
                    >
                  </q-td>
                  <q-td
                    key="time"
                    :props="props"
                    class="onchain-activity-description"
                  >
                    <a
                      class="onchain-transaction-link"
                      :href="mempoolHostname + '/tx/' + props.row.txId"
                      target="_blank"
                      rel="noopener noreferrer"
                      :aria-label="'View transaction ' + props.row.txId"
                      >{{
                        props.row.amount < 0
                          ? 'Sent bitcoin'
                          : 'Received bitcoin'
                      }}
                      <q-tooltip>{{ props.row.txId }}</q-tooltip> </a
                    ><br />
                    <div
                      v-if="props.row.transactionAddresses.length"
                      class="onchain-activity-addresses"
                    >
                      <a
                        v-for="address in props.row.transactionAddresses"
                        :key="address"
                        class="onchain-transaction-link text-grey"
                        :href="mempoolHostname + '/address/' + address"
                        :aria-label="'View address ' + address"
                        :title="address"
                        target="_blank"
                        rel="noopener noreferrer"
                        >{{ props.row.amount < 0 ? 'To' : 'On' }}
                        {{ shortActivityAddress(address)
                        }}<q-tooltip>{{ address }}</q-tooltip></a
                      >
                    </div>
                    <i
                      class="text-grey"
                      :title="
                        props.row.confirmed
                          ? props.row.date
                          : 'Time since first seen by this wallet'
                      "
                      >{{ activityDate(props.row) }}</i
                    >
                    <span
                      v-if="!props.row.confirmed && props.row.firstSeen"
                      class="text-grey"
                    >
                      · Pending</span
                    >
                  </q-td>
                  <q-td key="amount" :props="props" class="text-right">
                    {{ formatActivityAmount(props.row.amount) }}
                    <div v-if="hasFiatRate" class="text-italic text-caption">
                      {{
                        utils.formatCurrency(
                          (Math.abs(props.row.amount) * g.exchangeRate) /
                            100000000,
                          g.wallet.currency
                        )
                      }}<q-tooltip>At the current exchange rate</q-tooltip>
                    </div>
                  </q-td>
                </q-tr>
              </template>
              <template v-slot:no-data>
                <div class="full-width text-center q-pa-lg">
                  <q-icon name="receipt" size="32px" class="q-mb-sm"></q-icon>
                  <div>
                    {{
                      scan.scanning
                        ? 'Looking for transactions…'
                        : historyFilter
                          ? 'No matching transactions'
                          : 'No transactions yet'
                    }}
                  </div>
                  <div class="text-caption q-mt-sm">
                    {{
                      historyFilter
                        ? 'Try a different transaction, address or amount.'
                        : 'Receive bitcoin to get started.'
                    }}
                  </div>
                </div>
              </template>
            </q-table>
          </q-tab-panel>
          <q-tab-panel name="addresses">
            <onchain-address-list
              :addresses="selectedAddresses"
              :accounts="selectedAccounts"
              :mempool-endpoint="mempoolHostname"
              :sats-denominated="config.sats_denominated"
              :inkey="g.wallet.inkey"
              @scan:address="scanAddress"
              @show-address-details="showAddressDetails"
              @search:tab="searchInTab"
              @update:note="updateNoteForAddress"
            ></onchain-address-list>
          </q-tab-panel>
          <q-tab-panel name="utxos">
            <p class="text-caption">
              Coins are individual payments available to spend. Coin selection
              is also available when sending.
            </p>
            <onchain-utxo-list
              :utxos="selectedUtxos"
              :accounts="selectedAccounts"
              :mempool-endpoint="mempoolHostname"
              :sats-denominated="config.sats_denominated"
              :filter="utxosFilter"
            ></onchain-utxo-list>
          </q-tab-panel>
        </q-tab-panels>
      </q-card>
      <div v-if="showPayment && selectedWallet">
        <div class="row items-center">
          <h2 class="text-h6 col q-my-none">Send bitcoin</h2>
          <q-btn
            flat
            label="Cancel"
            :disable="$refs.paymentRef?.showChecking"
            @click="showPayment = false"
          ></q-btn>
        </div>
        <onchain-payment
          :key="selectedWallet.id + config.network"
          ref="paymentRef"
          :accounts="paymentData.accounts"
          :addresses="paymentData.addresses"
          :utxos="paymentData.utxos"
          :mempool-endpoint="mempoolHostname"
          :adminkey="g.wallet.adminkey"
          :serial-signer-ref="signerDevice"
          :sats-denominated="config.sats_denominated"
          :network="config.network"
          @broadcast-done="handleBroadcastSuccess"
        />
      </div>
    </div>
    <div class="col-12 col-md-5 q-gutter-y-md">
      <lnbits-wallet-extra
        :chart-config="chartConfig"
        @update-wallet="$emit('update-wallet', $event)"
      >
        <template #wallet-type-header>
          <q-separator></q-separator>
          <onchain-wallet-list
            v-if="config.isLoaded"
            ref="walletList"
            :adminkey="g.wallet.adminkey"
            :inkey="g.wallet.inkey"
            :sats-denominated="config.sats_denominated"
            :network="config.network"
            :addresses="addresses"
            :serial-signer-ref="signerDevice"
            :busy="showPayment"
            @accounts-update="updateAccounts"
            @new-receive-address="showAddressDetailsWithConfirmation"
            @create-hot="$refs.hotWallet.openCreate()"
            @backup-wallet="$refs.hotWallet.openBackup($event)"
          ></onchain-wallet-list>
          <onchain-hot-wallet
            ref="hotWallet"
            :adminkey="g.wallet.adminkey"
            :network="config.network"
            @wallet-created="hotWalletCreated"
            @backup-done="$refs.walletList.refreshWalletAccounts()"
          ></onchain-hot-wallet>
          <onchain-wallet-config
            :total="selectedBalance"
            v-model:config-data="config"
            :adminkey="g.wallet.adminkey"
            :busy="showPayment"
          >
            <template v-slot:trezor
              ><onchain-trezor-signer
                ref="trezorSigner"
                :network="config.network"
                @signed:tx="updateSignedTx"
                @device:connected="handleDeviceConnected"
              ></onchain-trezor-signer
            ></template>
            <template v-slot:serial
              ><onchain-serial-signer
                ref="serialSigner"
                :network="config.network"
                :sats-denominated="config.sats_denominated"
                @signed:psbt="updateSignedPsbt"
                @device:connected="handleDeviceConnected"
              ></onchain-serial-signer
            ></template>
          </onchain-wallet-config>
        </template>
        <template #wallet-type-tools>
          <q-expansion-item
            v-if="selectedWallet"
            group="extras"
            label="Advanced"
            icon="tune"
          >
            <q-card-section
              ><q-btn
                flat
                label="Import signed PSBT"
                :disable="showPayment"
                @click="openImportPsbt"
              ></q-btn>
              <p class="text-caption q-mb-none">
                Review a transaction signed by an offline wallet before
                broadcasting.
              </p></q-card-section
            >
          </q-expansion-item>
          <q-separator v-if="selectedWallet"></q-separator>
        </template>
      </lnbits-wallet-extra>
      <slot name="wallet-tools"></slot>
    </div>
    <q-dialog v-model="showAddress" position="top">
      <q-card class="q-pa-lg lnbits__dialog-card">
        <h5 class="text-subtitle1 q-my-none" v-text="'Receive bitcoin'"></h5>
        <q-separator></q-separator><br />

        <div class="q-mx-xl q-mb-md">
          <lnbits-qrcode
            v-if="currentAddress"
            :value="receiveUri"
          ></lnbits-qrcode>
        </div>
        <p v-if="currentAddress">
          <q-btn
            flat
            dense
            size="ms"
            icon="content_copy"
            @click="copyText(currentAddress.address)"
            class="q-ml-sm"
          ></q-btn>
          <span v-text="currentAddress.address"></span>
          <q-btn
            flat
            dense
            size="ms"
            icon="launch"
            type="a"
            :href="mempoolHostname + '/address/' + currentAddress.address"
            target="_blank"
          ></q-btn>
        </p>
        <q-input
          filled
          class="q-mb-md"
          v-model.number="receiveAmount"
          type="number"
          min="1"
          step="1"
          label="Amount in sats (optional)"
          :rules="[
            v =>
              !v ||
              (Number.isSafeInteger(+v) && +v > 0 && +v <= 2100000000000000) ||
              'Enter a whole number of sats'
          ]"
        ></q-input>
        <q-btn
          v-if="currentAddress"
          outline
          color="primary"
          label="Copy payment link"
          class="q-mb-md"
          @click="copyText(receiveUri)"
        ></q-btn>
        <p class="text-caption">
          Send only bitcoin on
          {{ config.network === 'Testnet' ? 'Testnet3' : config.network }} to
          this address.
        </p>
        <p v-if="currentAddress">
          <q-input
            filled
            dense
            v-model.trim="addressNote"
            type="text"
            :label="$t('onchain.note')"
          ></q-input>
        </p>
        <div v-if="currentAddress && currentAddress.gapLimitExceeded">
          <q-badge
            color="yellow"
            text-color="black"
            v-text="$t('onchain.gap_limit_exceeded')"
          ></q-badge>
        </div>
        <div class="row q-mt-lg q-gutter-sm">
          <q-btn
            v-if="currentAddress"
            outline
            v-close-popup
            color="grey"
            @click="
              updateNoteForAddress({
                addressId: currentAddress.id,
                note: addressNote
              })
            "
            class="q-ml-sm"
            :label="$t('onchain.save_note')"
          ></q-btn>
          <q-btn
            v-close-popup
            flat
            color="grey"
            class="q-ml-auto"
            :label="$t('onchain.close')"
          ></q-btn>
        </div>
        <div class="row q-mt-lg q-gutter-sm"></div>
      </q-card>
    </q-dialog>

    <q-dialog
      v-model="showEnterSignedPsbt"
      :persistent="$refs.paymentRef?.showChecking"
      position="top"
    >
      <q-card class="q-pa-lg lnbits__dialog-card">
        <h5
          class="text-subtitle1 q-my-none"
          v-text="$t('onchain.enter_signed_psbt')"
        ></h5>
        <q-separator></q-separator><br />

        <p>
          <q-input
            filled
            dense
            v-model.trim="signedBase64Psbt"
            type="textarea"
            :label="$t('onchain.signed_psbt')"
          ></q-input>
        </p>

        <div class="row q-mt-lg q-gutter-sm">
          <q-btn
            outline
            :loading="$refs.paymentRef?.showChecking"
            :disable="!signedBase64Psbt || $refs.paymentRef?.showChecking"
            color="primary"
            @click="checkPsbt"
            class="q-ml-sm"
            :label="$t('onchain.check_psbt')"
          ></q-btn>
          <q-btn
            v-close-popup
            flat
            color="grey"
            class="q-ml-auto"
            :label="$t('onchain.close')"
          ></q-btn>
        </div>
        <div class="row q-mt-lg q-gutter-sm"></div>
      </q-card>
    </q-dialog>
  </div>
  <q-banner v-else>Create an LNbits wallet to use onchain wallets.</q-banner>
</template>

<template id="onchain-wallet-config">
  <div>
    <q-banner v-if="loadError"
      >Could not load onchain settings.<template v-slot:action
        ><q-btn flat label="Retry" @click="getConfig"></q-btn></template
    ></q-banner>
    <q-card-section class="q-pt-xs">
      <div class="row items-center no-wrap">
        <div class="col row items-center q-gutter-sm">
          <slot name="trezor"></slot><slot name="serial"></slot>
        </div>
        <q-btn
          flat
          round
          dense
          class="q-ml-sm"
          icon="settings"
          aria-label="Onchain settings"
          :disable="busy"
          @click="openSettings"
          ><q-tooltip>Blockchain settings</q-tooltip></q-btn
        >
      </div>
    </q-card-section>

    <q-dialog v-model="show" position="top">
      <q-card class="q-pa-lg q-pt-xl lnbits__dialog-card">
        <q-form @submit="updateConfig" class="q-gutter-md">
          <q-select
            filled
            dense
            emit-value
            map-options
            v-model="config.explorer_provider"
            :options="explorerOptions"
            label="Block explorer"
          ></q-select>
          <q-input
            v-if="config.explorer_provider === 'mempool'"
            filled
            dense
            v-model.trim="config.mempool_endpoint"
            hint="Use mempool.space or your own Mempool server URL for this network."
            type="text"
            :label="$t('onchain.mempool_endpoint')"
          >
          </q-input>

          <q-input
            filled
            dense
            v-model.number="config.receive_gap_limit"
            type="number"
            min="0"
            :label="$t('onchain.receive_gap_limit')"
          ></q-input>

          <q-input
            filled
            dense
            v-model.number="config.change_gap_limit"
            type="number"
            min="0"
            :label="$t('onchain.change_gap_limit')"
          ></q-input>

          <q-select
            filled
            dense
            emit-value
            v-model="config.network"
            map-options
            :options="networkOptions"
            :label="$t('onchain.network')"
          ></q-select>

          <q-toggle
            :label="
              config.sats_denominated
                ? $t('onchain.sats_denominated')
                : $t('onchain.btc_denominated')
            "
            color="primary"
            v-model="config.sats_denominated"
          ></q-toggle>

          <div class="row q-mt-lg">
            <q-btn
              unelevated
              color="primary"
              :disable="
                config.explorer_provider === 'mempool' &&
                !config.mempool_endpoint
              "
              type="submit"
              :label="$t('onchain.update')"
            ></q-btn>
            <q-btn
              v-close-popup
              flat
              color="grey"
              class="q-ml-auto"
              :label="$t('onchain.cancel')"
            ></q-btn>
          </div>
        </q-form>
      </q-card>
    </q-dialog>
  </div>
</template>

<template id="onchain-utxo-list">
  <q-card>
    <q-card-section>
      <div class="row items-center q-mb-md">
        <div v-if="selectable" class="col-9 col-sm-5 q-pr-sm">
          <q-select
            filled
            dense
            emit-value
            v-model="utxoSelectionMode"
            :options="utxoSelectionModes"
            :label="$t('onchain.selection_mode')"
            @update:model-value="updateUtxoSelection"
          ></q-select>
        </div>
        <div v-if="selectable" class="col-3 col-sm-1">
          <q-btn
            outline
            icon="refresh"
            color="grey"
            @click="updateUtxoSelection"
            class="q-ml-sm"
          ></q-btn>
        </div>
        <div v-if="selectable" class="col-sm-2"></div>
        <div v-if="!selectable" class="col-sm-8"></div>
        <div class="col-12 col-sm-4">
          <q-input
            borderless
            dense
            debounce="300"
            v-model="filterLocal"
            :placeholder="$t('onchain.search')"
          >
            <template v-slot:append>
              <q-icon name="search"></q-icon>
            </template>
          </q-input>
        </div>
      </div>

      <q-table
        flat
        dense
        :rows="utxos"
        :row-key="row => row.txId + ':' + row.vout"
        :columns="columns"
        v-model:pagination="utxosTable.pagination"
        :filter="filterLocal"
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

            <q-td v-if="selectable" key="selected" :props="props">
              <div>
                <q-checkbox v-model="props.row.selected"></q-checkbox>
              </div>
            </q-td>
            <q-td key="status" :props="props">
              <div>
                <q-badge
                  v-if="props.row.confirmed"
                  @click="props.row.expanded = !props.row.expanded"
                  color="primary"
                  class="q-mr-md cursor-pointer"
                  v-text="$t('onchain.confirmed')"
                >
                </q-badge>
                <q-badge
                  v-if="!props.row.confirmed"
                  @click="props.row.expanded = !props.row.expanded"
                  color="secondary"
                  class="q-mr-md cursor-pointer"
                  v-text="$t('onchain.pending')"
                >
                </q-badge>
              </div>
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
                  v-if="props.row.isChange"
                  color="primary"
                  class="q-mr-md"
                  v-text="$t('onchain.change')"
                >
                </q-badge>
                <q-badge
                  v-if="props.row.accountType === 'p2tr'"
                  color="yellow"
                  text-color="black"
                  v-text="$t('onchain.taproot')"
                >
                </q-badge>
              </div>
            </q-td>

            <q-td
              key="amount"
              :props="props"
              class="text-green-13 text-weight-bold"
            >
              <div v-text="satBtc(props.row.amount)"></div>
            </q-td>
            <q-td key="date" :props="props" v-text="props.row.date"></q-td>
            <q-td key="wallet" :props="props">
              <div v-text="getWalletName(props.row.wallet)"></div>
            </q-td>
          </q-tr>
          <q-tr v-show="props.row.expanded" :props="props">
            <q-td colspan="100%">
              <div class="row items-center q-mb-md">
                <div
                  class="col-2 q-pr-lg"
                  v-text="$t('onchain.transaction_id')"
                ></div>
                <div class="col-10 q-pr-lg">
                  <a
                    style="color: unset"
                    :href="mempoolEndpoint + '/tx/' + props.row.txId"
                    target="_blank"
                    v-text="props.row.txId"
                  ></a>
                </div>
              </div>
            </q-td>
          </q-tr>
        </template>
      </q-table> </q-card-section
  ></q-card>
</template>

<template id="onchain-wallet-list">
  <div class="q-pt-sm">
    <q-linear-progress v-if="loading" indeterminate></q-linear-progress>
    <q-banner v-if="fetchError"
      >Could not load wallet.<template v-slot:action
        ><q-btn
          flat
          label="Retry"
          @click="refreshWalletAccounts"
        ></q-btn></template
    ></q-banner>
    <q-list separator>
      <q-item v-if="wallet" :disable="busy || loading">
        <q-item-section avatar
          ><q-icon
            :name="
              wallet.wallet_kind === 'hot'
                ? 'account_balance_wallet'
                : wallet.meta?.xpub
                  ? 'usb'
                  : 'visibility'
            "
          ></q-icon
        ></q-item-section>
        <q-item-section
          ><q-item-label class="row items-center q-gutter-x-sm">
            <span>{{ wallet.title }}</span>
            <q-badge
              outline
              :color="network === 'Mainnet' ? 'primary' : 'orange'"
            >
              {{ network === 'Testnet' ? 'Testnet3' : network }}
            </q-badge></q-item-label
          ><q-item-label caption>{{
            wallet.wallet_kind === 'hot'
              ? 'Server wallet'
              : wallet.meta?.xpub
                ? 'Hardware wallet'
                : 'Watch-only'
          }}</q-item-label></q-item-section
        >
        <q-item-section side>{{
          getAmmountForWallet(wallet.id)
        }}</q-item-section>
        <q-item-section side
          ><q-btn
            flat
            round
            dense
            icon="more_vert"
            :aria-label="'Manage ' + wallet.title"
            @click.stop
            ><q-menu auto-close
              ><q-list style="min-width: 180px">
                <q-item clickable @click="openQrCodeDialog(wallet.masterpub)"
                  ><q-item-section
                    >Export public descriptor</q-item-section
                  ></q-item
                >
                <q-item
                  v-if="wallet.wallet_kind === 'hot'"
                  clickable
                  @click="$emit('backup-wallet', wallet)"
                  ><q-item-section
                    >Back up recovery phrase</q-item-section
                  ></q-item
                >
                <q-item v-else clickable @click="deleteWalletAccount(wallet.id)"
                  ><q-item-section class="text-negative"
                    >Remove wallet</q-item-section
                  ></q-item
                >
              </q-list></q-menu
            ></q-btn
          ></q-item-section
        >
      </q-item>
    </q-list>
    <div
      v-if="!walletAccounts.length && !loading && !fetchError"
      class="q-px-md q-pb-lg text-caption"
    >
      <q-badge
        class="q-mr-sm"
        outline
        :color="network === 'Mainnet' ? 'primary' : 'orange'"
      >
        {{ network === 'Testnet' ? 'Testnet3' : network }}
      </q-badge>
      Set up a server, hardware or watch-only wallet to get started.
    </div>
  </div>
  <q-dialog v-model="showSetup">
    <q-card class="lnbits__dialog-card q-pa-md">
      <q-card-section
        ><h2 class="text-h6 q-my-none">Set up your onchain wallet</h2>
        <p class="text-caption q-mb-none">
          Choose how you want to hold your bitcoin on
          {{ network === 'Testnet' ? 'Testnet3' : network }}. To use another
          Bitcoin wallet, create another LNbits onchain wallet.
        </p></q-card-section
      >
      <q-list separator>
        <q-item clickable v-close-popup @click="$emit('create-hot')"
          ><q-item-section avatar
            ><q-icon
              name="account_balance_wallet"
              color="primary"
            ></q-icon></q-item-section
          ><q-item-section
            ><q-item-label>Server wallet</q-item-label
            ><q-item-label caption
              >Create or restore a wallet. This LNbits server holds the keys and
              signs payments.</q-item-label
            ></q-item-section
          ><q-item-section side
            ><q-icon name="chevron_right"></q-icon></q-item-section
        ></q-item>
        <q-item clickable v-close-popup @click="getXpubFromDevice"
          ><q-item-section avatar
            ><q-icon name="usb" color="primary"></q-icon></q-item-section
          ><q-item-section
            ><q-item-label>Hardware wallet</q-item-label
            ><q-item-label caption
              >Connect Trezor or a serial device first. Approve spending on your
              device.</q-item-label
            ></q-item-section
          ><q-item-section side
            ><q-icon name="chevron_right"></q-icon></q-item-section
        ></q-item>
        <q-item clickable v-close-popup @click="showAddAccountDialog"
          ><q-item-section avatar
            ><q-icon name="visibility" color="primary"></q-icon></q-item-section
          ><q-item-section
            ><q-item-label>Watch-only wallet</q-item-label
            ><q-item-label caption
              >Import a public key or descriptor. Sign with a hardware device or
              PSBT.</q-item-label
            ></q-item-section
          ><q-item-section side
            ><q-icon name="chevron_right"></q-icon></q-item-section
        ></q-item>
      </q-list>
      <q-card-actions align="right"
        ><q-btn flat label="Cancel" v-close-popup></q-btn
      ></q-card-actions>
    </q-card>
  </q-dialog>

  <q-dialog
    v-model="formDialog.show"
    :persistent="showCreating"
    position="top"
    @hide="closeFormDialog"
  >
    <q-card class="q-pa-lg q-pt-xl lnbits__dialog-card">
      <q-form @submit="addWalletAccount" class="q-gutter-md">
        <q-input
          filled
          dense
          v-model.trim="formDialog.data.title"
          type="text"
          :label="$t('onchain.title')"
        ></q-input>
        <q-input
          v-if="!formDialog.useSerialPort"
          filled
          type="textarea"
          v-model="formDialog.data.masterpub"
          height="50px"
          autogrow
          :label="$t('onchain.account_key_label')"
        ></q-input>
        <q-select
          v-if="formDialog.useSerialPort"
          filled
          dense
          emit-value
          v-model="formDialog.addressType"
          :options="addressTypeOptions"
          :label="$t('onchain.address_type')"
          @update:model-value="handleAddressTypeChanged"
        ></q-select>

        <q-input
          v-if="formDialog.useSerialPort"
          filled
          type="text"
          v-model="accountPath"
          height="50px"
          autogrow
          :label="$t('onchain.account_path')"
        ></q-input>

        <div class="row q-mt-lg">
          <q-btn
            unelevated
            color="primary"
            :label="$t('onchain.add_watch_only_account')"
            :loading="showCreating"
            :disable="
              (formDialog.useSerialPort
                ? !accountPath
                : !formDialog.data.masterpub?.trim()) ||
              !formDialog.data.title?.trim() ||
              showCreating
            "
            type="submit"
          >
          </q-btn>
          <q-btn
            v-close-popup
            :disable="showCreating"
            flat
            color="grey"
            class="q-ml-auto"
            :label="$t('onchain.cancel')"
          ></q-btn>
        </div>
      </q-form>
    </q-card>
  </q-dialog>
  <q-dialog v-model="showQrCodeDialog" position="top">
    <q-card class="q-pa-lg q-pt-xl lnbits__dialog-card">
      <div class="q-mx-xl q-mb-md">
        <lnbits-qrcode :value="qrCodeValue"></lnbits-qrcode>
      </div>
    </q-card>
  </q-dialog>
</template>

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
          <q-td key="wallet" :props="props">
            <div v-text="getWalletName(props.row.wallet)"></div>
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

<template id="onchain-fee-rate">
  <div>
    <div class="row items-center q-mb-md">
      <div
        class="col-4 col-sm-2 q-pr-sm"
        v-text="$t('onchain.fee_rate_label')"
      ></div>
      <div class="col-8 col-sm-3 q-pr-sm">
        <q-input
          filled
          dense
          v-model.number="feeRate"
          step="any"
          :rules="[
            val =>
              (Number.isFinite(+val) && +val > 0) ||
              $t('onchain.field_required')
          ]"
          type="number"
          label="sats/vbyte"
        ></q-input>
      </div>
      <div class="col-12 col-sm-7 q-pt-sm">
        <q-slider
          v-model="feeRate"
          color="secondary"
          markers
          snap
          label
          label-always
          :label-value="getFeeRateLabel(feeRate)"
          :min="1"
          :max="recommededFees.fastestFee"
        ></q-slider>
      </div>
    </div>
    <div
      v-if="
        feeRate < recommededFees.hourFee || feeRate > recommededFees.fastestFee
      "
      class="row items-center q-mb-md"
    >
      <div class="col-4 col-sm-2 q-pr-sm"></div>
      <div class="col-10 q-pr-lg">
        <q-badge
          v-if="feeRate < recommededFees.hourFee"
          color="pink"
          size="lg"
          v-text="$t('onchain.fee_too_low_warning')"
        >
        </q-badge>
        <q-badge
          v-if="feeRate > recommededFees.fastestFee"
          color="pink"
          v-text="$t('onchain.fee_too_high_warning')"
        >
        </q-badge>
      </div>
    </div>

    <div class="row items-center q-mb-md">
      <div
        class="col-4 col-sm-2 q-pr-sm"
        v-text="$t('onchain.fee_label')"
      ></div>
      <div class="col-8 col-sm-3 q-pr-sm">{{ feeValue }} sats</div>
      <div class="col-12 col-sm-7 q-pt-sm">
        <q-btn
          outline
          dense
          size="md"
          icon="refresh"
          color="grey"
          class="float-right"
          @click="refreshRecommendedFees()"
          :loading="refreshing"
          :label="$t('onchain.refresh_fee_rates')"
        ></q-btn>
      </div>
    </div>
  </div>
</template>

<template id="onchain-seed-input">
  <div>
    <div v-if="done">
      <div class="row">
        <div class="col-12" v-text="$t('onchain.seed_input_done')"></div>
      </div>
    </div>
    <div v-else>
      <div class="row">
        <div class="col-3 q-pt-sm" v-text="$t('onchain.word_count')"></div>
        <div class="col-6 q-pr-lg">
          <q-select
            filled
            dense
            v-model="wordCount"
            type="number"
            :label="$t('onchain.word_count')"
            :options="wordCountOptions"
            @update:model-value="initWords"
          ></q-select>
        </div>
        <div class="col-3 q-pr-lg"></div>
      </div>
      <div class="row">
        <div class="col-3 q-pr-lg"></div>
        <div
          class="col-6"
          v-text="
            $t('onchain.enter_word_at_position', {position: actualPosition})
          "
        ></div>
        <div class="col-3 q-pr-lg"></div>
      </div>
      <div class="row">
        <div class="col-3 q-pr-lg">
          <q-btn
            v-if="currentPosition > 0"
            @click="previousPosition"
            unelevated
            class="btn-full"
            color="secondary"
            :label="$t('onchain.previous')"
          ></q-btn>
        </div>
        <div class="col-6 q-pr-lg">
          <q-select
            filled
            dense
            use-input
            hide-selected
            fill-input
            input-debounce="0"
            v-model="currentWord"
            :options="options"
            @filter="filterFn"
            @input-value="setModel"
          ></q-select>
        </div>

        <div class="col-3 q-pr-lg">
          <q-btn
            v-if="currentPosition < wordCount - 1"
            @click="nextPosition"
            unelevated
            class="btn-full"
            color="secondary"
            :label="$t('onchain.next')"
          ></q-btn>
          <q-btn
            v-else
            @click="seedInputDone"
            unelevated
            class="btn-full"
            color="primary"
            :label="$t('onchain.done')"
          ></q-btn>
        </div>
        <q-linear-progress
          :value="currentPosition / (wordCount - 1)"
          size="5px"
          color="primary"
          class="q-mt-sm"
        ></q-linear-progress>
      </div>
    </div>
  </div>
</template>

<template id="onchain-send-to">
  <div class="row items-center no-wrap q-mb-md">
    <div class="col-12">
      <q-table
        flat
        dense
        hide-header
        :rows="data"
        :columns="paymentTable.columns"
        v-model:pagination="paymentTable.pagination"
      >
        <template v-slot:body="props">
          <q-tr :props="props">
            <q-td colspan="100%">
              <div class="row items-start">
                <div class="col-1">
                  <q-btn
                    flat
                    dense
                    size="l"
                    @click="deletePaymentAddress(props.row)"
                    icon="cancel"
                    color="grey"
                    class="q-mt-sm"
                  ></q-btn>
                </div>
                <div class="col-11 col-sm-7 q-pr-sm">
                  <q-input
                    filled
                    dense
                    v-model.trim="props.row.address"
                    type="text"
                    label="Bitcoin address or payment link"
                    :error="!!props.row.error"
                    :error-message="props.row.error"
                    :rules="[val => !!val || $t('onchain.field_required')]"
                    @update:model-value="handleAddressInput(props.row)"
                    ><template v-slot:append
                      ><q-btn
                        flat
                        round
                        dense
                        icon="qr_code_scanner"
                        aria-label="Scan bitcoin address"
                        @click="scanAddress(props.row)"
                      ></q-btn></template
                  ></q-input>
                </div>
                <div class="col-9 col-sm-3 q-pr-sm">
                  <q-input
                    filled
                    dense
                    v-model.number="props.row.amount"
                    type="number"
                    step="1"
                    :label="$t('onchain.amount_sats')"
                    :rules="[
                      val => !!val || $t('onchain.field_required'),
                      val =>
                        (Number.isSafeInteger(+val) && +val >= DUST_LIMIT) ||
                        $t('onchain.amount_too_small')
                    ]"
                    @update:model-value="handleOutputsChange"
                  ></q-input>
                </div>
                <div class="col-3 col-sm-1">
                  <q-btn
                    outline
                    color="grey"
                    @click="sendMaxToAddress(props.row)"
                    :label="$t('onchain.max')"
                  ></q-btn>
                </div>
              </div>
            </q-td>
          </q-tr>
        </template>
      </q-table>
      <div class="row items-center no-wrap">
        <div class="col-auto q-pr-sm">
          <q-btn
            unelevated
            color="primary"
            @click="addPaymentAddress"
            class="btn-full"
            :label="$t('onchain.add')"
          ></q-btn>
        </div>
        <div class="col">
          <div class="float-right">
            <span v-text="$t('onchain.payed_amount')"></span>
            <span class="text-subtitle2 q-ml-lg">
              {{ satBtc(getTotalPaymentAmount()) }}
            </span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<template id="onchain-payment">
  <div>
    <q-form @submit="checkAndSend" ref="paymentFormRef" class="q-gutter-y-md">
      <fieldset
        :disabled="showChecking"
        style="border: 0; padding: 0; margin: 0; min-width: 0"
      >
        <q-card class="q-mt-lg">
          <q-card-section>
            <onchain-send-to
              v-model:data="sendToList"
              :fee-rate="feeRate"
              :tx-size="txSize"
              :selected-amount="selectedAmount"
              :sats-denominated="satsDenominated"
              @update:outputs="handleOutputsChange"
              @send-max="sendMaximum"
            ></onchain-send-to>
          </q-card-section>
        </q-card>

        <q-card class="q-mt-lg">
          <q-card-section>
            <div class="row items-center">
              <div class="col-12 col-sm-4">
                <q-toggle
                  :label="$t('onchain.show_custom_fee')"
                  color="primary"
                  class="float-left"
                  v-model="showCustomFee"
                ></q-toggle>
              </div>

              <div class="col-12 col-sm-8">
                <div class="float-right">
                  <span v-text="$t('onchain.fee_rate_label')"></span>
                  <span class="text-subtitle2 q-ml-md">
                    {{ feeRate }} sats/vbyte</span
                  >
                  <span class="q-ml-lg" v-text="$t('onchain.fee_label')"></span>
                  <span class="text-subtitle2 q-ml-md">
                    {{ satBtc(feeValue) }}
                  </span>
                </div>
              </div>
            </div>

            <div
              v-show="showCustomFee"
              class="row items-center no-wrap q-mt-md"
            >
              <div class="col-12">
                <q-separator class="q-mb-md"></q-separator>
                <onchain-fee-rate
                  :fee-value="feeValue"
                  v-model:rate="feeRate"
                  :mempool-endpoint="mempoolEndpoint"
                  :sats-denominated="satsDenominated"
                ></onchain-fee-rate>
              </div>
            </div>
          </q-card-section>
        </q-card>

        <q-card class="q-mt-lg">
          <q-card-section>
            <div class="row items-center">
              <div class="col-12 col-sm-4">
                <q-toggle
                  :label="$t('onchain.show_coin_select')"
                  color="primary"
                  class="float-left"
                  v-model="showCoinSelect"
                ></q-toggle>
              </div>

              <div class="col-12 col-sm-8">
                <div class="float-right">
                  <span v-text="$t('onchain.balance_label')"></span>
                  <span class="text-subtitle2 q-ml-md">
                    {{ satBtc(balance) }}
                  </span>
                  <span
                    class="q-ml-lg"
                    v-text="$t('onchain.selected_label')"
                  ></span>
                  <span class="text-subtitle2 q-ml-md">
                    {{ satBtc(selectedAmount) }}
                  </span>
                </div>
              </div>
            </div>

            <div
              v-show="showCoinSelect"
              class="row items-center no-wrap q-mt-md"
            >
              <div class="col-12">
                <q-separator class="q-mb-md"></q-separator>
                <onchain-utxo-list
                  ref="utxoList"
                  :utxos="utxos"
                  :selectable="true"
                  :payed-amount="totalPayedAmount"
                  :mempool-endpoint="mempoolEndpoint"
                  :sats-denominated="satsDenominated"
                  :accounts="accounts"
                ></onchain-utxo-list>
              </div>
            </div>
          </q-card-section>
        </q-card>

        <q-card class="q-mt-lg">
          <q-card-section>
            <div class="row items-center">
              <div class="col-12 col-sm-4">
                <q-toggle
                  :label="$t('onchain.show_change')"
                  color="primary"
                  class="float-left"
                  v-model="showChange"
                ></q-toggle>
              </div>

              <div class="col-12 col-sm-4">
                <q-badge
                  v-if="changeAmount > 0 && changeAmount < DUST_LIMIT"
                  class="text-subtitle2 float-right"
                  color="yellow"
                  text-color="black"
                  v-text="$t('onchain.below_dust_limit_warning')"
                >
                </q-badge>
              </div>
              <div class="col-12 col-sm-4">
                <div class="float-right">
                  <span v-text="$t('onchain.change_label')"></span>
                  <span v-if="changeAmount < 0" class="text-subtitle2 q-ml-md">
                    {{ satBtc(0) }}
                  </span>
                  <span v-if="changeAmount >= 0" class="text-subtitle2 q-ml-md">
                    {{ satBtc(changeAmount) }}
                  </span>
                </div>
              </div>
            </div>

            <div v-show="showChange" class="row items-center no-wrap q-mt-md">
              <div class="col-12">
                <q-separator class="q-mb-md"></q-separator>
                <div class="row items-center">
                  <div
                    class="col-12 col-sm-2 q-pr-sm"
                    v-text="$t('onchain.change_account')"
                  ></div>
                  <div class="col-12 col-sm-3 q-pr-sm">
                    <q-select
                      filled
                      dense
                      emit-value
                      v-model="changeWallet"
                      :options="accounts"
                      @update:model-value="selectChangeAddress"
                      :rules="[val => !!val || $t('onchain.field_required')]"
                      :label="$t('onchain.wallet_account')"
                    ></q-select>
                  </div>
                  <div class="col-12 col-sm-7">
                    <q-input
                      filled
                      dense
                      readonly
                      v-model.trim="changeAddress.address"
                      :rules="[val => !!val || $t('onchain.field_required')]"
                      type="text"
                      :label="$t('onchain.change_address')"
                    ></q-input>
                  </div>
                </div>
              </div>
            </div>
          </q-card-section>
        </q-card>

        <div class="row items-center no-wrap q-mb-md q-pt-lg">
          <div class="col-auto">
            <q-btn
              unelevated
              color="primary"
              :disable="!canReview || showChecking"
              :loading="showChecking"
              :label="isHotWallet ? 'Review payment' : 'Sign with device'"
              @click="checkAndSend"
            ></q-btn>
            <q-btn
              v-if="!isHotWallet"
              flat
              label="Export PSBT"
              :disable="!canReview || showChecking"
              @click="showPsbtDialog"
              class="q-ml-sm"
            ></q-btn>
          </div>

          <div class="col">
            <q-spinner
              v-if="showChecking"
              size="2.55em"
              color="primary"
            ></q-spinner>
            <q-badge
              v-if="changeAmount < 0"
              class="text-subtitle2 float-right"
              color="yellow"
              text-color="black"
              v-text="$t('onchain.payed_amount_higher_warning')"
            >
            </q-badge>
          </div>
        </div>
      </fieldset>
    </q-form>
    <q-dialog v-model="showPsbt" position="top">
      <q-card class="q-pa-lg q-pt-xl">
        <q-input
          filled
          dense
          v-model.trim="psbtBase64"
          type="textarea"
          rows="25"
          cols="200"
          :label="$t('onchain.psbt_label')"
        ></q-input>

        <div class="row q-mt-lg">
          <q-btn
            v-close-popup
            flat
            color="grey"
            class="q-ml-auto"
            :label="$t('onchain.close')"
          ></q-btn>
        </div>
      </q-card>
    </q-dialog>

    <q-dialog v-model="showFinalTx" :persistent="showChecking" position="top">
      <q-card class="lnbits__dialog-card q-pa-lg">
        <h2 class="text-h6 q-mt-none">Review payment</h2>
        <p>
          Check the address and amount before sending on
          {{ network === 'Testnet' ? 'Testnet3' : network }}. Bitcoin payments
          cannot be reversed.
        </p>
        <template v-if="signedTx">
          <div
            v-for="(out, index) in signedTx.outputs"
            :key="index"
            class="q-py-md"
          >
            <div class="row items-center">
              <div class="col text-subtitle2">
                {{
                  addresses.some(a => a.address === out.address && a.isChange)
                    ? 'Change back to your wallet'
                    : 'Recipient'
                }}
              </div>
              <strong>{{ satBtc(out.amount) }}</strong>
            </div>
            <div class="onchain-address q-mt-xs">{{ out.address }}</div>
          </div>
          <q-separator></q-separator>
          <div class="row q-my-md">
            <span class="col">Network fee</span
            ><strong>{{ satBtc(signedTx.fee) }}</strong>
          </div>
          <q-expansion-item label="Transaction details" dense>
            <q-input
              filled
              readonly
              :model-value="signedTxHex"
              type="textarea"
              rows="3"
              label="Signed transaction"
            ></q-input>
          </q-expansion-item>
        </template>
        <div class="row q-mt-lg">
          <q-btn
            unelevated
            color="primary"
            label="Confirm and send"
            :loading="showChecking"
            :disable="!signedTxHex || showChecking"
            @click="broadcastTransaction"
          ></q-btn
          ><q-btn
            flat
            label="Back"
            class="q-ml-auto"
            v-close-popup
            :disable="showChecking"
          ></q-btn>
        </div>
      </q-card>
    </q-dialog>
  </div>
</template>

<template id="onchain-serial-signer">
  <div>
    <q-btn-dropdown
      split
      unelevated
      color="primary"
      icon="usb"
      label="Serial device"
      :text-color="
        connected ? (hww.authenticated ? 'green' : 'orange') : 'white'
      "
      :loading="isConnecting"
      :disable="closingSerialPort"
      @click="openSerialPortDialog"
    >
      <q-list>
        <q-item
          v-if="connected && !hww.authenticated"
          clickable
          v-close-popup
          @click="hwwShowPasswordDialog()"
        >
          <q-item-section>
            <q-item-label v-text="$t('onchain.login')"></q-item-label>
            <q-item-label caption v-text="$t('onchain.enter_password_hww')">
            </q-item-label>
          </q-item-section>
        </q-item>

        <q-item
          v-if="hww.authenticated"
          clickable
          v-close-popup
          @click="hwwLogout()"
        >
          <q-item-section>
            <q-item-label v-text="$t('onchain.logout')"></q-item-label>
            <q-item-label
              caption
              v-text="$t('onchain.clear_password_hww')"
            ></q-item-label>
          </q-item-section>
        </q-item>
        <q-item
          v-if="!selectedPort"
          clickable
          v-close-popup
          @click="openSerialPortConfig"
        >
          <q-item-section>
            <q-item-label
              v-text="$t('onchain.config_and_connect')"
            ></q-item-label>
            <q-item-label caption v-text="$t('onchain.set_serial_port_params')">
            </q-item-label>
          </q-item-section>
        </q-item>
        <q-item
          v-if="selectedPort"
          clickable
          v-close-popup
          @click="closeSerialPort()"
        >
          <q-item-section>
            <q-item-label v-text="$t('onchain.disconnect')"></q-item-label>
            <q-item-label
              caption
              v-text="$t('onchain.disconnect_from_serial')"
            ></q-item-label>
          </q-item-section>
        </q-item>

        <q-item
          v-if="connected"
          clickable
          v-close-popup
          @click="hwwShowRestoreDialog()"
        >
          <q-item-section>
            <q-item-label v-text="$t('onchain.restore')"></q-item-label>
            <q-item-label caption v-text="$t('onchain.restore_wallet_desc')">
            </q-item-label>
          </q-item-section>
        </q-item>
        <q-item
          v-if="hww.authenticated"
          clickable
          v-close-popup
          @click="hwwShowSeed()"
        >
          <q-item-section>
            <q-item-label v-text="$t('onchain.show_seed')"></q-item-label>
            <q-item-label caption v-text="$t('onchain.show_seed_desc')">
            </q-item-label>
          </q-item-section>
        </q-item>
        <q-item
          v-if="connected"
          @click="hwwShowWipeDialog()"
          clickable
          v-close-popup
        >
          <q-item-section>
            <q-item-label v-text="$t('onchain.wipe')"></q-item-label>
            <q-item-label caption v-text="$t('onchain.wipe_desc')">
            </q-item-label>
          </q-item-section>
        </q-item>
        <q-item
          v-if="connected"
          :disable="
            trng.running || hww.loggingIn || hww.sendingPsbt || hww.signingPsbt
          "
          @click="hwwTestTrng()"
          clickable
          v-close-popup
        >
          <q-item-section>
            <q-item-label v-text="$t('onchain.trng_check')"></q-item-label>
            <q-item-label
              caption
              v-text="$t('onchain.trng_check_desc')"
            ></q-item-label>
          </q-item-section>
        </q-item>
        <q-item v-if="connected" @click="hwwHelp()" clickable v-close-popup>
          <q-item-section>
            <q-item-label v-text="$t('onchain.help')"></q-item-label>
            <q-item-label
              caption
              v-text="$t('onchain.view_commands')"
            ></q-item-label>
          </q-item-section>
        </q-item>
        <q-item
          v-if="selectedPort"
          @click="showConsole = true"
          clickable
          v-close-popup
        >
          <q-item-section>
            <q-item-label v-text="$t('onchain.console')"></q-item-label>
            <q-item-label caption v-text="$t('onchain.serial_comm_messages')">
            </q-item-label>
          </q-item-section>
        </q-item>
      </q-list>
    </q-btn-dropdown>

    <q-dialog
      v-model="trng.showDialog"
      :persistent="trng.running"
      position="top"
    >
      <q-card class="q-pa-lg lnbits__dialog-card">
        <div class="text-h6 q-mb-md" v-text="$t('onchain.trng_result')"></div>
        <div v-if="trng.running" class="row items-center q-gutter-sm">
          <q-spinner color="primary" size="2em"></q-spinner>
          <span v-text="$t('onchain.trng_running')"></span>
        </div>
        <template v-else-if="trng.result">
          <q-banner
            :class="
              trng.result.looksHealthy
                ? 'bg-positive text-white'
                : 'bg-warning text-black'
            "
          >
            <span
              v-text="
                $t(
                  trng.result.looksHealthy
                    ? 'onchain.trng_healthy'
                    : 'onchain.trng_unexpected'
                )
              "
            ></span>
          </q-banner>
          <div class="q-markup-table q-my-md bg-transparent">
            <table class="q-table">
              <tbody>
                <tr>
                  <td v-text="$t('onchain.trng_samples')"></td>
                  <td v-text="trng.result.samples"></td>
                </tr>
                <tr>
                  <td v-text="$t('onchain.trng_expected')"></td>
                  <td>50</td>
                </tr>
                <tr>
                  <td v-text="$t('onchain.trng_range')"></td>
                  <td
                    v-text="
                      trng.result.minimumCount + '–' + trng.result.maximumCount
                    "
                  ></td>
                </tr>
                <tr>
                  <td v-text="$t('onchain.trng_chi_squared')"></td>
                  <td v-text="trng.result.chiSquared.toFixed(2)"></td>
                </tr>
              </tbody>
            </table>
          </div>
          <p class="text-weight-bold" v-text="$t('onchain.trng_interval')"></p>
          <p v-text="$t('onchain.trng_thresholds')"></p>
          <p v-text="$t('onchain.trng_limit')"></p>
          <p v-text="$t('onchain.trng_continue')"></p>
        </template>
        <template v-else-if="trng.error">
          <q-banner class="bg-warning text-black">
            <span v-text="$t('onchain.trng_failed')"></span>
            <div v-text="trng.error"></div>
          </q-banner>
          <p class="q-mt-md" v-text="$t('onchain.trng_firmware')"></p>
        </template>
        <div class="row justify-end q-mt-md">
          <q-btn
            v-close-popup
            flat
            color="grey"
            :disable="trng.running"
            :label="$t('onchain.close')"
          ></q-btn>
        </div>
      </q-card>
    </q-dialog>

    <q-dialog v-model="hww.showConfigDialog" position="top">
      <q-card class="q-pa-lg q-pt-xl lnbits__dialog-card">
        <q-form @submit="hwwConfigAndConnect" class="q-gutter-md">
          <span v-text="$t('onchain.enter_config')"></span>
          <onchain-serial-port-config
            ref="serialPortConfig"
            :config="config"
          ></onchain-serial-port-config>

          <div class="row q-mt-lg">
            <q-btn
              unelevated
              color="primary"
              type="submit"
              :label="$t('onchain.connect')"
            ></q-btn>
            <q-btn
              v-close-popup
              flat
              color="grey"
              class="q-ml-auto"
              :label="$t('onchain.cancel')"
            ></q-btn>
          </div>
        </q-form>
      </q-card>
    </q-dialog>

    <q-dialog
      v-model="hww.showPasswordDialog"
      :persistent="hww.loggingIn"
      @hide="passwordDialogClosed"
      position="top"
    >
      <q-card class="q-pa-lg q-pt-xl lnbits__dialog-card">
        <q-form @submit="hwwLogin" class="q-gutter-md">
          <span v-text="$t('onchain.enter_password_hww_full')"></span>
          <q-input
            filled
            dense
            v-model.trim="hww.password"
            type="password"
            :label="$t('onchain.password')"
          ></q-input>
          <q-separator></q-separator>
          <q-toggle
            :label="$t('onchain.passphrase_optional')"
            color="primary"
            v-model="hww.hasPassphrase"
          ></q-toggle>
          <q-input
            v-if="hww.hasPassphrase"
            v-model="hww.passphrase"
            filled
            :type="hww.showPassphrase ? 'text' : 'password'"
            dense
            :label="$t('onchain.passphrase')"
            :hint="$t('onchain.passphrase_hint')"
          >
            <template v-slot:append>
              <q-icon
                :name="hww.showPassphrase ? 'visibility' : 'visibility_off'"
                class="cursor-pointer"
                @click="hww.showPassphrase = !hww.showPassphrase"
              ></q-icon>
            </template>
          </q-input>

          <br />

          <div class="row q-mt-lg">
            <q-btn
              unelevated
              color="primary"
              :disable="!connected"
              :loading="hww.loggingIn"
              type="submit"
              :label="$t('onchain.login')"
            ></q-btn>
            <q-btn
              v-close-popup
              :disable="hww.loggingIn"
              flat
              color="grey"
              class="q-ml-auto"
              :label="$t('onchain.cancel')"
            ></q-btn>
          </div>
        </q-form>
      </q-card>
    </q-dialog>

    <q-dialog v-model="hww.showConfirmationDialog" persistent position="top">
      <q-card class="q-pa-lg q-pt-xl lnbits__dialog-card">
        <div class="q-gutter-md">
          <div
            v-if="tx && ['output', 'fee', 'sign'].includes(hww.confirm.stage)"
          >
            <div v-if="!hww.confirm.showFee" class="row q-mt-lg">
              <div class="col-12">
                <span class="text-subtitle2"
                  >Output {{ hww.confirm.outputIndex + 1 }}</span
                >
                <q-badge
                  v-if="tx.outputs[hww.confirm.outputIndex].branch_index === 1"
                  color="orange"
                  text-color="black"
                >
                  <span v-text="$t('onchain.change')"></span>
                </q-badge>
              </div>
            </div>
            <div v-if="!hww.confirm.showFee" class="row q-mt-lg">
              <div class="col-3">
                <span v-text="$t('onchain.address_colon')"></span>
              </div>
              <div class="col-9">
                <span class="text-wrap">{{
                  tx.outputs[hww.confirm.outputIndex].address
                }}</span>
              </div>
            </div>
            <div v-if="!hww.confirm.showFee" class="row q-mt-lg">
              <div class="col-3">
                <span v-text="$t('onchain.amount_label')"></span>
              </div>
              <div class="col-9">
                <span>{{
                  satBtc(tx.outputs[hww.confirm.outputIndex].amount)
                }}</span>
              </div>
            </div>
            <div v-if="hww.confirm.showFee" class="row q-mt-lg">
              <div class="col-3">
                <span v-text="$t('onchain.fee_label')"></span>
              </div>
              <div class="col-9">
                <span>{{ satBtc(tx.feeValue) }}</span>
              </div>
            </div>
            <div v-if="hww.confirm.showFee" class="row q-mt-lg">
              <div class="col-3">
                <span v-text="$t('onchain.fee_rate_label')"></span>
              </div>
              <div class="col-9">
                <span>{{ tx.feeRate }} sats/vbyte</span>
              </div>
            </div>
          </div>
          <div class="row q-mt-lg">
            <div class="col-12">
              <q-badge class="text-subtitle2" color="yellow" text-color="black">
                <span v-text="$t('onchain.bowser_review_on_device')"></span>
              </q-badge>
            </div>
          </div>
          <div class="row items-center q-gutter-sm q-mt-lg" role="status">
            <q-spinner color="primary"></q-spinner>
            <span>{{
              hww.confirm.stage === 'transfer'
                ? $t('onchain.bowser_transfer')
                : $t('onchain.bowser_physical_review')
            }}</span>
          </div>
        </div>
      </q-card>
    </q-dialog>

    <q-dialog
      v-model="hww.showWipeDialog"
      :persistent="hww.settingUp"
      @hide="clearSetupSecrets"
      position="top"
    >
      <q-card class="q-pa-lg q-pt-xl lnbits__dialog-card">
        <q-form @submit="hwwWipe" class="q-gutter-md">
          <q-badge
            color="pink"
            text-color="black"
            v-text="$t('onchain.wipe_warning')"
          >
          </q-badge>
          <span v-text="$t('onchain.enter_new_password_hww')"></span>
          <q-input
            filled
            dense
            v-model.trim="hww.password"
            type="password"
            :label="$t('onchain.password')"
          ></q-input>

          <q-input
            filled
            dense
            v-model.trim="hww.confirmedPassword"
            type="password"
            :label="$t('onchain.confirm_password')"
          ></q-input>
          <q-badge
            color="pink"
            text-color="black"
            v-text="$t('onchain.irreversible_warning')"
          >
          </q-badge>

          <div class="row q-mt-lg">
            <q-btn
              unelevated
              color="primary"
              :loading="hww.settingUp"
              :disable="
                hww.settingUp ||
                !hww.password ||
                hww.password.length < 8 ||
                hww.password !== hww.confirmedPassword
              "
              type="submit"
              :label="$t('onchain.wipe')"
            ></q-btn>
            <q-btn
              v-close-popup
              :disable="hww.settingUp"
              flat
              color="grey"
              class="q-ml-auto"
              :label="$t('onchain.cancel')"
            ></q-btn>
          </div>
        </q-form>
      </q-card>
    </q-dialog>

    <q-dialog v-model="showConsole" position="top">
      <q-card class="q-pa-lg q-pt-xl">
        <q-input
          filled
          dense
          for="serial-port-console"
          v-model.trim="receivedData"
          type="textarea"
          rows="25"
          cols="200"
          :label="$t('onchain.console')"
        ></q-input>

        <div class="row q-mt-lg">
          <q-btn
            v-close-popup
            flat
            color="grey"
            class="q-ml-auto"
            :label="$t('onchain.close')"
          ></q-btn>
        </div>
      </q-card>
    </q-dialog>

    <q-dialog v-model="showConsole" position="top">
      <q-card class="q-pa-lg q-pt-xl">
        <div class="row q-mt-lg q-mb-lg">
          <div class="col">
            <q-badge
              class="text-subtitle2 float-right"
              color="yellow"
              text-color="black"
              v-text="$t('onchain.open_dev_console_warning')"
            >
            </q-badge>
          </div>
        </div>

        <q-input
          filled
          dense
          for="serial-port-console"
          v-model.trim="receivedData"
          type="textarea"
          rows="25"
          cols="200"
          :label="$t('onchain.console')"
        ></q-input>
        <div class="row q-mt-lg">
          <q-btn
            v-close-popup
            flat
            color="grey"
            class="q-ml-auto"
            :label="$t('onchain.close')"
          ></q-btn>
        </div>
      </q-card>
    </q-dialog>

    <q-dialog
      v-model="hww.showSeedDialog"
      @hide="closeSeedDialog"
      position="top"
    >
      <q-card class="q-pa-lg q-pt-xl">
        <span
          v-text="
            $t('onchain.check_word_position', {
              position: hww.seedWordPosition
            })
          "
        ></span>
        <p class="q-mt-lg" v-text="$t('onchain.bowser_seed_display')"></p>

        <div class="row q-mt-lg">
          <div class="col-4">
            <q-btn
              v-if="hww.seedWordPosition !== 1"
              unelevated
              color="primary"
              @click="showPrevSeedWord"
              :disable="hww.seedLoading"
              :label="$t('onchain.prev')"
            ></q-btn>
          </div>
          <div class="col-4">
            <q-btn
              v-if="hww.seedWordPosition !== 24"
              unelevated
              color="primary"
              @click="showNextSeedWord"
              :disable="hww.seedLoading"
              :label="$t('onchain.next')"
            ></q-btn>
          </div>
          <div class="col-4">
            <q-btn
              v-close-popup
              flat
              color="grey"
              class="q-ml-auto"
              :label="$t('onchain.close')"
            ></q-btn>
          </div>
        </div>
      </q-card>
    </q-dialog>

    <q-dialog
      v-model="hww.showRestoreDialog"
      :persistent="hww.settingUp"
      @hide="clearSetupSecrets"
      position="top"
    >
      <q-card class="q-pa-lg q-pt-xl lnbits__dialog-card">
        <q-form @submit="hwwRestore" class="q-gutter-md">
          <q-badge
            color="pink"
            text-color="black"
            class="text-subtitle2"
            multi-line
            v-text="$t('onchain.test_only_warning')"
          >
          </q-badge>
          <br />
          <q-toggle
            :label="$t('onchain.enter_word_list_space')"
            color="primary"
            v-model="hww.quickMnemonicInput"
          ></q-toggle>
          <br />

          <div v-if="hww.quickMnemonicInput">
            <q-input
              v-model.trim="hww.mnemonic"
              filled
              :type="hww.showMnemonic ? 'text' : 'password'"
              dense
              :label="$t('onchain.word_list')"
            >
              <template v-slot:append>
                <q-icon
                  :name="hww.showMnemonic ? 'visibility' : 'visibility_off'"
                  class="cursor-pointer"
                  @click="hww.showMnemonic = !hww.showMnemonic"
                ></q-icon>
              </template>
            </q-input>
          </div>

          <onchain-seed-input
            v-else
            @on-seed-input-done="seedInputDone"
          ></onchain-seed-input>
          <br />
          <q-separator></q-separator>
          <br />
          <span v-text="$t('onchain.enter_new_password_short')"></span>
          <q-input
            v-model.trim="hww.password"
            filled
            :type="hww.showPassword ? 'text' : 'password'"
            dense
            :label="$t('onchain.new_password')"
          >
            <template v-slot:append>
              <q-icon
                :name="hww.showPassword ? 'visibility' : 'visibility_off'"
                class="cursor-pointer"
                @click="hww.showPassword = !hww.showPassword"
              ></q-icon>
            </template>
          </q-input>

          <q-input
            filled
            dense
            v-model.trim="hww.confirmedPassword"
            type="password"
            :label="$t('onchain.confirm_password')"
          ></q-input>
          <br />
          <q-separator></q-separator>
          <q-badge
            color="pink"
            text-color="black"
            class="text-subtitle2"
            multi-line
            v-text="$t('onchain.all_data_lost_warning')"
          >
          </q-badge>

          <div class="row q-mt-lg">
            <q-btn
              unelevated
              color="primary"
              :loading="hww.settingUp"
              :disable="
                hww.settingUp ||
                !hww.mnemonic ||
                !hww.password ||
                hww.password.length < 8 ||
                hww.password !== hww.confirmedPassword
              "
              type="submit"
              :label="$t('onchain.restore')"
            ></q-btn>
            <q-btn
              v-close-popup
              :disable="hww.settingUp"
              flat
              color="grey"
              class="q-ml-auto"
              :label="$t('onchain.cancel')"
            ></q-btn>
          </div>
        </q-form>
      </q-card>
    </q-dialog>
  </div>
</template>

<template id="onchain-trezor-signer">
  <div>
    <q-btn
      @click="connectToDevice"
      split
      unelevated
      color="primary"
      :text-color="connected ? 'green' : ''"
      :label="connected ? 'Trezor connected' : 'Connect Trezor'"
    >
      <q-spinner v-if="isConnecting" color="secondary"></q-spinner>
    </q-btn>

    <q-btn
      v-if="connected"
      flat
      dense
      round
      icon="info"
      aria-label="Trezor device details"
      @click="showFeatures = true"
    ></q-btn>
    <q-dialog v-model="showFeatures" position="top">
      <q-card v-if="features" class="q-pa-lg q-pt-md">
        <q-card-section>
          <h5
            v-text="
              $t('onchain.connected_to_trezor', {
                label: features.payload.label
              })
            "
          ></h5>
          <q-input
            filled
            dense
            for="serial-port-console"
            v-model.trim="featuresJson"
            type="textarea"
            rows="20"
            cols="200"
            :label="$t('onchain.device_features')"
          ></q-input>
        </q-card-section>

        <q-card-section>
          <div class="row q-mt-lg">
            <q-btn
              v-close-popup
              flat
              color="grey"
              class="q-ml-auto"
              :label="$t('onchain.close')"
            ></q-btn>
          </div>
        </q-card-section>
      </q-card>
    </q-dialog>
  </div>
</template>

<template id="onchain-serial-port-config">
  <div>
    <div class="row q-mt-md">
      <div class="col-12">
        <q-input
          filled
          dense
          v-model.trim="config.name"
          :label="$t('onchain.name_optional')"
        ></q-input>
      </div>
    </div>
    <q-separator class="q-mt-sm"></q-separator>
    <div class="row q-mt-md">
      <div class="col-12">
        <q-input
          filled
          dense
          v-model.trim="config.baudRate"
          type="number"
          :label="$t('onchain.baud_rate')"
        ></q-input>
      </div>
    </div>
    <div class="row q-mt-md">
      <div class="col-12">
        <q-input
          filled
          dense
          v-model.trim="config.bufferSize"
          type="number"
          :label="$t('onchain.buffer_size')"
        ></q-input>
      </div>
    </div>
    <div class="row q-mt-md">
      <div class="col-12">
        <q-input
          filled
          dense
          v-model.trim="config.flowControl"
          :label="$t('onchain.flow_control')"
        ></q-input>
      </div>
    </div>
    <div class="row q-mt-md">
      <div class="col-12">
        <q-input
          filled
          dense
          v-model.trim="config.parity"
          :label="$t('onchain.parity')"
        ></q-input>
      </div>
    </div>
    <div class="row q-mt-md">
      <div class="col-12">
        <q-input
          filled
          dense
          v-model.trim="config.dataBits"
          type="number"
          :label="$t('onchain.data_bits')"
        ></q-input>
      </div>
    </div>

    <div class="row q-mt-md">
      <div class="col-12">
        <q-input
          filled
          dense
          v-model.trim="config.stopBits"
          type="number"
          :label="$t('onchain.stop_bits')"
        ></q-input>
      </div>
    </div>
  </div>
</template>

<template id="onchain-hot-wallet">
  <q-dialog v-model="show" :persistent="busy" @hide="resetSecrets">
    <q-card
      class="lnbits__dialog-card q-pa-lg"
      :style="mode === 'backup' ? {width: '760px', maxWidth: '95vw'} : {}"
    >
      <h2 class="text-h6 q-mt-none">
        {{
          mode === 'backup' ? 'Back up ' + wallet.title : 'Add a server wallet'
        }}
      </h2>
      <q-banner
        v-if="error"
        class="bg-red-1 text-negative q-mb-md"
        role="alert"
        >{{ error }}</q-banner
      >
      <template v-if="mode !== 'backup'">
        <q-linear-progress
          v-if="available === null && !error"
          indeterminate
        ></q-linear-progress>
        <q-banner v-if="available === false"
          >Server wallets are not enabled on this instance. Ask the
          administrator to enable onchain payments and complete key backup in
          Settings → Payments. Hardware and watch-only wallets are
          available.</q-banner
        >
        <q-form v-if="available" @submit="createWallet" class="q-gutter-md">
          <p>
            This LNbits server holds your private keys and can spend your
            bitcoin. Only use a server you trust. Your recovery phrase lets you
            recover independently.
          </p>
          <q-btn-toggle
            v-model="mode"
            no-caps
            spread
            unelevated
            toggle-color="primary"
            :options="[
              {label: 'Create wallet', value: 'create'},
              {label: 'Restore wallet', value: 'restore'}
            ]"
            :disable="busy"
          ></q-btn-toggle>
          <q-input
            filled
            v-model="title"
            label="Wallet name"
            maxlength="100"
            :disable="busy"
            :rules="[v => !!v.trim() || 'Enter a name']"
            autofocus
          ></q-input>
          <template v-if="mode === 'restore'">
            <q-banner dense
              >Restore only a phrase you intend this server to control. This
              restores Native SegWit, account 0, with no BIP39 passphrase. Never
              enter a hardware wallet's recovery phrase here.</q-banner
            >
            <q-input
              filled
              v-model="mnemonic"
              type="password"
              autocomplete="off"
              spellcheck="false"
              label="Recovery phrase"
              :disable="busy"
              :rules="[v => !!v.trim() || 'Enter the recovery phrase']"
            ></q-input>
          </template>
          <div class="row">
            <q-btn
              type="submit"
              color="primary"
              unelevated
              :loading="busy"
              :label="mode === 'restore' ? 'Restore wallet' : 'Create wallet'"
            ></q-btn
            ><q-btn
              flat
              label="Cancel"
              class="q-ml-auto"
              v-close-popup
              :disable="busy"
            ></q-btn>
          </div>
        </q-form>
        <q-btn v-else flat label="Close" class="q-mt-md" v-close-popup></q-btn>
      </template>
      <template v-else>
        <div class="row q-col-gutter-sm q-mb-md" aria-label="Backup progress">
          <div class="col-6">
            <q-chip
              square
              class="full-width"
              icon="looks_one"
              :color="backupStep === 1 ? 'primary' : 'grey-9'"
              text-color="white"
              label="Backup"
            ></q-chip>
          </div>
          <div class="col-6">
            <q-chip
              square
              class="full-width"
              icon="looks_two"
              :color="backupStep === 2 ? 'primary' : 'grey-9'"
              text-color="white"
              label="Verify"
            ></q-chip>
          </div>
        </div>
        <q-separator class="q-mb-lg"></q-separator>
        <template v-if="backupStep === 1">
          <div class="row items-center justify-between q-gutter-sm q-mb-md">
            <div>
              <div class="text-subtitle1">
                {{
                  phrase
                    ? seedWords.length + '-word recovery phrase'
                    : 'Recovery phrase'
                }}
              </div>
              <div class="text-caption text-grey">
                Write these words down in order.
              </div>
            </div>
            <q-btn
              outline
              no-caps
              color="primary"
              :icon="wordsVisible ? 'visibility_off' : 'visibility'"
              :label="wordsVisible ? 'Hide words' : 'Show words'"
              :loading="busy"
              @click="revealBackup"
            ></q-btn>
          </div>
          <div class="onchain-secret">
            <div
              v-for="word in seedWords"
              :key="word.index"
              class="row items-center no-wrap rounded-borders"
            >
              <div
                class="onchain-word-number text-caption text-grey text-center"
              >
                {{ word.index + 1 }}
              </div>
              <div class="onchain-word text-body2 text-weight-medium q-px-sm">
                {{ wordsVisible ? word.word : '••••••' }}
              </div>
            </div>
          </div>
          <p class="text-caption text-grey q-mt-md">
            Anyone with this phrase can spend your bitcoin. Keep your backup
            somewhere private.
          </p>
          <p class="text-caption text-grey">
            Recovery: Native SegWit · {{ wallet.network }} ·
            {{ wallet.network === 'Mainnet' ? "m/84'/0'/0'" : "m/84'/1'/0'" }} ·
            no passphrase
          </p>
          <div class="row justify-between q-mt-lg">
            <q-btn
              flat
              no-caps
              label="Close"
              v-close-popup
              :disable="busy"
            ></q-btn>
            <q-btn
              color="primary"
              no-caps
              label="I have written it down"
              :disable="!phrase || busy"
              @click="prepareChallenge"
            ></q-btn>
          </div>
        </template>
        <q-form v-else @submit="confirmBackup" autocomplete="off">
          <div class="text-subtitle1">Confirm your backup</div>
          <div class="text-caption text-grey q-mb-md">
            Enter the requested words from your written recovery phrase.
          </div>
          <div class="row q-col-gutter-md">
            <div
              class="col-12 col-sm-6"
              v-for="index in challenge"
              :key="index"
            >
              <q-input
                dense
                filled
                v-model.trim="answers[index]"
                :label="`Word ${index + 1}`"
                autocomplete="off"
                autocapitalize="none"
                spellcheck="false"
                :disable="busy"
              ></q-input>
            </div>
          </div>
          <div class="row justify-between q-mt-lg">
            <q-btn
              flat
              no-caps
              label="Back"
              :disable="busy"
              @click="backToWords"
            ></q-btn>
            <q-btn
              color="primary"
              icon="check"
              no-caps
              label="Confirm backup"
              type="submit"
              :loading="busy"
            ></q-btn>
          </div>
        </q-form>
      </template>
    </q-card>
  </q-dialog>
</template>

<style>
.onchain-wallet .onchain-balance {
  font-size: clamp(1.6rem, 7vw, 3rem);
  overflow-wrap: anywhere;
}
.onchain-activity-table .onchain-activity-description {
  white-space: normal;
}
.onchain-transaction-link {
  color: inherit;
  text-decoration: none;
}
.onchain-activity-addresses a {
  display: block;
  font-size: 11px;
  overflow-wrap: anywhere;
}
.onchain-transaction-link:hover {
  text-decoration: underline;
}
.onchain-wallet .q-tab-panel {
  overflow-x: auto;
}
.onchain-wallet .q-item__section--main {
  min-width: 0;
}
.onchain-secret {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
}
.onchain-secret > div {
  min-height: 42px;
  border: 1px solid rgba(128, 128, 128, 0.3);
  background: rgba(128, 128, 128, 0.035);
}
.onchain-word-number {
  flex: 0 0 36px;
  border-right: 1px solid rgba(128, 128, 128, 0.2);
}
.onchain-word {
  min-width: 0;
  overflow-wrap: anywhere;
}
@media (max-width: 599px) {
  .onchain-secret {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
  .onchain-word-number {
    flex-basis: 24px;
  }
}
.onchain-address {
  overflow-wrap: anywhere;
  font-family: monospace;
}
.btn-full {
  width: 100%;
}
</style>
