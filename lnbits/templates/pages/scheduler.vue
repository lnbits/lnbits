<template id="page-scheduler">
  <div>
    <div class="row items-center justify-between q-mb-md">
      <h1 class="text-h6 q-my-none" v-text="$t('scheduler')"></h1>
      <div class="row q-gutter-xs">
        <q-btn
          flat
          icon="history"
          :label="$t('scheduler_history')"
          @click="openHistory()"
        ></q-btn>
        <q-btn
          flat
          icon="refresh"
          :label="$t('scheduler_refresh')"
          :loading="jobsTable.loading"
          @click="fetchJobs()"
        ></q-btn>
        <q-btn
          flat
          round
          icon="settings"
          to="/admin#scheduler"
          :aria-label="$t('settings')"
        ></q-btn>
      </div>
    </div>
    <q-table
      row-key="id"
      :rows="jobs"
      :columns="columns"
      v-model:pagination="jobsTable.pagination"
      :rows-per-page-options="[10, 25, 50, 100]"
      :loading="jobsTable.loading"
      :no-data-label="
        $t(loadError ? 'scheduler_load_error' : 'scheduler_no_jobs')
      "
      @request="fetchJobs"
      @row-click="(_event, job) => openHistory(job)"
    >
      <template v-slot:top>
        <div class="row q-col-gutter-md full-width">
          <div class="col-12 col-sm-6">
            <q-input
              v-model="jobsTable.search"
              :label="$t('scheduler_search')"
              debounce="300"
              outlined
              dense
              clearable
              @update:model-value="filterJobs"
            >
              <template v-slot:prepend
                ><q-icon name="search"></q-icon
              ></template>
            </q-input>
          </div>
          <div class="col-6 col-sm-3">
            <q-select
              v-model="source"
              :options="sourceOptions"
              :label="$t('scheduler_source')"
              emit-value
              map-options
              outlined
              dense
              clearable
              @update:model-value="filterJobs"
            ></q-select>
          </div>
          <div class="col-6 col-sm-3">
            <q-select
              v-model="enabled"
              :options="statusOptions"
              :label="$t('status')"
              emit-value
              map-options
              outlined
              dense
              clearable
              @update:model-value="filterJobs"
            ></q-select>
          </div>
        </div>
      </template>
      <template v-slot:body-cell-namespace="props">
        <q-td :props="props" v-text="sourceLabel(props.row.namespace)"></q-td>
      </template>
      <template v-slot:body-cell-handler="props">
        <q-td :props="props">
          <q-btn
            flat
            dense
            no-caps
            color="primary"
            :label="props.row.handler"
            :aria-label="
              $t('scheduler_view_history', {handler: props.row.handler})
            "
            @click.stop="openHistory(props.row)"
          ></q-btn>
          <div class="text-caption text-grey" v-text="props.row.id"></div>
        </q-td>
      </template>
      <template v-slot:body-cell-scope="props">
        <q-td :props="props" v-text="$t('scheduler_' + props.row.scope)"></q-td>
      </template>
      <template v-slot:body-cell-cron_expression="props">
        <q-td :props="props">
          <span v-text="scheduleLabel(props.row.cron_expression)"></span>
          <div class="text-caption text-grey">
            <code
              v-if="
                scheduleLabel(props.row.cron_expression) !==
                props.row.cron_expression
              "
              class="q-mr-sm"
              v-text="props.row.cron_expression"
            ></code>
            <span v-text="props.row.timezone"></span>
          </div>
        </q-td>
      </template>
      <template v-slot:body-cell-next_run_at="props">
        <q-td :props="props">
          <template v-if="props.row.enabled && props.row.next_run_at !== null">
            <span v-text="formatNextRun(props.row)"></span>
            <div
              class="text-caption text-grey"
              v-text="relativeNextRun(props.row)"
            ></div>
          </template>
          <span v-else>—</span>
        </q-td>
      </template>
      <template v-slot:body-cell-enabled="props">
        <q-td :props="props">
          <q-badge
            :color="props.row.enabled ? 'positive' : 'grey'"
            :label="$t(props.row.enabled ? 'enabled' : 'scheduler_paused')"
          ></q-badge>
        </q-td>
      </template>
      <template v-slot:body-cell-last_run_at="props">
        <q-td
          :props="props"
          v-text="formatTime(props.row.last_run_at, props.row.timezone)"
        ></q-td>
      </template>
      <template v-slot:body-cell-last_result="props">
        <q-td :props="props">
          <q-badge
            v-if="props.row.last_result"
            :color="runColor(props.row.last_result)"
            :label="$t('scheduler_run_' + props.row.last_result)"
          ></q-badge>
          <span v-else>—</span>
        </q-td>
      </template>
    </q-table>
    <q-dialog
      v-model="history.show"
      position="right"
      full-height
      @hide="history.requestId++"
    >
      <q-card class="column no-wrap" style="width: 960px; max-width: 100vw">
        <q-card-section class="row items-center q-gutter-sm">
          <div class="col">
            <h2 class="text-h6 q-my-none" v-text="$t('scheduler_history')"></h2>
            <div v-if="history.job" class="text-caption">
              <span
                v-text="
                  sourceLabel(history.job.namespace) +
                  ' / ' +
                  history.job.handler
                "
              ></span>
              <div
                class="text-grey"
                style="overflow-wrap: anywhere"
                v-text="history.job.id"
              ></div>
            </div>
            <div
              v-else
              class="text-caption"
              v-text="$t('scheduler_history_hint')"
            ></div>
          </div>
          <q-btn
            flat
            round
            icon="refresh"
            :loading="history.table.loading"
            :aria-label="$t('scheduler_refresh')"
            @click="fetchHistory()"
          ></q-btn>
          <q-btn
            flat
            round
            icon="close"
            :aria-label="$t('close')"
            v-close-popup
          ></q-btn>
        </q-card-section>
        <q-separator></q-separator>
        <q-card-section class="col scroll">
          <q-table
            flat
            row-key="id"
            :rows="history.runs"
            :columns="historyColumns"
            v-model:pagination="history.table.pagination"
            :rows-per-page-options="[10, 25, 50, 100]"
            :loading="history.table.loading"
            @request="fetchHistory"
            :no-data-label="
              $t(
                history.loadError
                  ? 'scheduler_history_error'
                  : 'scheduler_no_runs'
              )
            "
          >
            <template v-slot:top>
              <div class="row q-col-gutter-sm full-width">
                <div class="col-12 col-sm-8">
                  <q-input
                    v-model="history.table.search"
                    :label="$t('scheduler_search')"
                    dense
                    outlined
                    clearable
                    debounce="300"
                    @update:model-value="filterHistory"
                  >
                    <template v-slot:prepend
                      ><q-icon name="search"></q-icon
                    ></template>
                  </q-input>
                </div>
                <div class="col-12 col-sm-4">
                  <q-select
                    v-model="history.status"
                    :options="runStatusOptions"
                    :label="$t('scheduler_result')"
                    dense
                    outlined
                    clearable
                    emit-value
                    map-options
                    @update:model-value="filterHistory"
                  ></q-select>
                </div>
              </div>
            </template>
            <template v-slot:body-cell-job_id="props">
              <q-td :props="props">
                <div
                  v-text="
                    sourceLabel(props.row.namespace) + ' / ' + props.row.handler
                  "
                ></div>
                <div
                  class="text-caption text-grey"
                  v-text="props.row.job_id"
                ></div>
              </q-td>
            </template>
            <template v-slot:body-cell-started_at="props">
              <q-td :props="props">
                <span
                  v-text="formatTime(props.row.started_at, props.row.timezone)"
                ></span>
                <div
                  class="text-caption text-grey"
                  v-text="
                    $t('scheduler_scheduled_for', {
                      time: formatTime(
                        props.row.scheduled_at,
                        props.row.timezone
                      )
                    })
                  "
                ></div>
              </q-td>
            </template>
            <template v-slot:body-cell-finished_at="props">
              <q-td
                :props="props"
                v-text="formatTime(props.row.finished_at, props.row.timezone)"
              ></q-td>
            </template>
            <template v-slot:body-cell-duration="props">
              <q-td :props="props" v-text="runDuration(props.row)"></q-td>
            </template>
            <template v-slot:body-cell-status="props">
              <q-td :props="props"
                ><q-badge
                  :color="runColor(props.row.status)"
                  :label="$t('scheduler_run_' + props.row.status)"
                ></q-badge
              ></q-td>
            </template>
            <template v-slot:body-cell-error_summary="props">
              <q-td
                :props="props"
                style="white-space: normal; min-width: 180px"
                v-text="props.row.error_summary || '—'"
              ></q-td>
            </template>
          </q-table>
        </q-card-section>
      </q-card>
    </q-dialog>
  </div>
</template>
