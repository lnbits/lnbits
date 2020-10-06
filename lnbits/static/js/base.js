/* globals moment, Vue, EventHub, axios, Quasar, _ */

var LOCALE = 'en'

var EventHub = new Vue()

var LNbits = {
  api: {
    request: function (method, url, apiKey, data) {
      return axios({
        method: method,
        url: url,
        headers: {
          'X-Api-Key': apiKey
        },
        data: data
      })
    },
    createInvoice: function (wallet, amount, memo) {
      return this.request('post', '/api/v1/payments', wallet.inkey, {
        out: false,
        amount: amount,
        memo: memo
      })
    },
    payInvoice: function (wallet, bolt11) {
      return this.request('post', '/api/v1/payments', wallet.adminkey, {
        out: true,
        bolt11: bolt11
      })
    },
    getWallet: function (wallet) {
      return this.request('get', '/api/v1/wallet', wallet.inkey)
    },
    getPayments: function (wallet, checkPending) {
      var query_param = checkPending ? '?check_pending' : ''
      return this.request(
        'get',
        ['/api/v1/payments', query_param].join(''),
        wallet.inkey
      )
    },
    getPayment: function (wallet, paymentHash) {
      return this.request(
        'get',
        '/api/v1/payments/' + paymentHash,
        wallet.inkey
      )
    }
  },
  href: {
    createWallet: function (walletName, userId) {
      window.location.href =
        '/wallet?' + (userId ? 'usr=' + userId + '&' : '') + 'nme=' + walletName
    },
    deleteWallet: function (walletId, userId) {
      window.location.href = '/deletewallet?usr=' + userId + '&wal=' + walletId
    }
  },
  map: {
    extension: function (data) {
      var obj = _.object(
        ['code', 'isValid', 'name', 'shortDescription', 'icon'],
        data
      )
      obj.url = ['/', obj.code, '/'].join('')
      return obj
    },
    user: function (data) {
      var obj = _.object(['id', 'email', 'extensions', 'wallets'], data)
      var mapWallet = this.wallet
      obj.wallets = obj.wallets
        .map(function (obj) {
          return mapWallet(obj)
        })
        .sort(function (a, b) {
          return a.name.localeCompare(b.name)
        })
      obj.walletOptions = obj.wallets.map(function (obj) {
        return {
          label: [obj.name, ' - ', obj.id].join(''),
          value: obj.id
        }
      })
      return obj
    },
    wallet: function (data) {
      var obj = _.object(
        ['id', 'name', 'user', 'adminkey', 'inkey', 'balance'],
        data
      )
      obj.msat = obj.balance
      obj.sat = Math.round(obj.balance / 1000)
      obj.fsat = new Intl.NumberFormat(LOCALE).format(obj.sat)
      obj.url = ['/wallet?usr=', obj.user, '&wal=', obj.id].join('')
      return obj
    },
    payment: function (data) {
      var obj = _.object(
        [
          'checking_id',
          'pending',
          'amount',
          'fee',
          'memo',
          'time',
          'bolt11',
          'preimage',
          'payment_hash',
          'extra'
        ],
        data
      )
      obj.date = Quasar.utils.date.formatDate(
        new Date(obj.time * 1000),
        'YYYY-MM-DD HH:mm'
      )
      obj.dateFrom = moment(obj.date).fromNow()
      obj.msat = obj.amount
      obj.sat = obj.msat / 1000
      obj.tag = obj.extra.tag
      obj.fsat = new Intl.NumberFormat(LOCALE).format(obj.sat)
      obj.isIn = obj.amount > 0
      obj.isOut = obj.amount < 0
      obj.isPaid = obj.pending === 0
      obj._q = [obj.memo, obj.sat].join(' ').toLowerCase()
      return obj
    }
  },
  utils: {
    confirmDialog: function (msg) {
      return Quasar.plugins.Dialog.create({
        message: msg,
        ok: {
          flat: true,
          color: 'orange'
        },
        cancel: {
          flat: true,
          color: 'grey'
        }
      })
    },
    formatCurrency: function (value, currency) {
      return new Intl.NumberFormat(LOCALE, {
        style: 'currency',
        currency: currency
      }).format(value)
    },
    formatSat: function (value) {
      return new Intl.NumberFormat(LOCALE).format(value)
    },
    notifyApiError: function (error) {
      var types = {
        400: 'warning',
        401: 'warning',
        500: 'negative'
      }
      Quasar.plugins.Notify.create({
        timeout: 5000,
        type: types[error.response.status] || 'warning',
        message: error.response.data.message || null,
        caption:
          [error.response.status, ' ', error.response.statusText]
            .join('')
            .toUpperCase() || null,
        icon: null
      })
    },
    search: function (data, q, field, separator) {
      try {
        var queries = q.toLowerCase().split(separator || ' ')
        return data.filter(function (obj) {
          var matches = 0
          _.each(queries, function (q) {
            if (obj[field].indexOf(q) !== -1) matches++
          })
          return matches === queries.length
        })
      } catch (err) {
        return data
      }
    },
    exportCSV: function (columns, data) {
      var wrapCsvValue = function (val, formatFn) {
        var formatted = formatFn !== void 0 ? formatFn(val) : val

        formatted =
          formatted === void 0 || formatted === null ? '' : String(formatted)

        formatted = formatted.split('"').join('""')

        return `"${formatted}"`
      }

      var content = [
        columns.map(function (col) {
          return wrapCsvValue(col.label)
        })
      ]
        .concat(
          data.map(function (row) {
            return columns
              .map(function (col) {
                return wrapCsvValue(
                  typeof col.field === 'function'
                    ? col.field(row)
                    : row[col.field === void 0 ? col.name : col.field],
                  col.format
                )
              })
              .join(',')
          })
        )
        .join('\r\n')

      var status = Quasar.utils.exportFile(
        'table-export.csv',
        content,
        'text/csv'
      )

      if (status !== true) {
        Quasar.plugins.Notify.create({
          message: 'Browser denied file download...',
          color: 'negative',
          icon: null
        })
      }
    }
  }
}

var windowMixin = {
  data: function () {
    return {
      g: {
        visibleDrawer: false,
        extensions: [],
        user: null,
        wallet: null,
        payments: []
      }
    }
  },
  methods: {
    toggleDarkMode: function () {
      this.$q.dark.toggle()
      this.$q.localStorage.set('lnbits.darkMode', this.$q.dark.isActive)
    },
    copyText: function (text, message, position) {
      var notify = this.$q.notify
      Quasar.utils.copyToClipboard(text).then(function () {
        notify({
          message: message || 'Copied to clipboard!',
          position: position || 'bottom'
        })
      })
    }
  },
  created: function () {
    this.$q.dark.set(this.$q.localStorage.getItem('lnbits.darkMode'))
    if (window.user) {
      this.g.user = Object.freeze(LNbits.map.user(window.user))
    }
    if (window.wallet) {
      this.g.wallet = Object.freeze(LNbits.map.wallet(window.wallet))
    }
    if (window.extensions) {
      var user = this.g.user
      this.g.extensions = Object.freeze(
        window.extensions
          .map(function (data) {
            return LNbits.map.extension(data)
          })
          .map(function (obj) {
            if (user) {
              obj.isEnabled = user.extensions.indexOf(obj.code) !== -1
            } else {
              obj.isEnabled = false
            }
            return obj
          })
          .sort(function (a, b) {
            return a.name > b.name
          })
      )
    }
  }
}
