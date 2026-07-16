<template id="lnbits-extension-permissions">
  <q-list bordered separator>
    <q-expansion-item
      v-for="permission of displayItems"
      :key="permission.id"
      dense
      expand-separator
      class="q-pt-xs"
    >
      <template v-slot:header>
        <q-item-section>
          <div class="row items-center q-col-gutter-x-md q-row-gutter-sm">
            <q-item-label
              class="text-weight-medium col-auto"
              style="max-width: 100%"
            >
              <span v-text="permission.label"></span>
            </q-item-label>
            <div
              v-if="permission.risk.level !== 'low' || permission.badges.length"
              class="row items-center q-gutter-xs col-auto q-mb-xs"
              style="max-width: 100%"
            >
              <q-badge
                v-for="badge of permission.badges"
                :key="badge.key"
                outline
                color="primary"
                v-text="badge.label"
              ></q-badge>
              <q-badge
                v-if="permission.risk.level !== 'low'"
                :color="permission.risk.color"
                v-text="permission.risk.label"
              ></q-badge>
            </div>
          </div>
        </q-item-section>
      </template>

      <div class="q-px-md q-pb-sm">
        <div
          v-if="permission.risk.warning"
          class="row items-center text-negative text-caption q-mb-xs"
        >
          <q-icon name="warning" size="16px" class="q-mr-xs"></q-icon>
          <span v-text="permission.risk.warning"></span>
        </div>
        <p
          v-for="description of permission.descriptions"
          :key="description"
          class="text-caption q-mb-xs"
          v-text="description"
        ></p>
        <p
          v-for="policy of permission.invoicePolicies"
          :key="policy.table + ':' + policy.walletField"
          class="text-caption q-mb-xs"
          v-text="publicInvoicePolicySentence(policy)"
        ></p>
        <ul v-if="permission.fieldGroups.length" class="q-my-sm q-pl-md">
          <li v-for="group of permission.fieldGroups" :key="group.table">
            <div class="row items-center q-gutter-xs">
              <span v-text="group.table"></span>
              <template v-if="group.sourceIdField">
                <q-badge
                  color="warning"
                  text-color="dark"
                  v-text="group.sourceIdField"
                ></q-badge>
                <span
                  class="text-caption text-grey"
                  v-text="
                    $t(
                      'extension_permission_ext_storage_read_public_source_required'
                    )
                  "
                ></span>
              </template>
            </div>
            <ul v-if="group.fields.length" class="q-pl-md">
              <li
                v-for="field of group.fields"
                :key="group.table + ':' + field"
                v-text="field"
              ></li>
            </ul>
          </li>
        </ul>
        <div v-if="permission.appendPolicies.length" class="q-mt-sm">
          <div
            class="text-caption text-grey"
            v-text="
              $t('extension_permission_ext_storage_append_public_sources')
            "
          ></div>
          <ul class="q-my-sm q-pl-md">
            <li
              v-for="policy of permission.appendPolicies"
              :key="
                policy.table +
                ':' +
                policy.sourceTable +
                ':' +
                policy.sourceIdField
              "
            >
              <span v-text="publicAppendPolicySentence(policy)"></span>
              <q-input
                v-if="editableAppendPublicLimits"
                v-model.number="policy.rawPolicy.max_rows_per_source"
                type="number"
                dense
                outlined
                class="q-mt-sm q-mb-sm"
                style="max-width: 240px"
                :min="1"
                :max="maxRowsPerSourceLimit"
                :label="
                  $t(
                    'extension_permission_ext_storage_append_public_max_rows_per_source'
                  )
                "
              ></q-input>
              <ul v-if="policy.allowedFields.length" class="q-pl-md">
                <li
                  v-for="field of policy.allowedFields"
                  :key="policy.table + ':' + field"
                  v-text="field"
                ></li>
              </ul>
            </li>
          </ul>
        </div>
        <div v-if="permission.extensionAccess.length" class="q-mt-sm">
          <div
            class="text-caption text-grey"
            v-text="$t('extension_permission_extension_api_request_extensions')"
          ></div>
          <div
            v-for="target of permission.extensionAccess"
            :key="target.id"
            class="row items-center q-gutter-xs q-mt-xs"
          >
            <span class="text-caption" v-text="target.name"></span>
            <q-badge
              v-for="access of target.access"
              :key="target.id + access"
              color="grey-7"
              v-text="permissionAccessLabel(access)"
            ></q-badge>
          </div>
        </div>
        <div v-if="permission.httpHosts.length" class="q-mt-sm">
          <div
            class="text-caption text-grey"
            v-text="$t('extension_permission_http_request_hosts')"
          ></div>
          <ul class="q-my-sm q-pl-md">
            <li
              v-for="host of permission.httpHosts"
              :key="host"
              v-text="host"
            ></li>
          </ul>
        </div>
      </div>
    </q-expansion-item>
  </q-list>
</template>
