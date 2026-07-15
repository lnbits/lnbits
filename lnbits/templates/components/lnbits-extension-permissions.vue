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
          <q-item-label class="text-weight-medium">
            <span v-text="permission.label"></span>
          </q-item-label>
        </q-item-section>
        <q-item-section
          v-if="permission.risk.level !== 'low' || permission.badges.length"
          side
          top
        >
          <div class="row items-center justify-end q-gutter-xs">
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
            <span v-text="group.table"></span>
            <ul v-if="group.fields.length" class="q-pl-md">
              <li
                v-for="field of group.fields"
                :key="group.table + ':' + field"
                v-text="field"
              ></li>
            </ul>
          </li>
        </ul>
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
