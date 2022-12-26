/* global Vue, VueQrcode, _, Quasar, LOCALE, windowMixin, LNbits */

Vue.component(VueQrcode.name, VueQrcode)

var locationPath = [
  window.location.protocol,
  '//',
  window.location.host,
  window.location.pathname
].join('')

var mapWithdrawLink = function (obj) {
  obj._data = _.clone(obj)
  obj.date = Quasar.utils.date.formatDate(
    new Date(obj.time * 1000),
    'YYYY-MM-DD HH:mm'
  )
  obj.min_fsat = new Intl.NumberFormat(LOCALE).format(obj.min_withdrawable)
  obj.max_fsat = new Intl.NumberFormat(LOCALE).format(obj.max_withdrawable)
  obj.uses_left = obj.uses - obj.used
  obj.print_url = [locationPath, 'print/', obj.id].join('')
  obj.withdraw_url = [locationPath, obj.id].join('')
  obj._data.use_custom = Boolean(obj.custom_url)
  return obj
}

const CUSTOM_URL = '/static/images/default_voucher.png'

new Vue({
  el: '#vue',
  mixins: [windowMixin],
  data: function () {
    return {
      checker: null,
      withdrawLinks: [],
      withdrawLinksTable: {
        columns: [
          {name: 'id', align: 'left', label: 'ID', field: 'id'},
          {name: 'title', align: 'left', label: 'Title', field: 'title'},
          {
            name: 'wait_time',
            align: 'right',
            label: 'Wait',
            field: 'wait_time'
          },
          {
            name: 'uses_left',
            align: 'right',
            label: 'Uses left',
            field: 'uses_left'
          },
          {name: 'min', align: 'right', label: 'Min (sat)', field: 'min_fsat'},
          {name: 'max', align: 'right', label: 'Max (sat)', field: 'max_fsat'}
        ],
        pagination: {
          rowsPerPage: 10
        }
      },
      nfcTagWriting: false,
      formDialog: {
        show: false,
        secondMultiplier: 'seconds',
        secondMultiplierOptions: ['seconds', 'minutes', 'hours'],
        data: {
          is_unique: false,
          use_custom: false,
          has_webhook: false
        }
      },
      simpleformDialog: {
        show: false,
        data: {
          is_unique: true,
          use_custom: false,
          title: 'Vouchers',
          min_withdrawable: 0,
          wait_time: 1
        }
      },
      qrCodeDialog: {
        show: false,
        data: null
      }
    }
  },
  computed: {
    sortedWithdrawLinks: function () {
      return this.withdrawLinks.sort(function (a, b) {
        return b.uses_left - a.uses_left
      })
    }
  },
  methods: {
    getWithdrawLinks: function () {
      var self = this

      LNbits.api
        .request(
          'GET',
          '/withdraw/api/v1/links?all_wallets=true',
          this.g.user.wallets[0].inkey
        )
        .then(function (response) {
          self.withdrawLinks = response.data.map(function (obj) {
            return mapWithdrawLink(obj)
          })
        })
        .catch(function (error) {
          clearInterval(self.checker)
          LNbits.utils.notifyApiError(error)
        })
    },
    closeFormDialog: function () {
      this.formDialog.data = {
        is_unique: false,
        use_custom: false
      }
    },
    simplecloseFormDialog: function () {
      this.simpleformDialog.data = {
        is_unique: false,
        use_custom: false
      }
    },
    openQrCodeDialog: function (linkId) {
      var link = _.findWhere(this.withdrawLinks, {id: linkId})

      this.qrCodeDialog.data = _.clone(link)
      this.qrCodeDialog.data.url =
        window.location.protocol + '//' + window.location.host
      this.qrCodeDialog.show = true
    },
    openUpdateDialog: function (linkId) {
      var link = _.findWhere(this.withdrawLinks, {id: linkId})
      this.formDialog.data = _.clone(link._data)
      this.formDialog.show = true
    },
    sendFormData: function () {
      var wallet = _.findWhere(this.g.user.wallets, {
        id: this.formDialog.data.wallet
      })
      var data = _.omit(this.formDialog.data, 'wallet')

      if (!data.use_custom) {
        data.custom_url = null
      }

      if (data.use_custom && !data?.custom_url) {
        data.custom_url = CUSTOM_URL
      }

      data.wait_time =
        data.wait_time *
        {
          seconds: 1,
          minutes: 60,
          hours: 3600
        }[this.formDialog.secondMultiplier]
      if (data.id) {
        this.updateWithdrawLink(wallet, data)
      } else {
        this.createWithdrawLink(wallet, data)
      }
    },
    simplesendFormData: function () {
      var wallet = _.findWhere(this.g.user.wallets, {
        id: this.simpleformDialog.data.wallet
      })
      var data = _.omit(this.simpleformDialog.data, 'wallet')

      data.wait_time = 1
      data.min_withdrawable = data.max_withdrawable
      data.title = 'vouchers'
      data.is_unique = true

      if (!data.use_custom) {
        data.custom_url = null
      }

      if (data.use_custom && !data?.custom_url) {
        data.custom_url = '/static/images/default_voucher.png'
      }

      if (data.id) {
        this.updateWithdrawLink(wallet, data)
      } else {
        this.createWithdrawLink(wallet, data)
      }
    },
    updateWithdrawLink: function (wallet, data) {
      var self = this
      const body = _.pick(
        data,
        'title',
        'min_withdrawable',
        'max_withdrawable',
        'uses',
        'wait_time',
        'is_unique',
        'webhook_url',
        'webhook_headers',
        'webhook_body',
        'custom_url'
      )

      if (data.has_webhook) {
        body = {
          ...body,
          webhook_url: data.webhook_url,
          webhook_headers: data.webhook_headers,
          webhook_body: data.webhook_body
        }
      }

      LNbits.api
        .request(
          'PUT',
          '/withdraw/api/v1/links/' + data.id,
          wallet.adminkey,
          body
        )
        .then(function (response) {
          self.withdrawLinks = _.reject(self.withdrawLinks, function (obj) {
            return obj.id === data.id
          })
          self.withdrawLinks.push(mapWithdrawLink(response.data))
          self.formDialog.show = false
        })
        .catch(function (error) {
          LNbits.utils.notifyApiError(error)
        })
    },
    createWithdrawLink: function (wallet, data) {
      var self = this

      LNbits.api
        .request('POST', '/withdraw/api/v1/links', wallet.adminkey, data)
        .then(function (response) {
          self.withdrawLinks.push(mapWithdrawLink(response.data))
          self.formDialog.show = false
          self.simpleformDialog.show = false
        })
        .catch(function (error) {
          LNbits.utils.notifyApiError(error)
        })
    },
    deleteWithdrawLink: function (linkId) {
      var self = this
      var link = _.findWhere(this.withdrawLinks, {id: linkId})

      LNbits.utils
        .confirmDialog('Are you sure you want to delete this withdraw link?')
        .onOk(function () {
          LNbits.api
            .request(
              'DELETE',
              '/withdraw/api/v1/links/' + linkId,
              _.findWhere(self.g.user.wallets, {id: link.wallet}).adminkey
            )
            .then(function (response) {
              self.withdrawLinks = _.reject(self.withdrawLinks, function (obj) {
                return obj.id === linkId
              })
            })
            .catch(function (error) {
              LNbits.utils.notifyApiError(error)
            })
        })
    },
    writeNfcTag: async function (lnurl) {
      try {
        if (typeof NDEFReader == 'undefined') {
          throw {
            toString: function () {
              return 'NFC not supported on this device or browser.'
            }
          }
        }

        const ndef = new NDEFReader()

        this.nfcTagWriting = true
        this.$q.notify({
          message: 'Tap your NFC tag to write the LNURL-withdraw link to it.'
        })

        await ndef.write({
          records: [{recordType: 'url', data: 'lightning:' + lnurl, lang: 'en'}]
        })

        this.nfcTagWriting = false
        this.$q.notify({
          type: 'positive',
          message: 'NFC tag written successfully.'
        })
      } catch (error) {
        this.nfcTagWriting = false
        this.$q.notify({
          type: 'negative',
          message: error
            ? error.toString()
            : 'An unexpected error has occurred.'
        })
      }
    },
    exportCSV() {
      LNbits.utils.exportCSV(
        this.withdrawLinksTable.columns,
        this.withdrawLinks,
        'withdraw-links'
      )
    }
  },
  created: function () {
    if (this.g.user.wallets.length) {
      var getWithdrawLinks = this.getWithdrawLinks
      getWithdrawLinks()
      this.checker = setInterval(function () {
        getWithdrawLinks()
      }, 300000)
    }
  }
})
