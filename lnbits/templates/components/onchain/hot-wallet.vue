<template id="onchain-hot-wallet">
  <q-dialog v-model="show" :persistent="busy" @hide="resetSecrets">
    <q-card
      class="lnbits__dialog-card q-pa-lg"
      :style="mode === 'backup' ? {width: '760px', maxWidth: '95vw'} : {}"
    >
      <h2
        class="text-h6 q-mt-none"
        v-text="
          mode === 'backup' ? 'Back up ' + wallet.name : 'Add a hot wallet'
        "
      ></h2>
      <q-banner v-if="error" class="bg-red-1 text-negative q-mb-md" role="alert"
        ><span v-text="error"></span
      ></q-banner>
      <template v-if="mode !== 'backup'">
        <q-linear-progress
          v-if="available === null && !error"
          indeterminate
        ></q-linear-progress>
        <q-banner v-if="available === false"
          >Hot wallets are not enabled on this instance. Ask the administrator
          to enable onchain payments and complete key backup in Settings →
          Payments. Hardware and watch-only wallets are available.</q-banner
        >
        <q-form v-if="available" @submit="createWallet" class="q-gutter-md">
          <p>
            This LNbits server holds your private keys and can spend your
            bitcoin. Only use a server you trust. Your recovery phrase lets you
            recover independently.
          </p>
          <q-btn-toggle
            v-model="mode"
            no-caps
            spread
            unelevated
            toggle-color="primary"
            :options="[
              {label: 'Create wallet', value: 'create'},
              {label: 'Restore wallet', value: 'restore'}
            ]"
            :disable="busy"
          ></q-btn-toggle>
          <template v-if="mode === 'restore'">
            <q-banner dense
              >Restore only a phrase you intend this server to control. This
              restores Native SegWit, account 0, with no BIP39 passphrase. Never
              enter a hardware wallet's recovery phrase here.</q-banner
            >
            <q-input
              filled
              v-model="mnemonic"
              type="password"
              autocomplete="off"
              spellcheck="false"
              label="Recovery phrase"
              :disable="busy"
              :rules="[v => !!v.trim() || 'Enter the recovery phrase']"
            ></q-input>
          </template>
          <div class="row">
            <q-btn
              type="submit"
              color="primary"
              unelevated
              :loading="busy"
              :label="mode === 'restore' ? 'Restore wallet' : 'Create wallet'"
            ></q-btn
            ><q-btn
              flat
              label="Cancel"
              class="q-ml-auto"
              v-close-popup
              :disable="busy"
            ></q-btn>
          </div>
        </q-form>
        <q-btn v-else flat label="Close" class="q-mt-md" v-close-popup></q-btn>
      </template>
      <template v-else>
        <div class="row q-col-gutter-sm q-mb-md" aria-label="Backup progress">
          <div class="col-6">
            <q-chip
              square
              class="full-width"
              icon="looks_one"
              :color="backupStep === 1 ? 'primary' : 'grey-9'"
              text-color="white"
              label="Backup"
            ></q-chip>
          </div>
          <div class="col-6">
            <q-chip
              square
              class="full-width"
              icon="looks_two"
              :color="backupStep === 2 ? 'primary' : 'grey-9'"
              text-color="white"
              label="Verify"
            ></q-chip>
          </div>
        </div>
        <q-separator class="q-mb-lg"></q-separator>
        <template v-if="backupStep === 1">
          <div class="row items-center justify-between q-gutter-sm q-mb-md">
            <div>
              <div
                class="text-subtitle1"
                v-text="
                  phrase
                    ? seedWords.length + '-word recovery phrase'
                    : 'Recovery phrase'
                "
              ></div>
              <div class="text-caption text-grey">
                Write these words down in order.
              </div>
            </div>
            <q-btn
              outline
              no-caps
              color="primary"
              :icon="wordsVisible ? 'visibility_off' : 'visibility'"
              :label="wordsVisible ? 'Hide words' : 'Show words'"
              :loading="busy"
              @click="revealBackup"
            ></q-btn>
          </div>
          <div class="row q-col-gutter-sm">
            <div
              v-for="word in seedWords"
              :key="word.index"
              class="col-4 col-sm-3"
            >
              <q-card flat bordered class="row items-center no-wrap q-pa-sm">
                <div
                  class="col-auto text-caption text-grey text-center q-pr-sm"
                  v-text="word.index + 1"
                ></div>
                <q-separator vertical></q-separator>
                <div
                  class="onchain-word col text-body2 text-weight-medium text-wrap q-pl-sm"
                  v-text="wordsVisible ? word.word : '••••••'"
                ></div>
              </q-card>
            </div>
          </div>
          <p class="text-caption text-grey q-mt-md">
            Anyone with this phrase can spend your bitcoin. Keep your backup
            somewhere private.
          </p>
          <p class="text-caption text-grey">
            Recovery: Native SegWit ·
            <span v-text="wallet.onchain_network"></span> ·
            <span
              v-text="
                wallet.onchain_network === 'Mainnet'
                  ? 'm/84\'/0\'/0\''
                  : 'm/84\'/1\'/0\''
              "
            ></span>
            · no passphrase
          </p>
          <div class="row justify-between q-mt-lg">
            <q-btn
              flat
              no-caps
              label="Close"
              v-close-popup
              :disable="busy"
            ></q-btn>
            <q-btn
              color="primary"
              no-caps
              label="I have written it down"
              :disable="!phrase || busy"
              @click="prepareChallenge"
            ></q-btn>
          </div>
        </template>
        <q-form v-else @submit="confirmBackup" autocomplete="off">
          <div class="text-subtitle1">Confirm your backup</div>
          <div class="text-caption text-grey q-mb-md">
            Enter the requested words from your written recovery phrase.
          </div>
          <div class="row q-col-gutter-md">
            <div
              class="col-12 col-sm-6"
              v-for="index in challenge"
              :key="index"
            >
              <q-input
                dense
                filled
                v-model.trim="answers[index]"
                :label="`Word ${index + 1}`"
                autocomplete="off"
                autocapitalize="none"
                spellcheck="false"
                :disable="busy"
              ></q-input>
            </div>
          </div>
          <div class="row justify-between q-mt-lg">
            <q-btn
              flat
              no-caps
              label="Back"
              :disable="busy"
              @click="backToWords"
            ></q-btn>
            <q-btn
              color="primary"
              icon="check"
              no-caps
              label="Confirm backup"
              type="submit"
              :loading="busy"
            ></q-btn>
          </div>
        </q-form>
      </template>
    </q-card>
  </q-dialog>
</template>
