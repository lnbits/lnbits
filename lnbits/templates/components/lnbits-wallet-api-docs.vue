<template id="lnbits-wallet-api-docs">
  <q-expansion-item
    group="extras"
    icon="vpn_key"
    :label="$t('api_keys_api_docs')"
    :content-inset-level="0.5"
  >
    <q-card-section>
      <q-list>
        <q-item dense class="q-pa-none">
          <q-item-section>
            <q-item-label>
              <strong>Node URL: </strong><em v-text="origin"></em>
            </q-item-label>
          </q-item-section>
        </q-item>
        <q-item dense class="q-pa-none">
          <q-item-section>
            <q-item-label>
              <strong>Wallet ID: </strong><em v-text="g.wallet.id"></em>
            </q-item-label>
          </q-item-section>
          <q-item-section side>
            <q-icon
              name="content_copy"
              class="cursor-pointer"
              @click="utils.copyText(g.wallet.id)"
            ></q-icon>
          </q-item-section>
        </q-item>
        <q-item dense class="q-pa-none">
          <q-item-section>
            <q-item-label>
              <strong>Admin key: </strong
              ><em
                v-text="adminkeyHidden ? '****************' : g.wallet.adminkey"
              ></em>
            </q-item-label>
          </q-item-section>
          <q-item-section side>
            <div>
              <q-icon
                :name="adminkeyHidden ? 'visibility_off' : 'visibility'"
                class="cursor-pointer"
                @click="adminkeyHidden = !adminkeyHidden"
              ></q-icon>
              <q-icon
                name="content_copy"
                class="cursor-pointer q-ml-sm"
                @click="utils.copyText(g.wallet.adminkey)"
              ></q-icon>
              <q-icon name="qr_code" class="cursor-pointer q-ml-sm">
                <q-popup-proxy>
                  <div class="q-pa-md">
                    <lnbits-qrcode
                      :value="g.wallet.adminkey"
                      :show-buttons="false"
                    ></lnbits-qrcode>
                  </div>
                </q-popup-proxy>
              </q-icon>
            </div>
          </q-item-section>
        </q-item>
        <q-item dense class="q-pa-none">
          <q-item-section>
            <q-item-label>
              <strong>Invoice/read key: </strong
              ><em
                v-text="inkeyHidden ? '****************' : g.wallet.inkey"
              ></em>
            </q-item-label>
          </q-item-section>
          <q-item-section side>
            <div>
              <q-icon
                :name="inkeyHidden ? 'visibility_off' : 'visibility'"
                class="cursor-pointer"
                @click="inkeyHidden = !inkeyHidden"
              ></q-icon>
              <q-icon
                name="content_copy"
                class="cursor-pointer q-ml-sm"
                @click="utils.copyText(g.wallet.inkey)"
              ></q-icon>
              <q-icon name="qr_code" class="cursor-pointer q-ml-sm">
                <q-popup-proxy>
                  <div class="q-pa-md">
                    <lnbits-qrcode
                      :value="g.wallet.inkey"
                      :show-buttons="false"
                    ></lnbits-qrcode>
                  </div>
                </q-popup-proxy>
              </q-icon>
            </div>
          </q-item-section>
        </q-item>
      </q-list>
    </q-card-section>
    <q-expansion-item
      v-if="!HIDE_API"
      group="api"
      dense
      expand-separator
      label="Get wallet details"
    >
      <q-card>
        <q-card-section>
          <code><span class="text-light-green">GET</span> /api/v1/wallet</code>
          <h5 class="text-caption q-mt-sm q-mb-none">Headers</h5>
          <code
            >{"X-Api-Key": "<i
              v-text="inkeyHidden ? '****************' : g.wallet.inkey"
            ></i
            >"}</code
          ><br />
          <h5 class="text-caption q-mt-sm q-mb-none">
            Returns 200 OK (application/json)
          </h5>
          <code
            >{"id": &lt;string&gt;, "name": &lt;string&gt;, "balance":
            &lt;int&gt;}</code
          >
          <h5 class="text-caption q-mt-sm q-mb-none">Curl example</h5>
          <code
            >curl <span v-text="baseUrl"></span>api/v1/wallet -H "X-Api-Key:
            <i v-text="inkeyHidden ? '****************' : g.wallet.inkey"></i
            >"</code
          >
        </q-card-section>
      </q-card>
    </q-expansion-item>

    <q-expansion-item
      v-if="!HIDE_API"
      group="api"
      dense
      expand-separator
      label="Create an invoice (incoming)"
    >
      <q-card>
        <q-card-section>
          <code
            ><span class="text-light-green">POST</span> /api/v1/payments</code
          >
          <h5 class="text-caption q-mt-sm q-mb-none">Headers</h5>
          <code
            >{"X-Api-Key": "<i
              v-text="inkeyHidden ? '****************' : g.wallet.inkey"
            ></i
            >"}</code
          ><br />
          <h5 class="text-caption q-mt-sm q-mb-none">
            Body (application/json)
          </h5>
          <code
            >{"out": false, "amount": &lt;int&gt;, "memo": &lt;string&gt;,
            "expiry": &lt;int&gt;, "unit": &lt;string&gt;, "webhook":
            &lt;url:string&gt;, "internal": &lt;bool&gt;}</code
          >
          <h5 class="text-caption q-mt-sm q-mb-none">
            Returns 201 CREATED (application/json)
          </h5>
          <code
            >{"payment_hash": &lt;string&gt;, "payment_request":
            &lt;string&gt;}</code
          >
          <h5 class="text-caption q-mt-sm q-mb-none">Curl example</h5>
          <code
            >curl -X POST <span v-text="baseUrl"></span>api/v1/payments -d
            '{"out": false, "amount": &lt;int&gt;, "memo": &lt;string&gt;}' -H
            "X-Api-Key:
            <i v-text="inkeyHidden ? '****************' : g.wallet.inkey"></i>"
            -H "Content-type: application/json"</code
          >
        </q-card-section>
      </q-card>
    </q-expansion-item>
    <q-expansion-item
      v-if="!HIDE_API"
      group="api"
      dense
      expand-separator
      label="Pay an invoice (outgoing)"
    >
      <q-card>
        <q-card-section>
          <code
            ><span class="text-light-green">POST</span> /api/v1/payments (reveal
            admin keys
            <q-icon
              :name="adminkeyHidden ? 'visibility_off' : 'visibility'"
              class="cursor-pointer"
              @click="adminkeyHidden = !adminkeyHidden"
            ></q-icon
            >)</code
          >
          <h5 class="text-caption q-mt-sm q-mb-none">Headers</h5>
          <code
            >{"X-Api-Key": "<i
              v-text="adminkeyHidden ? '****************' : g.wallet.adminkey"
            ></i
            >"}</code
          >
          <h5 class="text-caption q-mt-sm q-mb-none">
            Body (application/json)
          </h5>
          <code>{"out": true, "bolt11": &lt;string&gt;}</code>
          <h5 class="text-caption q-mt-sm q-mb-none">
            Returns 201 CREATED (application/json)
          </h5>
          <code>{"payment_hash": &lt;string&gt;}</code>
          <h5 class="text-caption q-mt-sm q-mb-none">Curl example</h5>
          <code
            >curl -X POST <span v-text="baseUrl"></span>api/v1/payments -d
            '{"out": true, "bolt11": &lt;string&gt;}' -H "X-Api-Key:
            <i
              v-text="adminkeyHidden ? '****************' : g.wallet.adminkey"
            ></i
            >" -H "Content-type: application/json"</code
          >
        </q-card-section>
      </q-card>
    </q-expansion-item>

    <q-expansion-item
      v-if="!HIDE_API"
      group="api"
      dense
      expand-separator
      label="Decode an invoice"
    >
      <q-card>
        <q-card-section>
          <code
            ><span class="text-light-green">POST</span>
            /api/v1/payments/decode</code
          >
          <h5 class="text-caption q-mt-sm q-mb-none">
            Body (application/json)
          </h5>
          <code>{"data": &lt;string&gt;}</code>
          <h5 class="text-caption q-mt-sm q-mb-none">
            Returns 200 (application/json)
          </h5>
          <h5 class="text-caption q-mt-sm q-mb-none">Curl example</h5>
          <code
            >curl -X POST <span v-text="baseUrl"></span>api/v1/payments/decode
            -d '{"data": &lt;bolt11/lnurl, string&gt;}' -H "Content-type:
            application/json"</code
          >
        </q-card-section>
      </q-card>
    </q-expansion-item>
    <q-expansion-item
      v-if="!HIDE_API"
      group="api"
      dense
      expand-separator
      label="Check an invoice (incoming or outgoing)"
      class="q-pb-md"
    >
      <q-card>
        <q-card-section>
          <code
            ><span class="text-light-blue">GET</span>
            /api/v1/payments/&lt;payment_hash&gt;</code
          >
          <h5 class="text-caption q-mt-sm q-mb-none">Headers</h5>
          <code
            >{"X-Api-Key": "<i
              v-text="inkeyHidden ? '****************' : g.wallet.inkey"
            ></i
            >"}</code
          >
          <h5 class="text-caption q-mt-sm q-mb-none">
            Returns 200 OK (application/json)
          </h5>
          <code>{"paid": &lt;bool&gt;}</code>
          <h5 class="text-caption q-mt-sm q-mb-none">Curl example</h5>
          <code
            >curl -X GET
            <span v-text="baseUrl"></span>api/v1/payments/&lt;payment_hash&gt;
            -H "X-Api-Key:
            <i v-text="inkeyHidden ? '****************' : g.wallet.inkey"></i>"
            -H "Content-type: application/json"</code
          >
        </q-card-section>
      </q-card>
      <q-card>
        <q-card-section>
          <code
            ><span class="text-pink">WS</span>
            /api/v1/ws/&lt;invoice_key&gt;</code
          >
          <h5
            class="text-caption q-mt-sm q-mb-none"
            v-text="$t('websocket_example')"
          ></h5>
          <code
            >wscat -c <span v-text="websocketUrl"></span>/<span
              v-text="inkeyHidden ? '****************' : g.wallet.inkey"
            ></span
          ></code>
          <h5 class="text-caption q-mt-sm q-mb-none">
            Returns 200 OK (application/json)/payments
          </h5>
          <code>{"balance": &lt;int&gt;, "payment": &lt;object&gt;}</code>
        </q-card-section>
      </q-card>
    </q-expansion-item>
    <q-separator></q-separator>
    <q-card-section>
      <p v-text="$t('reset_wallet_keys_desc')"></p>
      <q-btn
        unelevated
        color="red-10"
        @click="resetKeys()"
        :label="$t('reset_wallet_keys')"
      ></q-btn>
    </q-card-section>
  </q-expansion-item>
</template>
