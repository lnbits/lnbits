<template id="lnbits-two-factor">
  <q-card flat bordered class="q-pa-md" style="max-width: 650px">
    <h6 class="q-mt-none">Two Factor Auth (2FA)</h6>
    <q-banner
      v-if="error"
      class="bg-negative text-white q-mb-md"
      role="alert"
      v-text="error"
    ></q-banner>
    <div v-if="codes.length">
      <p>
        Save these recovery codes somewhere safe, separate from your phone. Each
        code works once. They will not be shown again.
      </p>
      <pre
        class="q-pa-md"
        style="user-select: text"
        v-text="codes.join('\n')"
      ></pre>
      <q-checkbox
        v-model="saved"
        label="I have saved my recovery codes"
      ></q-checkbox>
      <q-btn
        color="primary"
        label="Done"
        :disable="!saved"
        :loading="busy"
        @click="acknowledge"
      ></q-btn>
    </div>
    <template v-else-if="status">
      <q-banner v-if="!status.available" class="bg-warning text-black q-mb-md">
        2FA is disabled for this instance. Existing authenticator settings are
        retained, but verification is not required.
      </q-banner>
      <template v-else>
        <p v-if="status.mandatory && !status.enrolled">
          Set up an authenticator to continue. This instance requires 2FA.
        </p>
        <p v-else-if="!status.enrolled">
          Use Google Authenticator, Ente Auth, Aegis, or another TOTP app.
        </p>
        <p
          v-else
          v-text="
            'Authenticator enrolled. ' +
            status.recovery_remaining +
            ' recovery codes remaining.'
          "
        ></p>
        <div v-if="setup">
          <p>
            Scan this QR code with your authenticator, then enter its six-digit
            code.
          </p>
          <lnbits-qrcode :value="setup.uri"></lnbits-qrcode>
          <p class="q-mt-md">
            Manual setup key:
            <code style="overflow-wrap: anywhere" v-text="setup.secret"></code>
          </p>
        </div>
        <q-btn
          v-if="!status.enrolled && !setup"
          label="Set up authenticator"
          color="primary"
          :loading="busy"
          @click="start"
        ></q-btn>
        <q-form
          v-if="status.enrolled || setup"
          @submit="verify"
          class="q-gutter-md"
        >
          <q-input
            v-model="code"
            outlined
            autocomplete="one-time-code"
            :label="
              setup ? 'Authenticator code' : 'Authenticator or recovery code'
            "
            maxlength="64"
          ></q-input>
          <q-btn
            type="submit"
            :label="setup ? 'Enable 2FA' : 'Verify'"
            color="primary"
            :loading="busy"
            :disable="!code"
          ></q-btn>
        </q-form>
        <div v-if="status.enrolled && !standalone" class="q-gutter-sm q-mt-md">
          <p v-if="verified" class="text-positive">Verification complete.</p>
          <p>Verify a fresh code above before changing your 2FA settings.</p>
          <q-btn
            outline
            label="Replace recovery codes"
            :loading="busy"
            @click="regenerate"
          ></q-btn>
          <q-btn
            v-if="!status.mandatory"
            outline
            color="negative"
            label="Disable my 2FA"
            :loading="busy"
            @click="disable"
          ></q-btn>
        </div>
      </template>
    </template>
    <div class="q-mt-lg">
      <q-btn flat label="Sign in again" @click="logout"></q-btn>
    </div>
  </q-card>
</template>
