<template id="lnbits-header">
  <q-header bordered class="bg-marginal-bg">
    <q-banner v-if="showVoidwallet" class="bg-warning text-white" dense>
      <template v-slot:avatar>
        <q-icon name="warning" color="white" />
      </template>
      <a
        v-if="showAdmin"
        href="/admin"
        style="color: white; text-decoration: underline; cursor: pointer"
        v-text="$t('voidwallet_active_admin')"
      ></a>
      <span v-else v-text="$t('voidwallet_active_user')"></span>
    </q-banner>
    <q-toolbar>
      <q-btn
        v-if="!g.isPublicPage"
        dense
        flat
        round
        icon="menu"
        @click="g.visibleDrawer = !g.visibleDrawer"
      ></q-btn>
      <q-toolbar-title>
        <q-btn flat no-caps dense size="lg" type="a" href="/">
          <q-img
            v-if="customLogoUrl"
            height="30px"
            alt="Logo"
            :src="customLogoUrl"
          ></q-img>
          <span v-else-if="!titleIsLnbits"><strong>LN</strong>bits</span>
          <span v-else v-text="title"></span>
        </q-btn>
        <q-badge v-if="g.user && g.user.super_user">Super User</q-badge>
        <q-badge v-else-if="g.user && g.user.admin">Admin User</q-badge>
      </q-toolbar-title>
      <q-badge
        class="q-mr-md"
        v-show="$q.screen.gt.sm"
        v-if="hasCustomBadge"
        :label="customBadge"
        :color="customBadgeColor"
      >
      </q-badge>

      <q-badge
        v-show="$q.screen.gt.sm"
        v-if="hasServiceFee"
        color="green"
        class="q-mr-md"
      >
        <span
          v-if="hasServiceFeeMax"
          v-text="
            $t('service_fee_max_badge', {
              amount: serviceFee,
              max: serviceFeeMax,
              denom: g.denomination
            })
          "
        ></span>
        <span
          v-else
          v-text="$t('service_fee_badge', {amount: serviceFee})"
        ></span>
        <q-tooltip><span v-text="$t('service_fee_tooltip')"></span></q-tooltip>
      </q-badge>

      <q-badge v-if="g.offline" color="red" class="q-mr-md">
        <span>OFFLINE</span>
      </q-badge>

      <lnbits-language-dropdown></lnbits-language-dropdown>

      <q-btn-dropdown
        v-if="g.user || g.isUserAuthorized"
        flat
        rounded
        size="sm"
        class="q-pl-sm"
      >
        <template v-slot:label>
          <div>
            <q-img
              v-if="hasUserPicture"
              :src="userPictureUrl"
              style="max-width: 32px"
            ></q-img>
            <q-icon v-else name="account_circle" />
          </div>
        </template>
        <q-list>
          <q-item to="/account" clickable v-close-popup>
            <q-item-section>
              <q-item-label>
                <q-icon class="q-mr-sm" name="person"></q-icon>
                <span v-text="$t('my_account')"></span>
              </q-item-label>
            </q-item-section>
          </q-item>
          <q-item to="/account#theme" clickable v-close-popup>
            <q-item-section>
              <q-item-label>
                <q-icon
                  class="q-mr-sm"
                  :name="$q.dark.isActive ? 'dark_mode' : 'light_mode'"
                ></q-icon>
                <span v-text="$t('theme')"></span>
              </q-item-label>
            </q-item-section>
          </q-item>
          <q-separator></q-separator>
          <q-item clickable v-close-popup @click="utils.logout">
            <q-item-section>
              <q-item-label>
                <q-icon class="q-mr-sm" name="logout"></q-icon>
                <span v-text="$t('logout')"></span>
              </q-item-label>
            </q-item-section>
          </q-item>
        </q-list>
      </q-btn-dropdown>
    </q-toolbar>
  </q-header>
</template>
