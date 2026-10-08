<template id="page-scheduler">
  <div>
    <div class="row items-center justify-between q-mb-md">
      <h1 class="text-h6 q-my-none" v-text="$t('scheduler')"></h1>
      <q-btn
        flat
        icon="refresh"
        :label="$t('scheduler_refresh')"
        :loading="jobsTable.loading"
        @click="fetchJobs()"
      ></q-btn>
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
          <span v-text="props.row.handler"></span>
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
    </q-table>
  </div>
</template>
