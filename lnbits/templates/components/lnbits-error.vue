<template id="lnbits-error">
  <div class="text-center q-pa-md flex flex-center">
    <div>
      <div class="error-code" v-text="code"></div>
      <div class="error-message" v-text="message"></div>
      <div class="q-mx-auto q-mt-lg justify-center" style="width: max-content">
        <q-btn
          v-if="isExtension"
          color="primary"
          @click="goToExtension()"
          label="Go To Extension"
        ></q-btn>
        <q-btn
          v-else-if="g.isUserAuthorized"
          color="primary"
          @click="goToWallet()"
          label="Go to Wallet"
        ></q-btn>
        <q-btn v-else color="primary" @click="goBack()" label="Go Back"></q-btn>
        <span class="q-mx-md">OR</span>
        <q-btn color="secondary" @click="goHome()" label="Go Home"></q-btn>
      </div>
    </div>
  </div>
</template>
