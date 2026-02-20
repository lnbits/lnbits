<template id="lnbits-dialog">
  <q-dialog
    :model-value="show"
    :position="position"
    :persistent="persistent"
    @update:model-value="$emit('update:show', $event)"
    @hide="handleHide"
  >
    <q-card class="q-pa-lg q-pt-xl lnbits__dialog-card">
      <!-- Header with optional title -->
      <q-card-section v-if="title">
        <div class="text-h6 q-mb-md" v-text="title"></div>
      </q-card-section>

      <!-- Main content slot -->
      <q-card-section>
        <slot></slot>
      </q-card-section>

      <!-- Footer actions -->
      <q-card-actions class="q-mt-lg" align="right">
        <!-- Left-aligned buttons -->
        <q-btn
          v-if="showCancel"
          v-close-popup
          flat
          :color="cancelColor"
          :label="cancelLabel"
          :class="{'q-ml-sm': hasActionsSlot}"
          @click="handleCancel"
        ></q-btn>

        <q-space></q-space>

        <!-- Right-aligned primary action -->
        <q-btn
          v-if="hasAction"
          :outline="actionProps.outline"
          :flat="actionProps.flat"
          :unelevated="actionProps.unelevated"
          :no-caps="actionProps.noCaps"
          :color="actionProps.color"
          :label="actionProps.label"
          :icon="actionProps.icon"
          :loading="actionProps.loading"
          :disable="actionProps.disable"
          @click="handleAction"
        ></q-btn>
      </q-card-actions>
    </q-card>
  </q-dialog>
</template>
