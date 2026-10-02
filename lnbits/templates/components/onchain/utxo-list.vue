<template id="onchain-utxo-list">
  <div>
    <div class="row items-center q-mb-md">
      <div v-if="selectable" class="col-9 col-sm-5 q-pr-sm">
        <q-select
          filled
          dense
          emit-value
          v-model="utxoSelectionMode"
          :options="utxoSelectionModes"
          :label="$t('onchain.selection_mode')"
          @update:model-value="updateUtxoSelection"
        ></q-select>
      </div>
      <div v-if="selectable" class="col-3 col-sm-1">
        <q-btn
          outline
          icon="refresh"
          color="grey"
          @click="updateUtxoSelection"
          class="q-ml-sm"
        ></q-btn>
      </div>
      <div v-if="selectable" class="col-sm-2"></div>
      <div class="col-12" :class="{'col-sm-4': selectable}">
        <q-input
          borderless
          dense
          debounce="300"
          v-model="filterLocal"
          :placeholder="$t('onchain.search')"
        >
          <template v-slot:append>
            <q-icon name="search"></q-icon>
          </template>
        </q-input>
      </div>
    </div>

    <q-table
      flat
      dense
      :rows="utxos"
      :row-key="row => row.txId + ':' + row.vout"
      :columns="columns"
      v-model:pagination="utxosTable.pagination"
      :filter="filterLocal"
    >
      <template v-slot:body="props">
        <q-tr :props="props">
          <q-td auto-width>
            <q-btn
              size="sm"
              color="primary"
              round
              dense
              @click="props.row.expanded = !props.row.expanded"
              :icon="props.row.expanded ? 'remove' : 'add'"
            ></q-btn>
          </q-td>

          <q-td v-if="selectable" key="selected" :props="props">
            <div>
              <q-checkbox v-model="props.row.selected"></q-checkbox>
            </div>
          </q-td>
          <q-td key="status" :props="props">
            <div>
              <q-badge
                v-if="props.row.confirmed"
                @click="props.row.expanded = !props.row.expanded"
                color="primary"
                class="q-mr-md cursor-pointer"
                v-text="$t('onchain.confirmed')"
              >
              </q-badge>
              <q-badge
                v-if="!props.row.confirmed"
                @click="props.row.expanded = !props.row.expanded"
                color="secondary"
                class="q-mr-md cursor-pointer"
                v-text="$t('onchain.pending')"
              >
              </q-badge>
            </div>
          </q-td>
          <q-td key="address" :props="props">
            <div>
              <a
                style="color: unset"
                :href="mempoolEndpoint + '/address/' + props.row.address"
                target="_blank"
                v-text="props.row.address"
              ></a>
              <q-badge
                v-if="props.row.isChange"
                color="primary"
                class="q-mr-md"
                v-text="$t('onchain.change')"
              >
              </q-badge>
              <q-badge
                v-if="props.row.accountType === 'p2tr'"
                color="yellow"
                text-color="black"
                v-text="$t('onchain.taproot')"
              >
              </q-badge>
            </div>
          </q-td>

          <q-td
            key="amount"
            :props="props"
            class="text-green-13 text-weight-bold"
          >
            <div v-text="satBtc(props.row.amount)"></div>
          </q-td>
          <q-td key="date" :props="props" v-text="props.row.date"></q-td>
        </q-tr>
        <q-tr v-show="props.row.expanded" :props="props">
          <q-td colspan="100%">
            <div class="row items-center q-mb-md">
              <div
                class="col-2 q-pr-lg"
                v-text="$t('onchain.transaction_id')"
              ></div>
              <div class="col-10 q-pr-lg">
                <a
                  style="color: unset"
                  :href="mempoolEndpoint + '/tx/' + props.row.txId"
                  target="_blank"
                  v-text="props.row.txId"
                ></a>
              </div>
            </div>
          </q-td>
        </q-tr>
      </template>
    </q-table>
  </div>
</template>
