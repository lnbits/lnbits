<template id="page-scheduler-runs">
  <div>
    <div class="row items-center justify-between q-mb-md">
      <div>
        <h1 class="text-h6 q-my-none" v-text="$t('scheduler_history')"></h1>
        <div class="text-caption" v-text="$t('scheduler_history_hint')"></div>
      </div>
      <div class="row q-gutter-xs">
        <q-btn
          flat
          icon="arrow_back"
          :label="$t('scheduler')"
          to="/scheduler"
        ></q-btn>
        <q-btn
          flat
          icon="refresh"
          :label="$t('scheduler_refresh')"
          :loading="runsTable.loading"
          @click="fetchRuns()"
        ></q-btn>
      </div>
    </div>
    <q-table
      row-key="id"
      :rows="runs"
      :columns="columns"
      v-model:pagination="runsTable.pagination"
      :rows-per-page-options="[10, 25, 50, 100]"
      :loading="runsTable.loading"
      @request="fetchRuns"
      :no-data-label="
        $t(loadError ? 'scheduler_history_error' : 'scheduler_no_runs')
      "
    >
      <template v-slot:top>
        <div class="row q-col-gutter-md full-width">
          <div class="col-12">
            <q-input
              v-model="runsTable.search"
              :label="$t('scheduler_search')"
              dense
              outlined
              clearable
              debounce="300"
              @update:model-value="filterRuns"
            >
              <template v-slot:prepend
                ><q-icon name="search"></q-icon
              ></template>
            </q-input>
          </div>
          <div class="col-12 col-sm-6 col-md-3">
            <q-input
              v-model="jobId"
              :label="$t('scheduler_job_id')"
              dense
              outlined
              clearable
              debounce="300"
              @update:model-value="filterRuns"
            ></q-input>
          </div>
          <div class="col-12 col-sm-6 col-md-3">
            <q-input
              v-model="namespace"
              :label="$t('scheduler_namespace')"
              dense
              outlined
              clearable
              debounce="300"
              @update:model-value="filterRuns"
            ></q-input>
          </div>
          <div class="col-12 col-sm-6 col-md-3">
            <q-input
              v-model="userId"
              :label="$t('user_id')"
              dense
              outlined
              clearable
              debounce="300"
              @update:model-value="filterRuns"
            ></q-input>
          </div>
          <div class="col-12 col-sm-6 col-md-3">
            <q-select
              v-model="status"
              :options="statusOptions"
              :label="$t('status')"
              dense
              outlined
              clearable
              emit-value
              map-options
              @update:model-value="filterRuns"
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
          <div class="text-caption text-grey" v-text="props.row.job_id"></div>
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
                time: formatTime(props.row.scheduled_at, props.row.timezone)
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
  </div>
</template>
