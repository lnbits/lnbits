var LOCALE = 'en'

var LNbits = {
  api: {
    request: function (method, url, macaroon, data) {
      return axios({
        method: method,
        url: url,
        headers: {
          'Grpc-Metadata-macaroon': macaroon
        },
        data: data
      });
    },
    createInvoice: function (wallet, amount, memo) {
      return this.request('post', '/api/v1/payments', wallet.inkey, {
        out: false,
        amount: amount,
        memo: memo
      });
    },
    payInvoice: function (wallet, bolt11) {
      return this.request('post', '/api/v1/payments', wallet.inkey, {
        out: true,
        bolt11: bolt11
      });
    },
    getPayments: function (wallet, checkPending) {
      var query_param = (checkPending) ? '?check_pending' : '';
      return this.request('get', ['/api/v1/payments', query_param].join(''), wallet.inkey);
    },
    getPayment: function (wallet, payhash) {
      return this.request('get', '/api/v1/payments/' + payhash, wallet.inkey);
    }
  },
  href: {
    createWallet: function (walletName, userId) {
      window.location.href = '/wallet?' + (userId ? 'usr=' + userId + '&' : '') + 'nme=' + walletName;
    },
    deleteWallet: function (walletId, userId) {
      window.location.href = '/deletewallet?usr=' + userId + '&wal=' + walletId;
    }
  },
  map: {
    extension: function (data) {
      var obj = _.object(['code', 'isValid', 'name', 'shortDescription', 'icon'], data);
      obj.url = ['/', obj.code, '/'].join('');
      return obj;
    },
    user: function (data) {
      var obj = _.object(['id', 'email', 'extensions', 'wallets'], data);
      var mapWallet = this.wallet;
      obj.wallets = obj.wallets.map(function (obj) {
        return mapWallet(obj);
      }).sort(function (a, b) {
        return a.name > b.name;
      });
      return obj;
    },
    wallet: function (data) {
      var obj = _.object(['id', 'name', 'user', 'adminkey', 'inkey', 'balance'], data);
      obj.msat = obj.balance;
      obj.sat = Math.round(obj.balance / 1000);
      obj.fsat = new Intl.NumberFormat(LOCALE).format(obj.sat);
      obj.url = ['/wallet?usr=', obj.user, '&wal=', obj.id].join('');
      return obj;
    },
    payment: function (data) {
      var obj = _.object(['payhash', 'pending', 'amount', 'fee', 'memo', 'time'], data);
      obj.date = Quasar.utils.date.formatDate(new Date(obj.time * 1000), 'YYYY-MM-DD HH:mm');
      obj.msat = obj.amount;
      obj.sat = obj.msat / 1000;
      obj.fsat = new Intl.NumberFormat(LOCALE).format(obj.sat);
      obj.isIn = obj.amount > 0;
      obj.isOut = obj.amount < 0;
      obj.isPaid = obj.pending == 0;
      return obj;
    }
  },
  utils: {
    formatSat: function (value) {
      return new Intl.NumberFormat(LOCALE).format(value);
    },
    notifyApiError: function (error) {
      var types = {
        400: 'warning',
        401: 'warning',
        500: 'negative'
      };
      Quasar.plugins.Notify.create({
        timeout: 5000,
        type: types[error.response.status] || 'warning',
        message: error.response.data.message || null,
        caption: [error.response.status, ' ', error.response.statusText].join('').toUpperCase() || null,
        icon: null
      });
    }
  }
};

var windowMixin = {
  data: function () {
    return {
      w: {
        visibleDrawer: false,
        extensions: [],
        user: null,
        wallet: null,
        payments: [],
      }
    };
  },
  methods: {
    toggleDarkMode: function () {
      this.$q.dark.toggle();
      this.$q.localStorage.set('lnbits.darkMode', this.$q.dark.isActive);
    },
    copyText: function (text, message) {
      var notify = this.$q.notify;
      Quasar.utils.copyToClipboard(text).then(function () {
        notify({message: 'Copied to clipboard!'});
      });
    }
  },
  created: function () {
    this.$q.dark.set(this.$q.localStorage.getItem('lnbits.darkMode'));
    if (window.user) {
      this.w.user = Object.freeze(LNbits.map.user(window.user));
    }
    if (window.wallet) {
      this.w.wallet = Object.freeze(LNbits.map.wallet(window.wallet));
    }
    if (window.extensions) {
      var user = this.w.user;
      this.w.extensions = Object.freeze(window.extensions.map(function (data) {
        return LNbits.map.extension(data);
      }).map(function (obj) {
        if (user) {
          obj.isEnabled = user.extensions.indexOf(obj.code) != -1;
        } else {
          obj.isEnabled = false;
        }
        return obj;
      }).sort(function (a, b) {
        return a.name > b.name;
      }));
    }
  }
};
