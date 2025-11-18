<template id="page-home">
  <div class="home row justify-center items-center">
    <div
      class="full-width content-center"
      :style="`max-width: ${hasCustomImage ? '850' : '600'}px; min-height: 55vh;`"
    >
      <div class="row q-mb-md">
        <div class="col-12">
          <div v-if="showHomepageElements">
            <h5 v-text="siteTitle" class="q-my-none"></h5>
            <template v-if="$q.screen.gt.sm">
              <h6 class="q-my-sm" v-text="siteTagline"></h6>
              <p class="q-my-sm" v-html="formatDescription"></p>
            </template>
          </div>
        </div>
      </div>

      <div class="row">
        <q-badge
          v-if="isAccessTokenExpired"
          class="q-mx-auto q-mb-md"
          color="primary"
          rounded
        >
          <div class="text-h6">
            <span v-text="$t('session_has_expired')"></span>
          </div>
        </q-badge>
        <q-card bordered class="full-width q-py-md">
          <div class="row">
            <div
              class="col-12"
              :class="{'col-sm-7': hasCustomImage, 'col-lg-6': hasCustomImage}"
            >
              <div v-if="showClaimLnurl" class="full-height content-center">
                <q-card-section>
                  <div class="text-body1">
                    <span v-text="$t('claim_desc')"></span>
                  </div>
                </q-card-section>
                <q-card-section>
                  <q-btn
                    unelevated
                    color="primary"
                    @click="processing"
                    type="a"
                    :href="'/lnurlwallet?lightning=' + lnurl"
                    v-text="$t('press_to_claim')"
                    class="full-width"
                  ></q-btn>
                </q-card-section>
              </div>
              <div v-else class="full-height content-center">
                <username-password
                  v-if="authMethod != 'user-id-only'"
                  :allowed_new_users="allowRegister"
                  :auth-methods="LNBITS_AUTH_METHODS"
                  :auth-action="authAction"
                  v-model:user-name="username"
                  v-model:password_1="password"
                  v-model:password_2="passwordRepeat"
                  v-model:reset-key="reset_key"
                  @login="login"
                  @register="register"
                  @reset="reset"
                >
                  <div
                    class="text-center text-grey-6"
                    v-if="authAction !== 'reset'"
                  >
                    <p
                      v-if="authAction === 'login' && allowRegister"
                      class="q-mb-none"
                    >
                      Not registered?
                      <a
                        href="#"
                        class="text-secondary cursor-pointer"
                        @click.prevent="showRegister('username-password')"
                        >Create an Account</a
                      >
                    </p>
                    <p
                      v-else-if="authAction === 'login' && !allowRegister"
                      class="q-mb-none"
                    >
                      <span v-text="$t('new_user_not_allowed')"></span>
                    </p>
                    <p v-else-if="authAction === 'register'" class="q-mb-none">
                      <span v-text="$t('existing_account_question')"></span>

                      <a
                        href="#"
                        class="text-secondary cursor-pointer q-ml-sm"
                        @click.prevent="showLogin('username-password')"
                        v-text="$t('login')"
                      ></a>
                    </p>
                  </div>
                </username-password>
                <user-id-only
                  v-if="authMethod == 'user-id-only'"
                  :allowed_new_users="allowRegister"
                  v-model:usr="usr"
                  v-model:wallet="walletName"
                  :auth-action="authAction"
                  :auth-method="authMethod"
                  @show-login="showLogin"
                  @show-register="showRegister"
                  @login-usr="loginUsr"
                  @create-wallet="createWallet"
                >
                </user-id-only>
              </div>
            </div>
            <div v-if="hasCustomImage" class="col-sm-5 col-lg-6 gt-xs">
              <div class="full-height flex flex-center q-pa-lg">
                <q-img :src="hasCustomImage" :ratio="1" width="250px"></q-img>
              </div>
            </div>
          </div>
        </q-card>
      </div>
    </div>
    <div v-if="lnbitsBannerEnabled" class="full-width q-mb-lg q-mt-sm">
      <div class="flex flex-center q-gutter-md q-py-md">
        <q-btn
          outline
          color="grey"
          type="a"
          href="https://github.com/lnbits/lnbits"
          target="_blank"
          rel="noopener noreferrer"
          :label="$t('view_github')"
        ></q-btn>
        <q-btn
          outline
          color="grey"
          type="a"
          href="https://demo.lnbits.com/lnurlp/link/fH59GD"
          target="_blank"
          rel="noopener noreferrer"
          :label="$t('donate')"
        ></q-btn>
      </div>
    </div>
    <div
      :class="$q.screen.lt.md ? 'column col-10' : 'col-10'"
      class="flex justify-center q-col-gutter-sm q-mb-lg"
    >
      <a :href="ad[0]" class="col lnbits-ad" v-for="ad in g.ads">
        <img class="full-width" v-if="$q.dark.isActive" :src="ad[1]" />
        <img class="full-width" v-else :src="ad[2]" />
      </a>
    </div>
    <lnbits-home-logos />
  </div>
</template>
