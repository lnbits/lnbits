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
        <q-item-section
          class="cursor-pointer"
          @click="$router.push('/wallets')"
        >
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
            @click="g.walletFlip = !g.walletFlip"
          >
            <q-tooltip
              ><span
                v-text="g.walletFlip ? $t('view_list') : $t('view_column')"
              ></span
            ></q-tooltip>
          </q-btn>
        </q-item-section>
      </q-item>
      <lnbits-manage-wallet-list></lnbits-manage-wallet-list>
      <lnbits-manage></lnbits-manage>
      <lnbits-manage-extension-list
        class="q-pb-xl"
      ></lnbits-manage-extension-list>
    </q-scroll-area>
  </q-drawer>
</template>
