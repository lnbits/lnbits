/* global Vue, VueQrcode, _, Quasar, LOCALE, windowMixin, LNbits */

Vue.component(VueQrcode.name, VueQrcode)

var locationPath = [
  window.location.protocol,
  '//',
  window.location.host,
  window.location.pathname
].join('')

var maplnurlflipLink = function (obj) {
  obj._data = _.clone(obj)
  obj.date = Quasar.utils.date.formatDate(
    new Date(obj.time * 1000),
    'YYYY-MM-DD HH:mm'
  )
  obj.min_fsat = new Intl.NumberFormat(LOCALE).format(obj.min_lnurlflipable)
  obj.max_fsat = new Intl.NumberFormat(LOCALE).format(obj.max_lnurlflipable)
  obj.uses_left = obj.uses - obj.used
  obj.print_url = [locationPath, 'print/', obj.id].join('')
  obj.lnurlflip_url = [locationPath, obj.id].join('')
  return obj
}

new Vue({
  el: '#vue',
  mixins: [windowMixin],
  data: function () {
    return {
      checker: null,
      lnurlflipLinks: [],
      lnurlflipLinksTable: {
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
      formDialog: {
        show: false,
        secondMultiplier: 'seconds',
        secondMultiplierOptions: ['seconds', 'minutes', 'hours'],
        data: {
          is_unique: false
        }
      },
      simpleformDialog: {
        show: false,
        data: {
          is_unique: true,
          title: 'Vouchers',
          min_lnurlflipable: 0,
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
    sortedlnurlflipLinks: function () {
      return this.lnurlflipLinks.sort(function (a, b) {
        return b.uses_left - a.uses_left
      })
    }
  },
  methods: {
    getlnurlflipLinks: function () {
      var self = this

      LNbits.api
        .request(
          'GET',
          '/lnurlflip/api/v1/links?all_wallets',
          this.g.user.wallets[0].inkey
        )
        .then(function (response) {
          self.lnurlflipLinks = response.data.map(function (obj) {
            return maplnurlflipLink(obj)
          })
        })
        .catch(function (error) {
          clearInterval(self.checker)
          LNbits.utils.notifyApiError(error)
        })
    },
    closeFormDialog: function () {
      this.formDialog.data = {
        is_unique: false
      }
    },
    simplecloseFormDialog: function () {
      this.simpleformDialog.data = {
        is_unique: false
      }
    },
    openQrCodeDialog: function (linkId) {
      var link = _.findWhere(this.lnurlflipLinks, {id: linkId})

      this.qrCodeDialog.data = _.clone(link)
      console.log(this.qrCodeDialog.data)
      this.qrCodeDialog.data.url =
        window.location.protocol + '//' + window.location.host
      this.qrCodeDialog.show = true
    },
    openUpdateDialog: function (linkId) {
      var link = _.findWhere(this.lnurlflipLinks, {id: linkId})
      this.formDialog.data = _.clone(link._data)
      this.formDialog.show = true
    },
    sendFormData: function () {
      var wallet = _.findWhere(this.g.user.wallets, {
        id: this.formDialog.data.wallet
      })
      var data = _.omit(this.formDialog.data, 'wallet')

      data.wait_time =
        data.wait_time *
        {
          seconds: 1,
          minutes: 60,
          hours: 3600
        }[this.formDialog.secondMultiplier]

      if (data.id) {
        this.updatelnurlflipLink(wallet, data)
      } else {
        this.createlnurlflipLink(wallet, data)
      }
    },
    simplesendFormData: function () {
      var wallet = _.findWhere(this.g.user.wallets, {
        id: this.simpleformDialog.data.wallet
      })
      var data = _.omit(this.simpleformDialog.data, 'wallet')

      data.wait_time = 1
      data.min_lnurlflipable = data.max_lnurlflipable
      data.title = 'vouchers'
      data.is_unique = true

      if (data.id) {
        this.updatelnurlflipLink(wallet, data)
      } else {
        this.createlnurlflipLink(wallet, data)
      }
    },
    updatelnurlflipLink: function (wallet, data) {
      var self = this

      LNbits.api
        .request(
          'PUT',
          '/lnurlflip/api/v1/links/' + data.id,
          wallet.adminkey,
          _.pick(
            data,
            'title',
            'min_lnurlflipable',
            'max_lnurlflipable',
            'uses',
            'wait_time',
            'is_unique'
          )
        )
        .then(function (response) {
          self.lnurlflipLinks = _.reject(self.lnurlflipLinks, function (obj) {
            return obj.id === data.id
          })
          self.lnurlflipLinks.push(maplnurlflipLink(response.data))
          self.formDialog.show = false
        })
        .catch(function (error) {
          LNbits.utils.notifyApiError(error)
        })
    },
    createlnurlflipLink: function (wallet, data) {
      var self = this

      LNbits.api
        .request('POST', '/lnurlflip/api/v1/links', wallet.adminkey, data)
        .then(function (response) {
          self.lnurlflipLinks.push(maplnurlflipLink(response.data))
          self.formDialog.show = false
          self.simpleformDialog.show = false
        })
        .catch(function (error) {
          LNbits.utils.notifyApiError(error)
        })
    },
    deletelnurlflipLink: function (linkId) {
      var self = this
      var link = _.findWhere(this.lnurlflipLinks, {id: linkId})

      LNbits.utils
        .confirmDialog('Are you sure you want to delete this lnurlflip link?')
        .onOk(function () {
          LNbits.api
            .request(
              'DELETE',
              '/lnurlflip/api/v1/links/' + linkId,
              _.findWhere(self.g.user.wallets, {id: link.wallet}).adminkey
            )
            .then(function (response) {
              self.lnurlflipLinks = _.reject(self.lnurlflipLinks, function (
                obj
              ) {
                return obj.id === linkId
              })
            })
            .catch(function (error) {
              LNbits.utils.notifyApiError(error)
            })
        })
    },
    exportCSV: function () {
      LNbits.utils.exportCSV(this.paywallsTable.columns, this.paywalls)
    }
  },
  created: function () {
    if (this.g.user.wallets.length) {
      var getlnurlflipLinks = this.getlnurlflipLinks
      getlnurlflipLinks()
      this.checker = setInterval(function () {
        getlnurlflipLinks()
      }, 20000)
    }
  }
})
