<template id="lnbits-disclaimer">
  <q-dialog v-model="showDisclaimer" position="top">
    <q-card class="q-pa-lg">
      <h6
        class="q-my-md text-primary"
        v-text="$t('disclaimer_dialog_title')"
      ></h6>
      <p class="whitespace-pre-line" v-text="$t('disclaimer_dialog')"></p>
      <div class="row q-mt-lg">
        <q-btn
          outline
          color="grey"
          type="a"
          href="/account"
          :label="$t('my_account')"
        ></q-btn>
        <q-btn
          v-close-popup
          flat
          color="grey"
          class="q-ml-auto"
          :label="$t('i_understand')"
          @click="g.disclaimerShown = !g.disclaimerShown"
        ></q-btn>
      </div>
    </q-card>
  </q-dialog>
</template>
