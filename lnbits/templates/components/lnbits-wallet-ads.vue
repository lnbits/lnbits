<template id="lnbits-wallet-ads">
  <q-card v-if="adSpaceEnabled">
    <q-card-section>
      <h6 v-text="adSpaceTitle" class="text-subtitle1 q-mt-none q-mb-sm"></h6>
    </q-card-section>
    <q-card-section class="q-pa-none" v-for="ad in ads">
      <a
        style="display: inline-block"
        :href="ad[0]"
        class="q-ml-md q-mb-xs q-mr-md"
      >
        <img
          style="max-width: 100%; height: auto"
          v-if="$q.dark.isActive"
          :src="ad[1]"
        />
        <img v-else :src="ad[2]" style="max-width: 100%; height: auto" />
      </a>
    </q-card-section>
  </q-card>
</template>
