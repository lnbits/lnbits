var createEmptyScheduleEntry = function() {
  return {
    wallet: null,
    amount_sat: 1,
    base_datetime: "",
    title: "",
    lnurl: ""
  };
};

var processScheduleEntry = function(entry) {
  var processed = Object.assign({}, entry)

  if (entry["wallet"]) {
    processed["wallet_id"] = entry["wallet"]["value"];
    delete processed["wallet"];
  }

  processed["amount_msat"] = entry["amount_sat"] * 1000;
  delete processed["amount_sat"];

  return processed;
}

new Vue({
  el: '#vue',
  mixins: [windowMixin],
  data: function () {
    return {
      scheduleEntries: [],
      newScheduleEntry: createEmptyScheduleEntry(),
      scheduleFrequencyOptions: [
        "hour", "day", "week", "month"
      ]
    }
  },
  methods: {
    // Should be "computed" or "filter"?
    walletName: function(id) {
      return this.g.user.wallets.find(w => w.id === id).name;
    },
    formatAmount: function(msat) {
      return `${msat / 1000}sats`;
    },
    walletOptions: function() {
      return this.g.user.wallets.map(function(w) {
        return {"value": w.id, "label": w.name};
      });
    },

    submitNewScheduleEntry: function() {
      var self = this;
      var $q = this.$q;

      var entry = processScheduleEntry(this.newScheduleEntry);

      console.log("Creating...", entry);
      axios({
        method: 'POST',
        url: '/autopay/api/v1/schedule',
        data: entry
      }).then(function (response) {

        // Refresh the list
        axios({
          method: 'GET',
          url: '/autopay/api/v1/schedule'
        }).then(function (response) {
          self.scheduleEntries = response.data.schedule;
          self.newScheduleEntry = createEmptyScheduleEntry();

          $q.notify({
            timeout: 5000,
            type: 'success',
            message: `Payment scheduled`,
            caption: null
          });
        });
      }).catch(function(error) {
        $q.notify({
          timeout: 5000,
          type: 'error',
          message: `Failed to schedule payment`,
          caption: error.response.data["message"]
        });
      })
    },
    deleteScheduleEntry: function(entry) {
      var self = this;
      var $q = this.$q;

      axios({
        method: 'DELETE',
        url: '/autopay/api/v1/schedule/' + entry.id
      }).then(function (response) {
        // Refresh the list
        axios({
          method: 'GET',
          url: '/autopay/api/v1/schedule'
        }).then(function (response) {
          self.scheduleEntries = response.data.schedule;
          // self.newScheduleEntry = createEmptyScheduleEntry();

          $q.notify({
            timeout: 5000,
            type: 'success',
            message: `Schedule entry deleted`,
            caption: null
          });
        });
      }).catch(function(error) {
        $q.notify({
          timeout: 5000,
          type: 'error',
          message: `Failed to delete schedule`,
          caption: error.response.data["message"]
        });
      });
    }
  },
  created: function () {
    var self = this

    axios({
      method: 'GET',
      url: '/autopay/api/v1/schedule'
    }).then(function (response) {
      self.scheduleEntries = response.data.schedule;
    });
  }
});
