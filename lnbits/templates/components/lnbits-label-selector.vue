<template id="lnbits-label-selector">
  <div v-if="g.user.extra.labels?.length">
    <q-item header>
      <q-input
        v-model="labelFilter"
        :label="$t('filter_labels')"
        class="full-width"
        filled
        dense
        autofocus
      >
      </q-input>
    </q-item>
    <q-separator></q-separator>
    <q-scroll-area style="height: 230px; max-width: 300px">
      <div v-for="label in g.user.extra.labels" :key="label.name">
        <q-item
          v-if="
            !labelFilter ||
            label.name.toLowerCase().includes(labelFilter.toLowerCase())
          "
          clickable
          v-ripple
        >
          <q-item-section avatar top>
            <q-checkbox
              :model-value="localLabels.includes(label.name)"
              @click="toggleLabel(label)"
              dense
            >
            </q-checkbox>
          </q-item-section>

          <q-item-section>
            <q-item-label lines="1"
              ><span v-text="label.name"></span
            ></q-item-label>
            <q-item-label caption
              ><span v-text="label.description"></span
            ></q-item-label>
          </q-item-section>

          <q-item-section side>
            <q-badge
              class="q-pa-sm"
              size="xs"
              rounded
              :style="{
                backgroundColor: label.color,
                color: 'white'
              }"
            >
              <span v-text="label.color"></span>
            </q-badge>
          </q-item-section>
        </q-item>
      </div>
    </q-scroll-area>
    <q-item footer>
      <q-btn
        v-close-popup
        flat
        color="grey"
        class="q-ml-none"
        icon="highlight_off"
        @click="clearLabels"
      >
        <q-tooltip>
          <span v-text="$t('clear')"></span>
        </q-tooltip>
      </q-btn>
      <q-btn
        v-close-popup
        flat
        href="/account#labels"
        color="grey"
        icon="settings"
        class="q-ml-auto float-right"
      >
        <q-tooltip>
          <span v-text="$t('manage_labels')"></span>
        </q-tooltip>
      </q-btn>
      <q-btn
        v-close-popup
        flat
        color="primary"
        class="q-ml-none"
        :label="$t('ok')"
        @click="saveLabels"
      >
        <q-tooltip>
          <span v-text="$t('manage_labels')"></span>
        </q-tooltip>
      </q-btn>
    </q-item>
  </div>
  <div v-else class="q-pa-md">
    <p v-text="$t('no_labels_defined')"></p>
    <q-btn
      flat
      href="/account#labels"
      color="primary"
      :label="$t('manage_labels')"
    ></q-btn>
  </div>
</template>
