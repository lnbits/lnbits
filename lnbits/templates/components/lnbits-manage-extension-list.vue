<template id="lnbits-manage-extension-list">
  <q-list
    v-if="g.user && extensions && extensions.length > 0"
    dense
    class="lnbits-drawer__q-list"
  >
    <q-item>
      <q-item-section>
        <q-input
          v-model="searchTerm"
          dense
          borderless
          :label="$t('extensions')"
        >
        </q-input>
      </q-item-section>
    </q-item>
    <q-item
      v-for="extension in userExtensions"
      clickable
      :active="$route.path.startsWith('/' + extension.code)"
      tag="a"
      :to="'/' + extension.code + '/'"
    >
      <q-item-section side>
        <q-avatar size="md">
          <q-img :src="extension.tile" style="max-width: 20px"></q-img>
        </q-avatar>
      </q-item-section>
      <q-item-section>
        <q-item-label lines="1"
          ><span v-text="extension.name"></span>
        </q-item-label>
      </q-item-section>
      <q-item-section
        side
        v-show="$route.path.startsWith('/' + extension.code)"
      >
        <q-icon name="chevron_right" color="grey-5" size="md"></q-icon>
      </q-item-section>
    </q-item>
    <div class="lt-md q-mt-xl q-mb-xl"></div>
  </q-list>
</template>
