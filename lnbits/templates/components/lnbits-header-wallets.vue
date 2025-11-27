<template id="lnbits-header-wallets">
  <q-scroll-area
    v-if="g.user && g.walletFlip"
    style="
      height: 130px;
      width: 100%;
      overflow-x: auto;
      overflow-y: hidden;
      mask-image: linear-gradient(
        to right,
        hsl(0 0% 0% / 1) 80%,
        hsl(0 0% 0% / 0)
      );
    "
  >
    <div class="row no-wrap q-pr-md">
      <q-card class="wallet-list-card cursor-pointer">
        <q-card-section class="flex flex-center column full-height text-center">
          <div>
            <q-btn
              @click="openNewWalletDialog()"
              round
              color="primary"
              icon="add"
            >
              <q-tooltip><span v-text="$t('add_new_wallet')"></span></q-tooltip>
            </q-btn>
          </div>
          <div>
            <q-badge
              v-if="g.user.walletInvitesCount"
              @click="openNewWalletDialog('lightning-shared')"
              dense
              outline
              class="q-mt-sm"
            >
              <span
                v-text="'New wallet invite (' + g.user.walletInvitesCount + ')'"
              ></span>
            </q-badge>
          </div>
        </q-card-section>
      </q-card>
      <q-card
        v-for="wallet in g.user.wallets.slice(
          0,
          g.user.extra.visible_wallet_count || 10
        )"
        :key="wallet.id"
        clickable
        @click="$router.push('/wallet/' + wallet.id)"
        class="wallet-list-card"
        :class="{
          'active-wallet-card': g.wallet && g.wallet.id === wallet.id
        }"
        style="width: 250px; cursor: pointer"
        :style="
          g.wallet && g.wallet.id === wallet.id
            ? `background-color: ${
                $q.dark.isActive
                  ? 'rgba(255, 255, 255, 0.08)'
                  : 'rgba(0, 0, 0, 0.08)'
              } !important;`
            : ''
        "
      >
        <q-card-section>
          <div class="row items-center">
            <q-avatar
              size="lg"
              :text-color="$q.dark.isActive ? 'black' : 'grey-3'"
              :class="g.wallet && g.wallet.id === wallet.id ? 'disabled' : ''"
              :color="wallet.extra.color"
              :icon="wallet.extra.icon"
            >
            </q-avatar>
            <div
              class="text-h6 q-pl-md ellipsis"
              style="max-width: 80%"
              :class="{
                'text-bold': g.wallet && g.wallet.id === wallet.id
              }"
              v-text="wallet.name"
            ></div>
          </div>
          <div class="row items-center q-pt-sm">
            <h6 class="q-my-none ellipsis full-width">
              <strong v-text="formatBalance(wallet.sat)"></strong>
            </h6>
          </div>
        </q-card-section>
      </q-card>
      <q-card v-if="g.user.hiddenWalletsCount" class="wallet-list-card">
        <q-card-section class="flex flex-center column full-height text-center">
          <div>
            <q-btn
              round
              color="primary"
              icon="more_horiz"
              @click="$router.push('/wallets')"
            >
              <q-tooltip
                ><span
                  v-text="$t('more_count', {count: g.user.hiddenWalletsCount})"
                ></span
              ></q-tooltip>
            </q-btn>
          </div>
        </q-card-section>
      </q-card>
    </div>
  </q-scroll-area>
</template>
