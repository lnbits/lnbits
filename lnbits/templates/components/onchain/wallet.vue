<template id="lnbits-onchain-wallet">
  <div v-if="g.user.wallets.length" class="row q-col-gutter-md">
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
                <div
                  class="text-h3 text-weight-bold text-wrap"
                  v-text="
                    g.isFiatPriority && hasFiatRate
                      ? selectedFiat
                      : balanceLabel
                  "
                ></div>
                <div
                  v-if="hasFiatRate"
                  class="text-h5 text-italic"
                  style="opacity: 0.75"
                  v-text="g.isFiatPriority ? balanceLabel : selectedFiat"
                ></div>
              </div>
              <div
                v-if="hasFiatRate && $q.screen.gt.sm"
                class="text-right text-bold text-italic"
              >
                BTC Price<br /><span
                  v-text="
                    utils.formatCurrency(g.exchangeRate, g.wallet.currency)
                  "
                ></span>
              </div>
            </div>
            <div
              class="text-caption text-grey q-mb-md"
              role="status"
              aria-live="polite"
            >
              <span v-text="walletKindLabel"></span> ·
              <span
                v-text="
                  scan.scanning
                    ? 'Updating balance…'
                    : syncError
                      ? 'Update failed — balance may be out of date'
                      : lastSynced
                        ? 'Updated ' + lastSynced
                        : 'Balance has not been checked'
                "
              ></span>
              <span v-if="pendingBalance">
                ·
                <span v-text="formatAmount(pendingBalance)"></span>
                pending</span
              >
            </div>
            <q-banner
              v-if="
                selectedWallet.onchain_wallet_kind === 'hot' &&
                !selectedWallet.onchain_backup_confirmed
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
                v-if="!showPayment"
                unelevated
                color="primary"
                icon="file_upload"
                label="Send"
                :disable="!canTransact || !selectedUtxos.length"
                @click="goToPaymentView"
              ></q-btn>
              <q-btn
                v-else
                unelevated
                color="negative"
                icon="close"
                label="Cancel Send"
                :disable="$refs.paymentRef?.showChecking"
                @click="showPayment = false"
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
              Create a hot wallet, connect a hardware wallet, or follow an
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
        <q-tabs v-model="tab" active-color="primary" align="justify" no-caps>
          <q-tab name="history" label="Activity" class="col-4"></q-tab>
          <q-tab name="addresses" label="Addresses" class="col-4"></q-tab>
          <q-tab name="utxos" label="Coins" class="col-4"></q-tab>
        </q-tabs>
        <q-separator></q-separator>
        <q-tab-panels v-model="tab">
          <q-tab-panel name="history" class="q-pa-md scroll">
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
              wrap-cells
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
                  <q-th v-for="col in props.cols" :key="col.name" :props="props"
                    ><span v-text="col.label"></span
                  ></q-th>
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
                      ><q-tooltip
                        ><span
                          v-text="
                            props.row.confirmed
                              ? 'Confirmed'
                              : 'Pending confirmation'
                          "
                        ></span></q-tooltip
                    ></q-icon>
                  </q-td>
                  <q-td key="time" :props="props" class="text-wrap">
                    <a
                      class="inherit"
                      :href="mempoolHostname + '/tx/' + props.row.txId"
                      target="_blank"
                      rel="noopener noreferrer"
                      :aria-label="'View transaction ' + props.row.txId"
                      ><span
                        v-text="
                          props.row.amount < 0
                            ? 'Sent bitcoin'
                            : 'Received bitcoin'
                        "
                      ></span>
                      <q-tooltip
                        ><span v-text="props.row.txId"></span
                      ></q-tooltip> </a
                    ><br />
                    <div v-if="props.row.transactionAddresses.length">
                      <a
                        v-for="address in props.row.transactionAddresses"
                        :key="address"
                        class="inherit block text-caption text-grey text-wrap"
                        :href="mempoolHostname + '/address/' + address"
                        :aria-label="'View address ' + address"
                        :title="address"
                        target="_blank"
                        rel="noopener noreferrer"
                        ><span
                          v-text="props.row.amount < 0 ? 'To' : 'On'"
                        ></span>
                        <span v-text="shortActivityAddress(address)"></span
                        ><q-tooltip><span v-text="address"></span></q-tooltip
                      ></a>
                    </div>
                    <i
                      class="text-grey"
                      :title="
                        props.row.confirmed
                          ? props.row.date
                          : 'Time since first seen by this wallet'
                      "
                      v-text="activityDate(props.row)"
                    ></i>
                    <span
                      v-if="!props.row.confirmed && props.row.firstSeen"
                      class="text-grey"
                    >
                      · Pending</span
                    >
                  </q-td>
                  <q-td
                    key="amount"
                    :props="props"
                    class="text-right text-no-wrap"
                  >
                    <span
                      v-text="formatActivityAmount(props.row.amount)"
                    ></span>
                    <div v-if="hasFiatRate" class="text-italic text-caption">
                      <span
                        v-text="
                          utils.formatCurrency(
                            (Math.abs(props.row.amount) * g.exchangeRate) /
                              100000000,
                            g.wallet.currency
                          )
                        "
                      ></span
                      ><q-tooltip>At the current exchange rate</q-tooltip>
                    </div>
                  </q-td>
                </q-tr>
              </template>
              <template v-slot:no-data>
                <div class="full-width text-center q-pa-lg">
                  <q-icon name="receipt" size="32px" class="q-mb-sm"></q-icon>
                  <div
                    v-text="
                      scan.scanning
                        ? 'Looking for transactions…'
                        : historyFilter
                          ? 'No matching transactions'
                          : 'No transactions yet'
                    "
                  ></div>
                  <div
                    class="text-caption q-mt-sm"
                    v-text="
                      historyFilter
                        ? 'Try a different transaction, address or amount.'
                        : 'Receive bitcoin to get started.'
                    "
                  ></div>
                </div>
              </template>
            </q-table>
          </q-tab-panel>
          <q-tab-panel name="addresses" class="scroll">
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
          <q-tab-panel name="utxos" class="scroll">
            <onchain-utxo-list
              :utxos="selectedUtxos"
              :mempool-endpoint="mempoolHostname"
              :sats-denominated="config.sats_denominated"
              :filter="utxosFilter"
            ></onchain-utxo-list>
          </q-tab-panel>
        </q-tab-panels>
      </q-card>
      <div v-if="showPayment && selectedWallet">
        <h2 class="text-h6 q-my-none">Send bitcoin</h2>
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
            :network="config.network"
            :addresses="addresses"
            :serial-signer-ref="signerDevice"
            :busy="showPayment"
            @accounts-update="updateAccounts"
            @new-receive-address="showAddressDetailsWithConfirmation"
            @create-hot="$refs.hotWallet.openCreate()"
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
          <q-expansion-item group="extras" label="Advanced" icon="tune">
            <q-card-section class="column items-stretch q-gutter-y-sm">
              <q-btn
                outline
                color="primary"
                label="Import signed PSBT"
                :disable="!isConfigured || showPayment"
                @click="openImportPsbt"
              ></q-btn>
              <q-btn
                outline
                color="primary"
                label="Export public key descriptor"
                :disable="
                  !isConfigured || showPayment || $refs.walletList?.loading
                "
                @click="
                  $refs.walletList.openQrCodeDialog(
                    selectedWallet.onchain_meta.masterpub
                  )
                "
              ></q-btn>
              <q-btn
                v-if="
                  !isConfigured || selectedWallet.onchain_wallet_kind === 'hot'
                "
                outline
                color="primary"
                label="Back up recovery phrase"
                :disable="
                  !isConfigured || showPayment || $refs.walletList?.loading
                "
                @click="$refs.hotWallet.openBackup(selectedWallet)"
              ></q-btn>
              <q-btn
                v-if="
                  isConfigured && selectedWallet.onchain_wallet_kind === 'watch'
                "
                unelevated
                color="primary"
                label="Remove wallet"
                :disable="showPayment || $refs.walletList?.loading"
                @click="$refs.walletList.deleteWalletAccount(selectedWallet.id)"
              ></q-btn>
            </q-card-section>
            <q-expansion-item
              v-if="isConfigured && walletDetails.length"
              label="Wallet details"
              icon="info_outline"
            >
              <q-card-section class="q-gutter-y-md">
                <q-input
                  v-for="field in walletDetails"
                  :key="field.label"
                  filled
                  dense
                  readonly
                  :label="field.label"
                  :model-value="field.value"
                  :type="field.multiline ? 'textarea' : 'text'"
                  :autogrow="field.multiline"
                >
                  <template v-slot:append>
                    <q-btn
                      flat
                      round
                      dense
                      icon="content_copy"
                      :aria-label="'Copy ' + field.label.toLowerCase()"
                      @click="utils.copyText(field.value)"
                    ></q-btn>
                  </template>
                </q-input>
              </q-card-section>
            </q-expansion-item>
          </q-expansion-item>
          <q-separator></q-separator>
        </template>
      </lnbits-wallet-extra>
      <slot v-if="isConfigured" name="wallet-tools"></slot>
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
          <span
            v-text="config.network === 'Testnet' ? 'Testnet3' : config.network"
          ></span>
          to this address.
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
