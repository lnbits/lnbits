<template>
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
<script setup>
const LnbitsError = {
  props: ['dynamic', 'code', 'message'],
  computed: {
    isExtension() {
      if (this.code != 403) return false
      if (this.message.startsWith('Extension ')) return true
    }
  },
  methods: {
    goBack() {
      window.history.back()
    },
    goHome() {
      window.location = '/'
    },
    goToWallet() {
      if (this.dynamic) {
        this.$router.push('/wallet')
        return
      }
      window.location = '/wallet'
    },
    goToExtension() {
      const extension = this.message.match(/'([^']+)'/)[1]
      const url = `/extensions#${extension}`
      if (this.dynamic) {
        this.$router.push(url)
        return
      }
      window.location = url
    },
    async logOut() {
      try {
        await LNbits.api.logout()
        window.location = '/'
      } catch (e) {
        LNbits.utils.notifyApiError(e)
      }
    }
  },
  async created() {
    // check if we have error from error.html
    if (!this.dynamic) {
      if (this.code == 401) {
        console.warn(`Unauthorized: ${this.errorMessage}`)
        this.logOut()
        return
      }
    }
  }
}
// expose to window on the browser
if (typeof window !== 'undefined') window.LnbitsError = LnbitsError
export default LnbitsError
</script>
