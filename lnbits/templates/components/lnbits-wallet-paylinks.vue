<template id="lnbits-wallet-paylinks">
  <q-expansion-item
    group="extras"
    icon="qr_code"
    v-if="storedPaylinks.length > 0"
    :label="$t('stored_paylinks')"
  >
    <q-card>
      <q-card-section>
        <div class="row flex" v-for="paylink in storedPaylinks">
          <q-btn
            dense
            flat
            color="primary"
            icon="send"
            size="xs"
            @click="sendToPaylink(paylink.lnurl)"
          >
            <q-tooltip>
              <span v-text="`send to: ${paylink.lnurl}`"></span>
            </q-tooltip>
          </q-btn>
          <q-btn
            dense
            flat
            color="secondary"
            icon="content_copy"
            size="xs"
            @click="utils.copyText(paylink.lnurl)"
          >
            <q-tooltip>
              <span v-text="`copy: ${paylink.lnurl}`"></span>
            </q-tooltip>
          </q-btn>
          <span v-text="paylink.label" class="q-mr-xs q-ml-xs"></span>
          <q-btn dense flat color="primary" icon="edit" size="xs">
            <q-popup-edit
              @update:model-value="editPaylink()"
              v-model="paylink.label"
              v-slot="scope"
            >
              <q-input
                dark
                color="white"
                v-model="scope.value"
                dense
                autofocus
                counter
                @keyup.enter="scope.set"
              >
                <template v-slot:append>
                  <q-icon name="edit" />
                </template>
              </q-input>
            </q-popup-edit>
            <q-tooltip>
              <span v-text="$t('edit')"></span>
            </q-tooltip>
          </q-btn>
          <span style="flex-grow: 1"></span>
          <q-btn
            dense
            flat
            color="red"
            icon="delete"
            size="xs"
            @click="deletePaylink(paylink.lnurl)"
          >
            <q-tooltip>
              <span v-text="$t('delete')"></span>
            </q-tooltip>
          </q-btn>
          <span v-text="utils.formatTimestampFrom(paylink.last_used)"></span>
        </div>
      </q-card-section>
    </q-card>
  </q-expansion-item>
</template>
