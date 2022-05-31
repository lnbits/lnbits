/* global Vue, VueQrcode, _, Quasar, LOCALE, windowMixin, LNbits */

Vue.component(VueQrcode.name, VueQrcode)

var mapBleskomat = function (obj) {
  obj._data = _.clone(obj)
  return obj
}

var defaultValues = {
  name: 'My Bleskomat',
  fiat_currency: 'EUR',
  exchange_rate_provider: 'coinbase',
  fee: '0.00'
}

new Vue({
  el: '#vue',
  mixins: [windowMixin],
  data: function () {
    return {
      checker: null,
      bleskomats: [],
      bleskomatsTable: {
        columns: [
          {
            name: 'api_key_id',
            align: 'left',
            label: 'API Key ID',
            field: 'api_key_id'
          },
          {
            name: 'name',
            align: 'left',
            label: 'Name',
            field: 'name'
          },
          {
            name: 'fiat_currency',
            align: 'left',
            label: 'Fiat Currency',
            field: 'fiat_currency'
          },
          {
            name: 'exchange_rate_provider',
            align: 'left',
            label: 'Exchange Rate Provider',
            field: 'exchange_rate_provider'
          },
          {
            name: 'fee',
            align: 'left',
            label: 'Fee (%)',
            field: 'fee'
          }
        ],
        pagination: {
          rowsPerPage: 10
        }
      },
      formDialog: {
        show: false,
        fiatCurrencies: _.keys(window.bleskomat_vars.fiat_currencies),
        exchangeRateProviders: _.keys(
          window.bleskomat_vars.exchange_rate_providers
        ),
        data: _.clone(defaultValues)
      }
    }
  },
  computed: {
    sortedBleskomats: function () {
      return this.bleskomats.sort(function (a, b) {
        // Sort by API Key ID alphabetically.
        var apiKeyId_A = a.api_key_id.toLowerCase()
        var apiKeyId_B = b.api_key_id.toLowerCase()
        return apiKeyId_A < apiKeyId_B ? -1 : apiKeyId_A > apiKeyId_B ? 1 : 0
      })
    }
  },
  methods: {
    getBleskomats: function () {
      var self = this
      LNbits.api
        .request(
          'GET',
          '/bleskomat/api/v1/bleskomats?all_wallets',
          this.g.user.wallets[0].adminkey
        )
        .then(function (response) {
          self.bleskomats = response.data.map(function (obj) {
            return mapBleskomat(obj)
          })
        })
        .catch(function (error) {
          clearInterval(self.checker)
          LNbits.utils.notifyApiError(error)
        })
    },
    closeFormDialog: function () {
      this.formDialog.data = _.clone(defaultValues)
    },
    exportConfigFile: function (bleskomatId) {
      var bleskomat = _.findWhere(this.bleskomats, {id: bleskomatId})
      var fieldToKey = {
        api_key_id: 'apiKey.id',
        api_key_secret: 'apiKey.key',
        api_key_encoding: 'apiKey.encoding',
        fiat_currency: 'fiatCurrency'
      }
      var lines = _.chain(bleskomat)
        .map(function (value, field) {
          var key = fieldToKey[field] || null
          return key ? [key, value].join('=') : null
        })
        .compact()
        .value()
      lines.push('callbackUrl=' + window.bleskomat_vars.callback_url)
      lines.push('shorten=true')
      var content = lines.join('\n')
      var status = Quasar.utils.exportFile(
        'bleskomat.conf',
        content,
        'text/plain'
      )
      if (status !== true) {
        Quasar.plugins.Notify.create({
          message: 'Browser denied file download...',
          color: 'negative',
          icon: null
        })
      }
    },
    openUpdateDialog: function (bleskomatId) {
      var bleskomat = _.findWhere(this.bleskomats, {id: bleskomatId})
      this.formDialog.data = _.clone(bleskomat._data)
      this.formDialog.show = true
    },
    sendFormData: function () {
      var wallet = _.findWhere(this.g.user.wallets, {
        id: this.formDialog.data.wallet
      })
      var data = _.omit(this.formDialog.data, 'wallet')
      if (data.id) {
        this.updateBleskomat(wallet, data)
      } else {
        this.createBleskomat(wallet, data)
      }
    },
    updateBleskomat: function (wallet, data) {
      var self = this
      LNbits.api
        .request(
          'PUT',
          '/bleskomat/api/v1/bleskomat/' + data.id,
          wallet.adminkey,
          _.pick(data, 'name', 'fiat_currency', 'exchange_rate_provider', 'fee')
        )
        .then(function (response) {
          self.bleskomats = _.reject(self.bleskomats, function (obj) {
            return obj.id === data.id
          })
          self.bleskomats.push(mapBleskomat(response.data))
          self.formDialog.show = false
        })
        .catch(function (error) {
          LNbits.utils.notifyApiError(error)
        })
    },
    createBleskomat: function (wallet, data) {
      var self = this
      LNbits.api
        .request('POST', '/bleskomat/api/v1/bleskomat', wallet.adminkey, data)
        .then(function (response) {
          self.bleskomats.push(mapBleskomat(response.data))
          self.formDialog.show = false
        })
        .catch(function (error) {
          LNbits.utils.notifyApiError(error)
        })
    },
    deleteBleskomat: function (bleskomatId) {
      var self = this
      var bleskomat = _.findWhere(this.bleskomats, {id: bleskomatId})
      LNbits.utils
        .confirmDialog(
          'Are you sure you want to delete "' + bleskomat.name + '"?'
        )
        .onOk(function () {
          LNbits.api
            .request(
              'DELETE',
              '/bleskomat/api/v1/bleskomat/' + bleskomatId,
              _.findWhere(self.g.user.wallets, {id: bleskomat.wallet}).adminkey
            )
            .then(function (response) {
              self.bleskomats = _.reject(self.bleskomats, function (obj) {
                return obj.id === bleskomatId
              })
            })
            .catch(function (error) {
              LNbits.utils.notifyApiError(error)
            })
        })
    }
  },
  created: function () {
    if (this.g.user.wallets.length) {
      var getBleskomats = this.getBleskomats
      getBleskomats()
      this.checker = setInterval(function () {
        getBleskomats()
      }, 20000)
    }
  }
})
