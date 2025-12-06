<template id="lnbits-wallet-new">
  <q-dialog v-model="showNewWalletDialog" position="top">
    <q-card class="q-pa-lg q-pt-md lnbits__dialog-card">
      <q-card-section>
        <div class="text-h6">
          <span v-text="$t('add_new_wallet')"></span>
        </div>
      </q-card-section>
      <q-card-section v-if="g.user.walletInvitesCount">
        <q-badge
          @click="g.newWalletType = 'lightning-shared'"
          class="cursor-pointer"
        >
          <span
            v-text="
              'You have ' +
              g.user.walletInvitesCount +
              ' wallet invitation' +
              (g.user.walletInvitesCount > 1 ? 's' : '')
            "
          ></span>
        </q-badge>
      </q-card-section>

      <q-card-section class="q-pt-none">
        <q-select
          v-if="walletTypes.length > 1"
          :options="walletTypes"
          emit-value
          map-options
          :label="$t('wallet_type')"
          v-model="g.newWalletType"
          dense
        ></q-select>
        <q-input
          v-if="isLightning"
          dense
          v-model="wallet.name"
          :label="$t('wallet_name')"
          autofocus
          @keyup.enter="submitAddWallet()"
          class="q-mt-md"
        ></q-input>
        <q-select
          v-if="isLightningShared"
          v-model="wallet.sharedWalletId"
          :label="$t('shared_wallet_id')"
          emit-value
          map-options
          dense
          :options="inviteWalletOptions"
          class="q-mt-md"
        ></q-select>
        <div v-if="isLightningShared" class="q-mt-md">
          <span v-text="$t('shared_wallet_desc')" class="q-mt-lg"></span>
        </div>
      </q-card-section>

      <q-card-actions class="text-primary">
        <div class="row full-width">
          <div class="col-md-4">
            <q-btn
              flat
              :label="$t('cancel')"
              class="float-left"
              v-close-popup
            ></q-btn>
          </div>
          <div class="col-md-4">
            <q-btn
              v-if="isLightningShared"
              :disabled="!wallet.sharedWalletId"
              flat
              :label="$t('reject_wallet')"
              v-close-popup
              color="negative"
              @click="submitRejectWalletInvitation()"
            ></q-btn>
            <span v-else></span>
          </div>
          <div class="col-md-4">
            <q-btn
              flat
              :label="$t('add_wallet')"
              v-close-popup
              @click="submitAddWallet()"
              class="float-right"
            ></q-btn>
          </div>
        </div>
      </q-card-actions>
    </q-card>
  </q-dialog>
</template>
