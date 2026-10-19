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
        <q-btn-dropdown
          flat
          no-caps
          label="Undo"
          :disable="busy || requestPending || !checkpoints.length"
        >
          <q-list>
            <q-item
              v-for="(checkpoint, index) in [...checkpoints].reverse()"
              :key="checkpoint.id"
              clickable
              v-close-popup
              @click="undo(checkpoint)"
            >
              <q-item-section
                v-text="`${checkpoints.length - index}. ${checkpoint.label}`"
              ></q-item-section>
            </q-item>
          </q-list>
        </q-btn-dropdown>
        <q-btn
          flat
          no-caps
          label="Review"
          :disable="
            busy || requestPending || workspaceLoading || !!workspaceError
          "
          @click="openReview('review')"
        ></q-btn>
        <q-btn
          flat
          no-caps
          color="primary"
          label="Build"
          :loading="busy === 'build'"
          :disable="
            !!busy || requestPending || workspaceLoading || !!workspaceError
          "
          @click="openReview('build')"
        ></q-btn>
        <q-btn
          :disable="!!busy || requestPending || !build"
          flat
          no-caps
          color="primary"
          :label="$t('ai_builder_deploy')"
          @click="openReview('deploy')"
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
      v-if="previewRoute || workspaceLoading || workspaceError"
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
        :key="previewVersion"
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
          <div class="row items-center q-pt-xs col-auto">
            <q-select
              v-model="selectedModel"
              :options="models"
              option-label="name"
              option-value="id"
              emit-value
              map-options
              dense
              borderless
              label="Model"
              :disable="!!busy || requestPending"
              style="min-width: 180px; max-width: 60%"
            ></q-select>
            <q-btn
              v-if="!models.length && !workspaceLoading"
              flat
              no-caps
              label="Configure models"
              to="/admin/extensions/wasm/studio"
            ></q-btn>
            <q-space></q-space>
            <q-spinner v-if="busy" size="18px" class="q-mr-sm"></q-spinner>
            <q-btn
              v-if="busy === 'chat' || busy === 'build'"
              flat
              no-caps
              label="Stop"
              icon="stop"
              :disable="requestPending"
              @click="perform('/stop')"
            ></q-btn>
          </div>
        </div>
      </div>
    </q-footer>
    <q-dialog v-model="reviewOpen">
      <q-card style="width: 900px; max-width: 95vw">
        <q-card-section
          class="text-h6"
          v-text="
            reviewAction === 'deploy'
              ? 'Review deployment'
              : reviewAction === 'build'
                ? 'Review preview access'
                : 'Draft changes'
          "
        ></q-card-section>
        <q-card-section v-if="review" class="scroll" style="max-height: 65vh">
          <q-banner
            v-if="reviewAction === 'deploy' && review.production_changed"
            class="bg-negative text-white q-mb-md"
            >Production changed since this draft was opened. Deployment is
            blocked until the changes are reconciled.</q-banner
          >
          <p v-if="reviewAction === 'deploy'">
            This deploys the successful build shown below. Later source edits
            are excluded. Production records are preserved; approved migrations
            may change the schema.
          </p>
          <p v-else-if="reviewAction === 'build'">
            Approve this draft's access before loading its preview. Wallet
            actions in the preview use real wallets.
          </p>
          <q-expansion-item label="Permissions" default-opened>
            <pre
              class="q-pa-sm"
              style="white-space: pre-wrap"
              v-text="
                JSON.stringify(
                  {
                    previous: review.previous_permissions,
                    requested: review.permissions
                  },
                  null,
                  2
                )
              "
            ></pre>
          </q-expansion-item>
          <q-expansion-item label="Runtime limits">
            <pre
              class="q-pa-sm"
              style="white-space: pre-wrap"
              v-text="
                JSON.stringify(
                  {previous: review.previous_limits, requested: review.limits},
                  null,
                  2
                )
              "
            ></pre>
          </q-expansion-item>
          <q-expansion-item label="Storage schema and migrations">
            <pre
              class="q-pa-sm"
              style="white-space: pre-wrap"
              v-text="JSON.stringify(review.schema, null, 2)"
            ></pre>
          </q-expansion-item>
          <q-separator class="q-my-md"></q-separator>
          <div v-if="!review.changes.length">No source changes.</div>
          <q-expansion-item
            v-for="change in review.changes"
            :key="change.path"
            :label="change.path"
          >
            <pre
              class="q-pa-sm"
              style="white-space: pre-wrap; overflow-wrap: anywhere"
              v-text="change.diff"
            ></pre>
          </q-expansion-item>
          <q-checkbox
            v-if="reviewAction !== 'review'"
            v-model="reviewApproved"
            label="I approve this code, its permissions, runtime limits and schema changes."
          ></q-checkbox>
        </q-card-section>
        <q-card-actions align="right">
          <q-btn flat label="Close" v-close-popup></q-btn>
          <q-btn
            v-if="reviewAction !== 'review'"
            color="primary"
            no-caps
            :label="
              reviewAction === 'deploy'
                ? 'Deploy Reviewed Build'
                : 'Approve & Build'
            "
            :disable="
              !reviewApproved ||
              (reviewAction === 'deploy' && review.production_changed)
            "
            :loading="requestPending"
            @click="approveReview"
          ></q-btn>
        </q-card-actions>
      </q-card>
    </q-dialog>
  </div>
</template>
