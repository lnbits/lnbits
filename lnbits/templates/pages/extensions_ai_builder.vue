<template id="page-extension-ai-builder">
  <div v-if="g.user?.admin">
    <q-card class="q-mb-md">
      <q-toolbar>
        <q-btn
          flat
          round
          icon="arrow_back"
          to="/extensions"
          :aria-label="$t('extensions')"
        ></q-btn>
        <h1
          class="col text-subtitle1 q-my-none q-ml-sm ellipsis"
          v-text="$t('build_extension')"
        ></h1>
        <q-btn
          disable
          flat
          no-caps
          color="primary"
          :label="$t('ai_builder_deploy')"
        ></q-btn>
        <q-btn
          flat
          round
          icon="settings"
          to="/admin#extensions"
          :aria-label="$t('settings')"
        ></q-btn>
      </q-toolbar>
    </q-card>
    <q-banner v-if="!extension.id" rounded class="bg-marginal-bg q-mb-md">
      <span v-text="$t('ai_builder_choose_extension')"></span>
    </q-banner>
    <q-card
      v-if="isEditing"
      flat
      bordered
      class="relative-position"
      style="min-height: 200px"
    >
      <q-inner-loading :showing="workspaceLoading">
        <q-spinner-dots size="40px"></q-spinner-dots>
      </q-inner-loading>
      <q-banner
        v-if="workspaceError"
        class="bg-negative text-white"
        role="alert"
      >
        <span v-text="workspaceError"></span>
        <template v-slot:action>
          <q-btn
            flat
            :label="$t('ai_builder_retry')"
            @click="loadWorkspace"
          ></q-btn>
        </template>
      </q-banner>
      <wasm-extension
        v-if="previewRoute"
        class="wasm-studio-preview"
        :style="{
          '--wasm-studio-height':
            Math.max(240, $q.screen.height - conversationHeight - 172) + 'px'
        }"
        :preview-route="previewRoute"
        @navigate="navigatePreview"
      ></wasm-extension>
    </q-card>
    <q-card v-else flat bordered>
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
            ref="messages"
            role="log"
            :aria-label="$t('ai_builder_conversation')"
            aria-live="polite"
            class="col scroll q-pa-sm"
            style="min-height: 0"
          >
            <div
              v-for="(message, index) in messages"
              :key="index"
              class="q-mb-sm q-pa-sm rounded-borders text-left"
              :class="
                message.role === 'user'
                  ? $q.dark.isActive
                    ? 'bg-grey-9'
                    : 'bg-grey-2'
                  : ''
              "
              style="white-space: pre-wrap; overflow-wrap: anywhere"
              v-text="message.content"
            ></div>
          </div>
          <q-input
            ref="promptInput"
            v-model="prompt"
            outlined
            type="textarea"
            rows="1"
            autogrow
            :input-style="{
              maxHeight: Math.max(52, conversationHeight / 2) + 'px'
            }"
            :aria-label="$t('ai_builder_prompt')"
            class="col-auto"
            :disable="!extension.id"
            @keydown.enter="handlePromptEnter"
          >
            <template v-slot:append>
              <q-btn
                round
                flat
                icon="arrow_upward"
                :aria-label="$t('ai_builder_send')"
                :disable="!canSendMessage"
                @click="sendMessage"
              ></q-btn>
            </template>
          </q-input>
        </div>
      </div>
    </q-footer>
  </div>
</template>
