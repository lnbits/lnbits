<template id="page-first-install">
  <div class="fullscreen">
    <div class="row q-col-gutter-md justify-center main first-install">
      <div class="col-10 col-md-8 col-lg-6 q-gutter-y-md">
        <q-card>
          <q-card-section class="grid">
            <div>
              <h6 class="q-my-none text-center">
                <strong v-text="$t('welcome_lnbits')"></strong>
                <p><span v-text="$t('setup_su_account')"></span></p>
              </h6>
              <br />
              <q-form class="q-gutter-md">
                <q-input
                  filled
                  v-model="loginData.username"
                  :label="$t('username')"
                ></q-input>
                <q-input
                  filled
                  v-model.trim="loginData.password"
                  :type="loginData.isPwd ? 'password' : 'text'"
                  autocomplete="off"
                  :label="$t('password')"
                  :rules="[
                    val => !val || val.length >= 8 || $t('invalid_password')
                  ]"
                  ><template v-slot:append>
                    <q-icon
                      :name="loginData.isPwd ? 'visibility_off' : 'visibility'"
                      class="cursor-pointer"
                      @click="loginData.isPwd = !loginData.isPwd"
                    /> </template
                ></q-input>
                <q-input
                  filled
                  v-model.trim="loginData.passwordRepeat"
                  :type="loginData.isPwdRepeat ? 'password' : 'text'"
                  autocomplete="off"
                  :label="$t('password_repeat')"
                  :rules="[
                    val => !val || val.length >= 8 || $t('invalid_password'),
                    val =>
                      val === loginData.password ||
                      $t('invalid_password_repeat')
                  ]"
                  ><template v-slot:append>
                    <q-icon
                      :name="
                        loginData.isPwdRepeat ? 'visibility_off' : 'visibility'
                      "
                      class="cursor-pointer"
                      @click="loginData.isPwdRepeat = !loginData.isPwdRepeat"
                    /> </template
                ></q-input>
                <q-btn
                  @click="setPassword()"
                  unelevated
                  color="primary"
                  :label="$t('login')"
                  :disable="
                    checkPasswordsMatch ||
                    !loginData.username ||
                    !loginData.password ||
                    !loginData.passwordRepeat
                  "
                ></q-btn>
              </q-form>
            </div>
            <div class="hero-wrapper">
              <div class="hero q-mx-auto"></div>
            </div>
          </q-card-section>
        </q-card>
      </div>
    </div>
  </div>
</template>
