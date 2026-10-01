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
              wallet.onchain_wallet_kind === 'hot'
                ? 'account_balance_wallet'
                : wallet.onchain_meta?.xpub
                  ? 'usb'
                  : 'visibility'
            "
          ></q-icon
        ></q-item-section>
        <q-item-section
          ><q-item-label class="row items-center q-gutter-x-sm">
            <span v-text="wallet.name"></span>
            <q-badge
              outline
              :color="network === 'Mainnet' ? 'primary' : 'orange'"
            >
              <span
                v-text="network === 'Testnet' ? 'Testnet3' : network"
              ></span> </q-badge></q-item-label
          ><q-item-label caption
            ><span
              v-text="
                wallet.onchain_wallet_kind === 'hot'
                  ? 'Server wallet'
                  : wallet.onchain_meta?.xpub
                    ? 'Hardware wallet'
                    : 'Watch-only'
              "
            ></span></q-item-label
        ></q-item-section>
        <q-item-section side
          ><span v-text="getAmmountForWallet(wallet.id)"></span
        ></q-item-section>
        <q-item-section side
          ><q-btn
            flat
            round
            dense
            icon="more_vert"
            :aria-label="'Manage ' + wallet.name"
            @click.stop
            ><q-menu auto-close
              ><q-list style="min-width: 180px">
                <q-item
                  clickable
                  @click="openQrCodeDialog(wallet.onchain_meta.masterpub)"
                  ><q-item-section
                    >Export public descriptor</q-item-section
                  ></q-item
                >
                <q-item
                  v-if="wallet.onchain_wallet_kind === 'hot'"
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
        <span v-text="network === 'Testnet' ? 'Testnet3' : network"></span>
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
          <span v-text="network === 'Testnet' ? 'Testnet3' : network"></span>.
          To use another Bitcoin wallet, create another LNbits onchain wallet.
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
