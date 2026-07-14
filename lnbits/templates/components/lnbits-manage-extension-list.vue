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
      :active="extensionActive(extension)"
      tag="a"
      :to="extensionUrl(extension)"
    >
      <q-item-section side>
        <q-avatar size="md">
          <img
            v-if="extension.tile"
            :src="extension.tile"
            style="width: 20px; height: 20px; object-fit: contain"
          />
          <q-icon v-else name="extension" size="20px"></q-icon>
        </q-avatar>
      </q-item-section>
      <q-item-section>
        <q-item-label lines="1"
          ><span v-text="extension.name"></span>
        </q-item-label>
      </q-item-section>
      <q-item-section side v-show="extensionActive(extension)">
        <q-icon name="chevron_right" color="grey-5" size="md"></q-icon>
      </q-item-section>
    </q-item>
    <div class="lt-md q-mt-xl q-mb-xl"></div>
  </q-list>
</template>
