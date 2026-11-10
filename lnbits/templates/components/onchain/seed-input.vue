<template id="onchain-seed-input">
  <div>
    <div v-if="done">
      <div class="row">
        <div class="col-12" v-text="$t('onchain.seed_input_done')"></div>
      </div>
    </div>
    <div v-else>
      <div class="row">
        <div class="col-3 q-pt-sm" v-text="$t('onchain.word_count')"></div>
        <div class="col-6 q-pr-lg">
          <q-select
            filled
            dense
            v-model="wordCount"
            type="number"
            :label="$t('onchain.word_count')"
            :options="wordCountOptions"
            @update:model-value="initWords"
          ></q-select>
        </div>
        <div class="col-3 q-pr-lg"></div>
      </div>
      <div class="row">
        <div class="col-3 q-pr-lg"></div>
        <div
          class="col-6"
          v-text="
            $t('onchain.enter_word_at_position', {position: actualPosition})
          "
        ></div>
        <div class="col-3 q-pr-lg"></div>
      </div>
      <div class="row">
        <div class="col-3 q-pr-lg">
          <q-btn
            v-if="currentPosition > 0"
            @click="previousPosition"
            unelevated
            class="full-width"
            color="secondary"
            :label="$t('onchain.previous')"
          ></q-btn>
        </div>
        <div class="col-6 q-pr-lg">
          <q-select
            filled
            dense
            use-input
            hide-selected
            fill-input
            input-debounce="0"
            v-model="currentWord"
            :options="options"
            @filter="filterFn"
            @input-value="setModel"
          ></q-select>
        </div>

        <div class="col-3 q-pr-lg">
          <q-btn
            v-if="currentPosition < wordCount - 1"
            @click="nextPosition"
            unelevated
            class="full-width"
            color="secondary"
            :label="$t('onchain.next')"
          ></q-btn>
          <q-btn
            v-else
            @click="seedInputDone"
            unelevated
            class="full-width"
            color="primary"
            :label="$t('onchain.done')"
          ></q-btn>
        </div>
        <q-linear-progress
          :value="currentPosition / (wordCount - 1)"
          size="5px"
          color="primary"
          class="q-mt-sm"
        ></q-linear-progress>
      </div>
    </div>
  </div>
</template>
