<template id="lnbits-admin-funding-seed-backup">
  <q-dialog v-model="dialog.show">
    <q-card style="width: 760px; max-width: 95vw; border-radius: 8px">
      <q-card-section class="q-pb-md">
        <div class="row q-col-gutter-sm">
          <div class="col-6">
            <q-chip
              square
              class="full-width"
              icon="looks_one"
              :color="dialog.step === 1 ? 'primary' : 'grey-9'"
              text-color="white"
              label="Backup"
            ></q-chip>
          </div>
          <div class="col-6">
            <q-chip
              square
              class="full-width"
              icon="looks_two"
              :color="dialog.step === 2 ? 'primary' : 'grey-9'"
              text-color="white"
              label="Verify"
            ></q-chip>
          </div>
        </div>
      </q-card-section>

      <q-separator></q-separator>

      <q-card-section v-if="dialog.step === 1">
        <div class="row items-center justify-between q-mb-md">
          <div>
            <div
              class="text-subtitle1"
              v-text="`${seedWords.length}-word recovery phrase`"
            ></div>
            <div
              class="text-caption text-grey-5"
              v-text="'Write these words down in order.'"
            ></div>
          </div>
          <q-btn
            outline
            no-caps
            color="primary"
            :icon="dialog.visible ? 'visibility_off' : 'visibility'"
            :label="dialog.visible ? 'Hide words' : 'Show words'"
            @click="dialog.visible = !dialog.visible"
          ></q-btn>
        </div>

        <div class="row q-col-gutter-sm">
          <div
            class="col-4 col-md-3"
            v-for="word in seedWords"
            :key="word.index"
          >
            <div
              class="row items-center no-wrap rounded-borders"
              style="
                min-height: 42px;
                border: 1px solid rgba(255, 255, 255, 0.14);
                background: rgba(255, 255, 255, 0.035);
              "
            >
              <div
                class="text-caption text-grey-5 text-center"
                style="
                  width: 42px;
                  border-right: 1px solid rgba(255, 255, 255, 0.1);
                "
                v-text="word.index + 1"
              ></div>
              <div
                class="text-body2 text-weight-medium q-px-sm"
                style="min-width: 0; overflow-wrap: anywhere"
                v-text="dialog.visible ? word.word : '••••••'"
              ></div>
            </div>
          </div>
        </div>

        <div class="row justify-end q-mt-lg">
          <q-btn
            color="primary"
            no-caps
            label="I have written it down"
            @click="prepareChallenge"
          ></q-btn>
        </div>
      </q-card-section>

      <q-card-section v-if="dialog.step === 2">
        <div class="q-mb-md">
          <div class="text-subtitle1" v-text="'Confirm your backup'"></div>
          <div
            class="text-caption text-grey-5"
            v-text="
              'Enter the requested words from your written recovery phrase.'
            "
          ></div>
        </div>

        <div class="row q-col-gutter-md">
          <div
            class="col-12 col-sm-6"
            v-for="word in dialog.challenge"
            :key="word.index"
          >
            <q-input
              v-model.trim="dialog.answers[word.index]"
              filled
              :label="`Word ${word.index + 1}`"
            ></q-input>
          </div>
        </div>
        <div
          class="text-negative q-mt-sm"
          v-if="dialog.error"
          v-text="dialog.error"
        ></div>
        <div class="row justify-between q-mt-lg">
          <q-btn flat no-caps label="Back" @click="dialog.step = 1"></q-btn>
          <q-btn
            color="primary"
            icon="check"
            no-caps
            label="Confirm backup"
            @click="submitChallenge"
          ></q-btn>
        </div>
      </q-card-section>
    </q-card>
  </q-dialog>
</template>
