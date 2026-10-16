<template id="page-extension-ai-builder">
  <div v-if="g.user?.admin">
    <div class="row items-center justify-between q-gutter-sm q-mb-lg">
      <div class="row items-center q-gutter-sm">
        <q-btn
          flat
          round
          icon="arrow_back"
          to="/extensions"
          :aria-label="$t('extensions')"
        ></q-btn>
        <h1 class="text-h6 q-my-none" v-text="$t('ai_extension_builder')"></h1>
        <q-badge
          outline
          color="primary"
          :label="$t('ai_builder_admin_only')"
        ></q-badge>
      </div>
      <q-badge
        v-if="extension.id"
        outline
        :label="$t(isEditing ? 'edit_wasm_extension' : 'new_wasm_extension')"
      ></q-badge>
    </div>
    <q-card v-if="extension.id" class="q-mb-md">
      <q-card-section>
        <div
          class="text-h6"
          style="overflow-wrap: anywhere"
          v-text="extension.name || extension.id"
        ></div>
        <div
          class="text-caption"
          style="overflow-wrap: anywhere"
          v-text="extension.id"
        ></div>
        <p
          v-if="extension.description"
          class="q-mt-sm q-mb-none"
          style="white-space: pre-wrap; overflow-wrap: anywhere"
          v-text="extension.description"
        ></p>
      </q-card-section>
    </q-card>
    <q-banner v-else rounded class="bg-marginal-bg q-mb-md">
      <span v-text="$t('ai_builder_choose_extension')"></span>
    </q-banner>
    <q-card flat bordered>
      <q-card-section
        class="text-subtitle1"
        v-text="$t('ai_builder_preview')"
      ></q-card-section>
      <q-separator></q-separator>
      <q-card-section
        class="column items-center justify-center q-pa-xl text-center"
        style="min-height: 200px"
      >
        <q-icon
          name="web_asset"
          size="40px"
          color="grey"
          class="q-mb-md"
        ></q-icon>
        <div v-text="$t('ai_builder_preview_empty')"></div>
        <div
          class="text-caption q-mt-sm"
          v-text="$t('ai_builder_ui_only')"
        ></div>
      </q-card-section>
    </q-card>
    <q-footer
      bordered
      :class="$q.dark.isActive ? 'bg-dark text-white' : 'bg-white text-dark'"
      :style="{height: conversationHeight + 'px'}"
    >
      <div class="column no-wrap full-height">
        <div
          v-touch-pan.prevent.mouse.vertical="resizeConversation"
          role="separator"
          tabindex="0"
          aria-orientation="horizontal"
          aria-controls="ai-builder-conversation"
          :aria-label="$t('ai_builder_resize')"
          :aria-valuenow="conversationHeight"
          :aria-valuemin="minConversationHeight"
          :aria-valuemax="maxConversationHeight"
          class="row items-center justify-center col-auto"
          style="
            height: 24px;
            cursor: ns-resize;
            touch-action: none;
            user-select: none;
          "
          @keydown.up.prevent="adjustConversationHeight(24)"
          @keydown.down.prevent="adjustConversationHeight(-24)"
          @keydown.home.prevent="footerHeight = minConversationHeight"
          @keydown.end.prevent="footerHeight = maxConversationHeight"
        >
          <q-icon name="drag_handle" size="20px"></q-icon>
          <q-tooltip v-text="$t('ai_builder_resize_hint')"></q-tooltip>
        </div>
        <div
          id="ai-builder-conversation"
          class="column no-wrap col q-px-md q-pb-md"
          style="min-height: 0"
        >
          <div
            class="text-subtitle2 col-auto"
            v-text="$t('ai_builder_conversation')"
          ></div>
          <div
            class="col scroll row items-center justify-center text-center q-pa-sm"
            style="min-height: 0"
          >
            <span
              class="text-caption"
              v-text="$t('ai_builder_conversation_empty')"
            ></span>
          </div>
          <q-input
            v-model="prompt"
            outlined
            type="textarea"
            rows="2"
            :label="$t('ai_builder_prompt')"
            :hint="$t('ai_builder_ui_only')"
            class="col-auto"
            :disable="!extension.id"
          >
            <template v-slot:append>
              <q-btn
                round
                flat
                icon="arrow_upward"
                :aria-label="$t('ai_builder_send')"
                disable
              ></q-btn>
            </template>
          </q-input>
        </div>
      </div>
    </q-footer>
  </div>
</template>
