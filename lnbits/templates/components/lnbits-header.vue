<template id="lnbits-header">
  <q-header bordered class="bg-marginal-bg">
    <q-banner
      v-if="g.settings.showVoidwallet"
      class="bg-warning text-white"
      dense
    >
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
        <q-btn
          flat
          no-caps
          dense
          class="q-mr-sm"
          size="lg"
          type="a"
          :href="utils.urlFor('/', true)"
        >
          <q-img
            v-if="customLogo"
            height="30px"
            alt="Logo"
            :src="customLogo"
          ></q-img>
          <span v-else-if="g.settings.siteTitle == 'LNbits'"
            ><strong>LN</strong>bits</span
          >
          <span v-else v-text="g.settings.siteTitle"></span>
        </q-btn>
        <q-badge v-if="g.user && g.user.super_user">Super User</q-badge>
        <q-badge v-else-if="g.user && g.user.admin">Admin User</q-badge>
      </q-toolbar-title>
      <q-badge
        class="q-mr-md"
        v-show="$q.screen.gt.sm"
        v-if="g.settings.customBadge"
        :label="g.settings.customBadge"
        :color="g.settings.customBadgeColor"
      >
      </q-badge>

      <q-badge
        v-show="$q.screen.gt.sm"
        v-if="g.user && g.settings.serviceFee > 0"
        color="green"
        class="q-mr-md"
      >
        <span
          v-if="g.user && g.settings.serviceFeeMax > 0"
          v-text="
            $t('service_fee_max_badge', {
              amount: g.settings.serviceFee,
              max: g.settings.serviceFeeMax,
              denom: g.denomination
            })
          "
        ></span>
        <span
          v-else
          v-text="$t('service_fee_badge', {amount: g.settings.serviceFee})"
        ></span>
        <q-tooltip><span v-text="$t('service_fee_tooltip')"></span></q-tooltip>
      </q-badge>

      <q-badge v-if="g.offline" color="red" class="q-mr-md">
        <span>OFFLINE</span>
      </q-badge>

      <lnbits-language-dropdown
        @language-changed="handleLanguageChanged({locale: $event})"
      ></lnbits-language-dropdown>

      <q-btn-dropdown v-if="g.user" flat rounded size="md" class="q-pl-sm">
        <template v-slot:label>
          <q-avatar
            v-if="g.user?.extra?.picture && g.user?.extra?.picture !== ''"
            size="18px"
          >
            <q-img :src="g.user?.extra?.picture"></q-img>
          </q-avatar>
          <q-avatar v-else icon="account_circle" size="18px"></q-avatar>
        </template>
        <q-list style="max-width: 200px">
          <q-item>
            <q-item-section
              avatar
              v-if="
                g.user &&
                g.user?.extra?.picture &&
                g.user?.extra?.picture !== ''
              "
            >
              <q-avatar size="md">
                <img :src="g.user?.extra?.picture" />
              </q-avatar>
            </q-item-section>
            <q-item-section>
              <q-item-label
                caption
                class="ellipsis"
                v-text="displayName"
              ></q-item-label>
            </q-item-section>
          </q-item>
          <q-separator></q-separator>
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
      <q-btn
        v-if="g.isUserImpersonated"
        @click="stopImpersonation"
        rounded
        size="sm"
        class="q-pl-sm"
        color="negative"
        icon="face_retouching_off"
        label="Stop"
      >
        <q-tooltip
          ><span v-text="$t('stop_user_impersonation')"></span
        ></q-tooltip>
      </q-btn>
    </q-toolbar>
  </q-header>
</template>
