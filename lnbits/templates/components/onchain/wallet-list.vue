<template id="onchain-wallet-list">
  <div v-if="loading || fetchError">
    <q-linear-progress v-if="loading" indeterminate></q-linear-progress>
    <q-banner v-if="fetchError"
      >Could not load wallet.<template v-slot:action
        ><q-btn
          flat
          label="Retry"
          @click="refreshWalletAccounts"
        ></q-btn></template
    ></q-banner>
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
            ><q-item-label>Hot Wallet</q-item-label
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
                : !formDialog.data.masterpub?.trim()) || showCreating
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
