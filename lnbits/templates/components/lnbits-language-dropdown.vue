<template id="lnbits-language-dropdown">
  <q-btn-dropdown dense flat rounded size="sm" icon="language" class="q-pl-md">
    <q-list v-for="(lang, index) in langs" :key="index">
      <q-item
        clickable
        v-close-popup
        :active="activeLanguage(lang.value)"
        @click="changeLanguage(lang.value)"
      >
        <q-item-section>
          <q-item-label
            v-text="lang.display ?? lang.value.toUpperCase()"
          ></q-item-label>
          <q-tooltip><span v-text="lang.label"></span></q-tooltip>
        </q-item-section>
      </q-item>
    </q-list>
  </q-btn-dropdown>
</template>
