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
      <div v-if="title" class="text-h6 q-mb-md" v-text="title"></div>

      <!-- Main content slot -->
      <slot></slot>

      <!-- Footer actions -->
      <div class="row q-mt-lg">
        <!-- Left-aligned action buttons -->
        <div v-if="hasActionsSlot" class="col">
          <slot name="actions"></slot>
        </div>

        <!-- Right-aligned buttons -->
        <div class="col-auto q-ml-auto">
          <q-btn
            v-if="showCancel"
            v-close-popup
            flat
            :color="cancelColor"
            :label="cancelLabel"
            @click="handleCancel"
          />
          <q-btn
            v-if="showConfirm"
            :outline="confirmOutline"
            :flat="confirmFlat"
            :color="confirmColor"
            :label="confirmLabel"
            :loading="confirmLoading"
            :disable="confirmDisable"
            class="q-ml-sm"
            @click="handleConfirm"
          />
        </div>
      </div>
    </q-card>
  </q-dialog>
</template>
