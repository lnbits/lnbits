Vue.component(VueQrcode.name, VueQrcode);

new Vue({
  el: '#vue',
  mixins: [windowMixin],
  data: function () {
    return {
      txUpdate: null,
      receive: {
        show: false,
        status: 'pending',
        paymentReq: null,
        data: {
          amount: null,
          memo: ''
        }
      },
      send: {
        show: false,
        invoice: null,
        data: {
          bolt11: ''
        }
      },
      transactionsTable: {
        columns: [
          {name: 'memo', align: 'left', label: 'Memo', field: 'memo'},
          {name: 'date', align: 'left', label: 'Date', field: 'date', sortable: true},
          {name: 'sat', align: 'right', label: 'Amount (sat)', field: 'sat', sortable: true}
        ],
        pagination: {
          rowsPerPage: 10
        }
      }
    };
  },
  computed: {
    canPay: function () {
      if (!this.send.invoice) return false;
      return this.send.invoice.sat < this.w.wallet.balance;
    },
    transactions: function () {
      var data = (this.txUpdate) ? this.txUpdate : this.w.transactions;
      return data.sort(function (a, b) {
        return b.time - a.time;
      });
    }
  },
  methods: {
    openReceiveDialog: function () {
      this.receive = {
        show: true,
        status: 'pending',
        paymentReq: null,
        data: {
          amount: null,
          memo: ''
        }
      };
    },
    openSendDialog: function () {
      this.send = {
        show: true,
        invoice: null,
        data: {
          bolt11: ''
        }
      };
    },
    createInvoice: function () {
      var self = this;
      this.receive.status = 'loading';
      LNbits.api.createInvoice(this.w.wallet, this.receive.data.amount, this.receive.data.memo)
        .then(function (response) {
          self.receive.status = 'success';
          self.receive.paymentReq = response.data.payment_request;

          var check_invoice = setInterval(function () {
            LNbits.api.getInvoice(self.w.wallet, response.data.payment_hash).then(function (response) {
              if (response.data.paid) {
                self.refreshTransactions();
                self.receive.show = false;
                clearInterval(check_invoice);
              }
            });
          }, 3000);

        }).catch(function (error) {
          LNbits.utils.notifyApiError(error);
          self.receive.status = 'pending';
        });
    },
    decodeInvoice: function () {
      try {
        var invoice = decode(this.send.data.bolt11);
      } catch (err) {
        this.$q.notify({type: 'warning', message: err});
        return;
      }

      var cleanInvoice = {
        msat: invoice.human_readable_part.amount,
        sat: invoice.human_readable_part.amount / 1000,
        fsat: LNbits.utils.formatSat(invoice.human_readable_part.amount / 1000)
      };

      _.each(invoice.data.tags, function (tag) {
        if (_.isObject(tag) && _.has(tag, 'description')) {
          if (tag.description == 'payment_hash') { cleanInvoice.hash = tag.value; }
          else if (tag.description == 'description') { cleanInvoice.description = tag.value; }
          else if (tag.description == 'expiry') {
            var expireDate = new Date((invoice.data.time_stamp + tag.value) * 1000);
            cleanInvoice.expireDate = Quasar.utils.date.formatDate(expireDate, 'YYYY-MM-DDTHH:mm:ss.SSSZ');
            cleanInvoice.expired = false;  // TODO
          }
        }
      });

      this.send.invoice = Object.freeze(cleanInvoice);
    },
    payInvoice: function () {
      alert('pay!');
    },
    deleteWallet: function (walletId, user) {
      LNbits.href.deleteWallet(walletId, user);
    },
    refreshTransactions: function (notify) {
      var self = this;

      LNbits.api.getTransactions(this.w.wallet).then(function (response) {
        self.txUpdate = response.data.map(function (obj) {
          return LNbits.map.transaction(obj);
        });
      });
    }
  }
});
