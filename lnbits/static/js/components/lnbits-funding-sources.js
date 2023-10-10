Vue.component('lnbits-funding-sources', {
  mixins: [windowMixin],
  props: ['form-data', 'allowed-funding-sources'],
  computed: {
    fundingSources() {
      let tmp = []
      for (const [key, _, obj] of this.rawFundingSources) {
        const tmpObj = {}
        if (obj !== null) {
          for (let [k, v] of Object.entries(obj)) {
            tmpObj[k] = {label: v, value: null}
          }
        }
        tmp.push([key, tmpObj])
      }
      return new Map(tmp)
    }
  },
  data() {
    return {
      rawFundingSources: [
        ['VoidWallet', 'Void Wallet', null],
        [
          'FakeWallet',
          'Fake Wallet',
          {
            fake_wallet_secret: 'Secret'
          }
        ],
        [
          'CoreLightningWallet',
          'Core Lightning',
          {
            corelightning_rpc: 'Endpoint'
          }
        ],
        [
          'CoreLightningRestWallet',
          'Core Lightning Rest',
          {
            corelightning_rest_url: 'Endpoint',
            corelightning_rest_cert: 'Certificate',
            corelightning_rest_macaroon: 'Macaroon'
          }
        ],
        [
          'LndRestWallet',
          'Lightning Network Daemon (LND Rest)',
          {
            lnd_rest_endpoint: 'Endpoint',
            lnd_rest_cert: 'Certificate',
            lnd_rest_macaroon: 'Macaroon',
            lnd_rest_macaroon_encrypted: 'Encrypted Macaroon'
          }
        ],
        [
          'LndWallet',
          'Lightning Network Daemon (LND)',
          {
            lnd_grpc_endpoint: 'Endpoint',
            lnd_grpc_cert: 'Certificate',
            lnd_grpc_port: 'Port',
            lnd_grpc_admin_macaroon: 'Admin Macaroon',
            lnd_grpc_macaroon_encrypted: 'Encrypted Macaroon'
          }
        ],
        [
          'LnTipsWallet',
          'LN.Tips',
          {
            lntips_api_endpoint: 'Endpoint',
            lntips_api_key: 'API Key'
          }
        ],
        [
          'LNPayWallet',
          'LN Pay',
          {
            lnpay_api_endpoint: 'Endpoint',
            lnpay_api_key: 'API Key',
            lnpay_wallet_key: 'Wallet Key'
          }
        ],
        [
          'EclairWallet',
          'Eclair (ACINQ)',
          {
            eclair_url: 'URL',
            eclair_pass: 'Password'
          }
        ],
        [
          'LNbitsWallet',
          'LNBits',
          {
            lnbits_endpoint: 'Endpoint',
            lnbits_key: 'Admin Key'
          }
        ],
        [
          'OpenNodeWallet',
          'OpenNode',
          {
            opennode_api_endpoint: 'Endpoint',
            opennode_key: 'Key'
          }
        ],
        [
          'ClicheWallet',
          'Cliche (NBD)',
          {
            cliche_endpoint: 'Endpoint'
          }
        ],
        [
          'SparkWallet',
          'Spark',
          {
            spark_url: 'Endpoint',
            spark_token: 'Token'
          }
        ]
      ]
    }
  },
  template: `
    <div class="funding-sources">
        <h6 class="q-mt-xl q-mb-md">Funding Sources</h6>
        <div class="row">
          <div class="col-12">
            <p>Active Funding<small> (Requires server restart)</small></p>
            <q-select
              filled
              v-model="formData.lnbits_backend_wallet_class"
              hint="Select the active funding wallet"
              :options="allowedFundingSources"
            ></q-select>
          </div>
        </div>
        <q-list
          class="q-mt-md"
          v-for="(fund, idx) in allowedFundingSources"
          :key="idx"
        >
          <div v-if="fundingSources.get(fund) && fund === formData.lnbits_backend_wallet_class">
            <div class="row"
              v-for="([key, prop], i) in Object.entries(fundingSources.get(fund))"
              :key="i"
            >
              <div class="col-12">
                <q-input
                  filled
                  type="text"
                  class="q-mt-sm"
                  v-model="formData[key]"
                  :label="prop.label"
                  :hint="prop.hint"
                ></q-input>
              </div>
            </div>
          </div>
        </q-list>
    </div>
  `
})
