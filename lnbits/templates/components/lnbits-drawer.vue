<template id="lnbits-drawer">
  <q-drawer
    v-model="g.visibleDrawer"
    side="left"
    :width="$q.screen.lt.md ? 260 : 230"
    show-if-above
    :elevated="$q.screen.lt.md"
  >
    <q-scroll-area style="height: 100%">
      <q-item>
        <q-item-section class="cursor-pointer" @click="goToWallets()">
          <q-item-label
            :style="$q.dark.isActive ? 'color:rgba(255, 255, 255, 0.64)' : ''"
            class="q-item__label q-item__label--header q-pa-none"
            header
            v-text="$t('wallets') + ' (' + g.user.wallets.length + ')'"
          ></q-item-label>
        </q-item-section>
        <q-item-section side>
          <q-btn
            flat
            :icon="g.walletFlip ? 'view_list' : 'view_column'"
            color="grey"
            class=""
            @click="flipWallets($q.screen.lt.md)"
          >
            <q-tooltip
              ><span
                v-text="g.walletFlip ? $t('view_list') : $t('view_column')"
              ></span
            ></q-tooltip>
          </q-btn>
        </q-item-section>
      </q-item>
      <lnbits-wallet-list
        v-if="!g.walletFlip"
        :balance="balance"
        @wallet-action="handleWalletAction"
      ></lnbits-wallet-list>
      <lnbits-manage></lnbits-manage>
      <lnbits-extension-list class="q-pb-xl"></lnbits-extension-list>
    </q-scroll-area>
  </q-drawer>
</template>
