<template id="lnbits-wallet-icon">
  <q-btn
    @click="icon.show = true"
    round
    color="grey-5"
    text-color="black"
    size="xs"
    icon="edit"
    style="position: relative; left: -15px; bottom: -10px"
  ></q-btn>
  <lnbits-dialog
    :show="icon.show"
    :action="{
      handler: setIcon,
      label: 'Save Icon',
      disable: !icon.data.icon
    }"
    @update:show="icon.show = $event"
    @hide="icon.data = {}"
  >
    <q-form class="q-gutter-md">
      <div class="q-gutter-sm q-pa-sm flex flex-wrap justify-center">
        <q-btn
          v-for="(thisIcon, index) in icon.options"
          :key="index"
          @click="setSelectedIcon(thisIcon)"
          round
          text-color="black"
          :color="
            icon.data.icon === thisIcon
              ? icon.data.color || 'primary'
              : 'grey-5'
          "
          size="md"
          :icon="thisIcon"
          class="q-mb-sm"
        ></q-btn>
      </div>
      <div class="q-pa-sm flex justify-between items-center">
        <div class="flex q-pl-lg">
          <q-btn
            v-for="(color, index) in icon.colorOptions"
            :key="'color-' + index"
            @click="setSelectedColor(color)"
            round
            :color="color"
            size="xs"
            style="width: 24px; height: 24px; min-width: 24px; padding: 0"
            class="q-mr-xs"
          ></q-btn>
        </div>
      </div>
    </q-form>
  </lnbits-dialog>
</template>
