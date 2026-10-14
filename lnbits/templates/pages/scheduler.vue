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
          <div class="col-12 col-sm-3">
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
          <div class="col-12 col-sm-3">
            <q-input
              v-model="userId"
              :label="$t('user_id')"
              debounce="300"
              outlined
              dense
              clearable
              @update:model-value="filterJobs"
            ></q-input>
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
      <template v-slot:body-cell-user_id="props">
        <q-td
          :props="props"
          :title="props.row.user_id"
          v-text="userLabel(props.row)"
        ></q-td>
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
  </div>
</template>
