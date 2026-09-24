<template id="lnbits-two-factor">
  <div>
    <q-card-section class="q-pb-none">
      <div
        class="text-center text-h6 q-mb-sm q-mt-none q-pt-none"
        v-text="$t('two_factor_auth_account')"
      ></div>
    </q-card-section>
    <q-card-section>
      <q-banner
        v-if="error"
        class="bg-negative text-white q-mb-md"
        role="alert"
        v-text="error"
      ></q-banner>
      <div v-if="codes.length">
        <p v-text="$t('two_factor_recovery_save_hint')"></p>
        <pre
          class="q-pa-md"
          style="user-select: text"
          v-text="codes.join('\n')"
        ></pre>
        <q-checkbox
          v-model="saved"
          :label="$t('two_factor_recovery_saved')"
        ></q-checkbox>
        <q-btn
          color="primary"
          class="full-width q-mt-sm"
          :label="$t('two_factor_done')"
          :disable="!saved"
          :loading="busy"
          @click="acknowledge"
        ></q-btn>
      </div>
      <template v-else-if="status">
        <q-banner
          v-if="!status.available"
          class="bg-warning text-black q-mb-md"
        >
          <span v-text="$t('two_factor_disabled_hint')"></span>
        </q-banner>
        <template v-else>
          <p
            v-if="status.mandatory && !status.enrolled"
            v-text="$t('two_factor_enrollment_required')"
          ></p>
          <p
            v-else-if="!status.enrolled"
            v-text="$t('two_factor_apps_hint')"
          ></p>
          <p v-else-if="standalone" v-text="$t('two_factor_verify_hint')"></p>
          <p
            v-else
            v-text="
              $t('two_factor_enrolled', {count: status.recovery_remaining})
            "
          ></p>
          <div v-if="setup">
            <p v-text="$t('two_factor_scan_hint')"></p>
            <lnbits-qrcode :value="setup.uri"></lnbits-qrcode>
            <p class="q-mt-md">
              <span v-text="$t('two_factor_manual_key')"></span>
              <code
                style="overflow-wrap: anywhere"
                v-text="setup.secret"
              ></code>
            </p>
          </div>
          <q-btn
            v-if="!status.enrolled && !setup"
            :label="$t('two_factor_setup')"
            color="primary"
            class="full-width"
            :loading="busy"
            @click="start"
          ></q-btn>
          <q-form
            v-if="status.enrolled || setup"
            @submit="verify"
            class="q-gutter-sm"
          >
            <q-input
              v-model="code"
              dense
              filled
              autocomplete="one-time-code"
              :label="
                setup
                  ? $t('two_factor_code')
                  : $t('two_factor_code_or_recovery')
              "
              maxlength="64"
            ></q-input>
            <div class="row justify-end">
              <q-btn
                type="submit"
                :label="
                  setup
                    ? $t('two_factor_enable_account')
                    : $t('two_factor_verify')
                "
                color="primary"
                class="full-width"
                :loading="busy"
                :disable="!code"
              ></q-btn>
            </div>
          </q-form>
          <div
            v-if="status.enrolled && !standalone"
            class="q-gutter-sm q-mt-md"
          >
            <p
              v-if="verified"
              class="text-positive"
              v-text="$t('two_factor_verified')"
            ></p>
            <p v-text="$t('two_factor_fresh_code_hint')"></p>
            <q-btn
              outline
              :label="$t('two_factor_recovery_replace')"
              :loading="busy"
              @click="regenerate"
            ></q-btn>
            <q-btn
              v-if="!status.mandatory"
              outline
              color="negative"
              :label="$t('two_factor_disable_account')"
              :loading="busy"
              @click="disable"
            ></q-btn>
          </div>
        </template>
      </template>
      <div class="q-mt-sm">
        <q-btn
          outline
          color="primary"
          class="full-width"
          :label="$t('two_factor_sign_in_again')"
          @click="logout"
        ></q-btn>
      </div>
    </q-card-section>
  </div>
</template>
