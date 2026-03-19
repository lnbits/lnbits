<template id="lnbits-dialog">
  <q-dialog
    :model-value="show"
    :position="position"
    :persistent="persistent"
    @update:model-value="handleModelUpdate"
    @hide="handleHide"
  >
    <q-card class="q-pa-lg q-pt-xl lnbits__dialog-card">
      <!-- Header with optional title -->
      <q-card-section v-if="title">
        <div class="text-h6" v-text="title"></div>
      </q-card-section>

      <!-- Main content slot -->
      <q-card-section>
        <slot></slot>
      </q-card-section>

      <q-card-actions
        v-if="showCancel || hasAction || hasSecondaryAction"
        class="q-mt-lg"
        align="right"
      >
        <q-btn
          v-if="showCancel"
          v-close-popup
          flat
          :color="cancelColor"
          :label="cancelLabel"
          @click="handleCancel"
        ></q-btn>

        <q-space></q-space>

        <q-btn
          v-if="hasSecondaryAction"
          :icon="secondaryActionProps.icon"
          :color="secondaryActionProps.color"
          :label="secondaryActionProps.label"
          :loading="secondaryActionProps.loading"
          :disable="secondaryActionProps.disable"
          @click="handleSecondaryAction"
          v-close-popup="secondaryActionProps.closePopup"
          class="q-mr-sm"
        ></q-btn>

        <q-btn
          v-if="hasAction"
          :icon="actionProps.icon"
          :color="actionProps.color"
          :label="actionProps.label"
          :loading="actionProps.loading"
          :disable="actionProps.disable"
          @click="handleAction"
          v-close-popup="actionProps.closePopup"
        ></q-btn>
      </q-card-actions>
    </q-card>
  </q-dialog>
</template>
