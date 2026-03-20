<template id="lnbits-wallet-new">
  <lnbits-dialog
    :show="showNewWalletDialog"
    :title="$t('add_new_wallet')"
    :action="{
      label: $t('add_wallet'),
      closePopup: true
    }"
    :secondary-action="
      isLightningShared
        ? {
            label: $t('reject_wallet'),
            color: 'negative',
            closePopup: true
          }
        : null
    "
    @update:show="showNewWalletDialog = $event"
    @action="submitAddWallet"
    @secondary-action="submitRejectWalletInvitation"
  >
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
  </lnbits-dialog>
</template>
