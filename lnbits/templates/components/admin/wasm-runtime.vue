<template id="lnbits-admin-wasm-runtime">
  <q-card-section class="q-pa-none">
    <div>
      <div class="row items-center justify-between q-mb-md">
        <div class="row items-center q-gutter-sm">
          <q-btn
            flat
            dense
            round
            icon="arrow_back"
            :to="
              wasmExtensionId ? '/admin/extensions/wasm' : '/admin#extensions'
            "
          >
            <q-tooltip
              v-text="
                wasmExtensionId ? 'Global WASM Runtime' : 'Extensions Settings'
              "
            ></q-tooltip>
          </q-btn>
          <div>
            <h6 class="q-my-none">WASM Runtime</h6>
            <div
              v-if="wasmExtensionId"
              class="text-caption text-grey-7"
              v-text="`Extension: ${wasmExtensionId}`"
            ></div>
          </div>
        </div>
        <div>
          <q-btn
            flat
            dense
            icon="refresh"
            :loading="wasmRuntimeLoading"
            @click="fetchWasmRuntime"
          >
            <q-tooltip>Refresh runtime data</q-tooltip>
          </q-btn>
        </div>
      </div>
      <div class="row q-col-gutter-md q-mb-md">
        <div
          v-for="item in wasmStatItems"
          :key="item.key"
          class="col-6 col-sm-4 col-md-2"
        >
          <q-card flat bordered class="full-height">
            <q-card-section class="q-pa-sm">
              <div class="row items-center no-wrap q-gutter-sm">
                <q-avatar
                  rounded
                  size="34px"
                  :color="item.color"
                  text-color="white"
                  :icon="item.icon"
                ></q-avatar>
                <div class="col">
                  <div
                    class="text-caption text-grey-7"
                    v-text="item.label"
                  ></div>
                  <div
                    class="text-h6 text-weight-bold"
                    v-text="formatWasmStat(item.key)"
                  ></div>
                </div>
              </div>
            </q-card-section>
          </q-card>
        </div>
      </div>
      <q-table
        class="q-mb-lg"
        dense
        flat
        wrap-cells
        :rows="wasmCurrentInvocations"
        :columns="wasmCurrentColumns"
        row-key="id"
        :loading="wasmRuntimeLoading"
        :pagination="{rowsPerPage: 5}"
        table-style="table-layout: fixed; width: 100%"
        title="Current Invocations"
      >
        <template v-slot:body-cell-extension_id="props">
          <q-td :props="props">
            <q-btn
              dense
              flat
              no-caps
              color="primary"
              :label="props.row.extension_id"
              :to="`/admin/extensions/wasm/${encodeURIComponent(props.row.extension_id)}`"
            ></q-btn>
          </q-td>
        </template>
        <template v-slot:body-cell-trigger_type="props">
          <q-td :props="props">
            <q-badge
              outline
              :color="wasmTriggerColor(props.row.trigger_type)"
              v-text="props.row.trigger_type"
            ></q-badge>
          </q-td>
        </template>
        <template v-slot:body-cell-status="props">
          <q-td :props="props">
            <q-badge
              :color="wasmStatusColor(props.row.status)"
              v-text="props.row.status"
            ></q-badge>
          </q-td>
        </template>
        <template v-slot:body-cell-user_id="props">
          <q-td :props="props">
            <span v-if="props.row.user_id">
              <span v-text="formatWasmUserId(props.row.user_id)"></span>
              <q-tooltip v-text="props.row.user_id"></q-tooltip>
            </span>
            <span v-else>-</span>
          </q-td>
        </template>
        <template v-slot:body-cell-started_at="props">
          <q-td
            :props="props"
            v-text="formatWasmDate(props.row.started_at)"
          ></q-td>
        </template>
        <template v-slot:body-cell-duration_ms="props">
          <q-td :props="props" v-text="formatWasmDuration(props.row)"></q-td>
        </template>
        <template v-slot:body-cell-context="props">
          <q-td :props="props">
            <div
              style="white-space: normal; word-break: break-word"
              v-text="formatWasmContext(props.row)"
            ></div>
          </q-td>
        </template>
        <template v-slot:body-cell-actions="props">
          <q-td :props="props">
            <div class="row justify-end q-gutter-xs">
              <q-btn
                dense
                flat
                color="negative"
                icon="stop_circle"
                @click="stopWasmInvocation(props.row.id)"
              >
                <q-tooltip>Stop Invocation</q-tooltip>
              </q-btn>
              <q-btn
                dense
                unelevated
                color="negative"
                label="Deactivate Extension"
                @click="deactivateWasmExtension(props.row.extension_id)"
              ></q-btn>
            </div>
          </q-td>
        </template>
      </q-table>
      <q-table
        dense
        flat
        wrap-cells
        :rows="wasmInvocationHistory"
        :columns="wasmHistoryColumns"
        row-key="id"
        :loading="wasmHistoryLoading"
        :pagination="{rowsPerPage: 10}"
        table-style="table-layout: fixed; width: 100%"
        title="Recent Invocations"
      >
        <template v-slot:body-cell-extension_id="props">
          <q-td :props="props">
            <q-btn
              dense
              flat
              no-caps
              color="primary"
              :label="props.row.extension_id"
              :to="`/admin/extensions/wasm/${encodeURIComponent(props.row.extension_id)}`"
            ></q-btn>
          </q-td>
        </template>
        <template v-slot:body-cell-trigger_type="props">
          <q-td :props="props">
            <q-badge
              outline
              :color="wasmTriggerColor(props.row.trigger_type)"
              v-text="props.row.trigger_type"
            ></q-badge>
          </q-td>
        </template>
        <template v-slot:body-cell-status="props">
          <q-td :props="props">
            <q-badge
              :color="wasmStatusColor(props.row.status)"
              v-text="props.row.status"
            ></q-badge>
          </q-td>
        </template>
        <template v-slot:body-cell-user_id="props">
          <q-td :props="props">
            <span v-if="props.row.user_id">
              <span v-text="formatWasmUserId(props.row.user_id)"></span>
              <q-tooltip v-text="props.row.user_id"></q-tooltip>
            </span>
            <span v-else>-</span>
          </q-td>
        </template>
        <template v-slot:body-cell-started_at="props">
          <q-td
            :props="props"
            v-text="formatWasmDate(props.row.started_at)"
          ></q-td>
        </template>
        <template v-slot:body-cell-duration_ms="props">
          <q-td :props="props" v-text="formatWasmDuration(props.row)"></q-td>
        </template>
        <template v-slot:body-cell-calls="props">
          <q-td :props="props" v-text="formatWasmCalls(props.row)"></q-td>
        </template>
        <template v-slot:body-cell-context="props">
          <q-td :props="props">
            <div
              style="white-space: normal; word-break: break-word"
              v-text="formatWasmContext(props.row)"
            ></div>
          </q-td>
        </template>
        <template v-slot:body-cell-error_message="props">
          <q-td :props="props">
            <span
              style="white-space: normal; word-break: break-word"
              v-text="props.row.error_message || props.row.stop_reason || ''"
            ></span>
          </q-td>
        </template>
      </q-table>
    </div>
  </q-card-section>
</template>
