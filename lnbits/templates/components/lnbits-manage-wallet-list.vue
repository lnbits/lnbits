<template id="lnbits-manage-wallet-list">
  <q-list
    v-if="g.user && g.user.wallets.length && !g.walletFlip"
    dense
    class="lnbits-drawer__q-list"
  >
    <q-item
      v-for="walletRec in g.user.wallets.slice(0, maxWallets)"
      :key="walletRec.id"
      clickable
      :active="walletRec.id === activeWalletId"
      @click="$router.push('/wallet/' + walletRec.id)"
    >
      <q-item-section side>
        <q-avatar
          size="lg"
          :text-color="$q.dark.isActive ? 'black' : 'grey-3'"
          :disabled="walletRec.id === activeWalletId"
          :color="walletRec.extra.color"
          :icon="walletRec.extra.icon"
        >
        </q-avatar>
      </q-item-section>
      <q-item-section
        style="max-width: 100px"
        class="q-my-none ellipsis full-width"
      >
        <q-item-label lines="1"
          ><span v-text="walletRec.name"></span
        ></q-item-label>
        <q-item-label class="q-my-none ellipsis full-width" caption>
          <strong
            v-text="utils.formatBalance(walletRec.sat, g.denomination)"
          ></strong>
        </q-item-label>
      </q-item-section>
      <q-item-section
        v-if="walletRec.walletType == 'lightning-shared'"
        side
        top
      >
        <q-icon name="group" :color="walletRec.extra.color" size="xs"></q-icon>
      </q-item-section>
      <q-item-section side v-show="walletRec.id === activeWalletId">
        <q-icon name="chevron_right" color="grey-5" size="md"></q-icon>
      </q-item-section>
    </q-item>
    <q-item
      v-if="g.user.hiddenWalletsCount > 0"
      clickable
      @click="$router.push('/wallets')"
    >
      <q-item-section side>
        <q-icon name="more_horiz" color="grey-5" size="md"></q-icon>
      </q-item-section>
      <q-item-section>
        <q-item-label
          lines="1"
          class="text-caption"
          v-text="$t('more_count', {count: g.user.hiddenWalletsCount})"
        ></q-item-label>
      </q-item-section>
    </q-item>
    <q-item
      clickable
      @click="
        g.user.walletInvitesCount
          ? openNewWalletDialog('lightning-shared')
          : openNewWalletDialog('lightning')
      "
    >
      <q-item-section side>
        <q-icon name="add" color="grey-5" size="md"></q-icon>
      </q-item-section>
      <q-item-section>
        <q-item-label
          lines="1"
          class="text-caption"
          v-text="$t('add_new_wallet')"
        ></q-item-label>
        <q-item-section v-if="g.user.walletInvitesCount" side>
          <q-badge>
            <span
              v-text="'Wallet Invite (' + g.user.walletInvitesCount + ')'"
            ></span>
          </q-badge>
        </q-item-section>
      </q-item-section>
    </q-item>
  </q-list>
</template>
