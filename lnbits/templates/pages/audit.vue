<template id="page-audit">
  <div class="row q-col-gutter-md q-mb-md">
    <div class="col-12">
      <q-card>
        <div class="q-pa-sm q-pl-lg">
          <div class="row items-center justify-between q-gutter-xs">
            <div class="col">
              <!-- Optional: Add content here if needed -->
            </div>
            <div>
              <q-btn
                v-if="g.user.admin"
                flat
                round
                icon="settings"
                to="/admin#audit"
              >
                <q-tooltip v-text="$t('admin_settings')"></q-tooltip>
              </q-btn>
            </div>
          </div>
        </div>
      </q-card>
    </div>
  </div>
  <div class="row q-col-gutter-md justify-center q-mb-lg">
    <div class="col-lg-3 col-md-6 col-sm-12 text-center">
      <q-card class="q-pt-sm">
        <strong v-text="$t('components')"></strong>
        <div style="width: 250px" class="q-pa-sm">
          <canvas v-if="chartsReady" ref="componentUseChart"></canvas>
        </div>
      </q-card>
    </div>
    <div class="col-lg-3 col-md-6 col-sm-12 text-center">
      <q-card class="q-pt-sm">
        <strong v-text="$t('long_running_endpoints')"></strong>
        <div style="width: 250px; height: 250px" class="q-pa-sm">
          <canvas v-if="chartsReady" ref="longDurationChart"></canvas>
        </div>
      </q-card>
    </div>
    <div class="col-lg-3 col-md-6 col-sm-12 text-center">
      <q-card class="q-pt-sm">
        <strong v-text="$t('http_request_methods')"></strong>
        <div style="width: 250px; height: 250px" class="q-pa-sm">
          <canvas v-if="chartsReady" ref="requestMethodChart"></canvas>
        </div>
      </q-card>
    </div>
    <div class="col-lg-3 col-md-6 col-sm-12 text-center">
      <q-card class="q-pt-sm">
        <strong v-text="$t('http_response_codes')"></strong>
        <div style="width: 250px; height: 250px" class="q-pa-sm">
          <canvas v-if="chartsReady" ref="responseCodeChart"></canvas>
        </div>
      </q-card>
    </div>
  </div>

  <div class="row q-col-gutter-md justify-center">
    <div class="col">
      <q-card class="q-pa-md">
        <q-table
          row-key="id"
          :rows="auditEntries"
          :columns="auditTable.columns"
          v-model:pagination="auditTable.pagination"
          :filter="auditTable.search"
          :loading="auditTable.loading"
          @request="fetchAudit"
        >
          <template v-slot:header="props">
            <q-tr :props="props">
              <q-th v-for="col in props.cols" :key="col.name" :props="props">
                <q-input
                  v-if="['ip_address', 'user_id', 'path'].includes(col.name)"
                  v-model="searchData[col.name]"
                  @keydown.enter="searchAuditBy()"
                  @update:model-value="searchAuditBy()"
                  dense
                  type="text"
                  filled
                  clearable
                  :label="col.label"
                >
                  <template v-slot:append>
                    <q-icon
                      name="search"
                      @click="searchAuditBy()"
                      class="cursor-pointer"
                    />
                  </template>
                </q-input>

                <q-select
                  v-else-if="
                    ['component', 'response_code', 'request_method'].includes(
                      col.name
                    )
                  "
                  v-model="searchData[col.name]"
                  :options="searchOptions[col.name]"
                  @update:model-value="searchAuditBy()"
                  :label="col.label"
                  clearable
                  style="width: 100px"
                ></q-select>

                <span v-else v-text="col.label"></span>
              </q-th>
            </q-tr>
          </template>
          <template v-slot:body="props">
            <q-tr auto-width :props="props">
              <q-td v-for="col in props.cols" :key="col.name" :props="props">
                <div v-if="col.name == 'created_at'">
                  <q-btn
                    icon="description"
                    :disable="!props.row.request_details"
                    size="sm"
                    flat
                    class="cursor-pointer q-mr-xs"
                    @click="showDetailsDialog(props.row)"
                  >
                    <q-tooltip
                      ><span v-text="$t('request_details')"></span
                    ></q-tooltip>
                  </q-btn>

                  <span v-text="formatDate(props.row.created_at)"></span>
                  <q-tooltip v-if="props.row.delete_at">
                    <span
                      v-text="
                        'Will be deleted at: ' + formatDate(props.row.delete_at)
                      "
                    ></span>
                  </q-tooltip>
                </div>
                <div
                  v-else-if="['user_id', 'request_details'].includes(col.name)"
                >
                  <q-btn
                    v-if="props.row[col.name]"
                    icon="content_copy"
                    size="sm"
                    flat
                    class="cursor-pointer q-mr-xs"
                    @click="copyText(props.row[col.name])"
                  >
                    <q-tooltip>Copy</q-tooltip>
                  </q-btn>
                  <span v-text="shortify(props.row[col.name])"> </span>
                  <q-tooltip>
                    <span v-text="props.row[col.name]"></span>
                  </q-tooltip>
                </div>
                <span
                  v-else
                  v-text="props.row[col.name]"
                  @click="searchAuditBy(col.name, props.row[col.name])"
                  class="cursor-pointer"
                ></span>
              </q-td>
            </q-tr>
          </template>
        </q-table>
      </q-card>
    </div>
  </div>

  <q-dialog v-model="auditDetailsDialog.show" position="top">
    <q-card class="q-pa-md q-pt-md lnbits__dialog-card">
      <strong v-text="$t('http_request_details')"></strong>
      <q-input
        filled
        dense
        v-model.trim="auditDetailsDialog.data"
        type="textarea"
        rows="25"
      ></q-input>

      <div class="row q-mt-lg">
        <q-btn
          @click="copyText(auditDetailsDialog.data)"
          icon="copy_content"
          color="grey"
          flat
          v-text="$t('copy')"
        ></q-btn>
        <q-btn
          v-close-popup
          flat
          color="grey"
          class="q-ml-auto"
          v-text="$t('close')"
        ></q-btn>
      </div>
    </q-card>
  </q-dialog>
</template>
