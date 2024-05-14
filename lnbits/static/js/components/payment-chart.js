function generateChart(canvas, rawData) {
  const data = rawData.reduce(
    (previous, current) => {
      previous.labels.push(current.date)
      previous.income.push(current.income)
      previous.spending.push(current.spending)
      previous.cumulative.push(current.balance)
      return previous
    },
    {
      labels: [],
      income: [],
      spending: [],
      cumulative: []
    }
  )

  return new Chart(canvas.getContext('2d'), {
    type: 'bar',
    data: {
      labels: data.labels,
      datasets: [
        {
          data: data.cumulative,
          type: 'line',
          label: 'balance',
          backgroundColor: '#673ab7', // deep-purple
          borderColor: '#673ab7',
          borderWidth: 4,
          pointRadius: 3,
          fill: false
        },
        {
          data: data.income,
          type: 'bar',
          label: 'in',
          barPercentage: 0.75,
          backgroundColor: window.Color('rgb(76,175,80)').alpha(0.5).rgbString() // green
        },
        {
          data: data.spending,
          type: 'bar',
          label: 'out',
          barPercentage: 0.75,
          backgroundColor: window.Color('rgb(233,30,99)').alpha(0.5).rgbString() // pink
        }
      ]
    },
    options: {
      title: {
        text: 'Chart.js Combo Time Scale'
      },
      tooltips: {
        mode: 'index',
        intersect: false
      },
      scales: {
        xAxes: [
          {
            type: 'time',
            display: true,
            //offset: true,
            time: {
              minUnit: 'hour',
              stepSize: 3
            }
          }
        ]
      },
      // performance tweaks
      animation: {
        duration: 0
      },
      elements: {
        line: {
          tension: 0
        }
      }
    }
  })
}

Vue.component('payment-chart', {
  name: 'payment-chart',
  props: ['wallet'],
  mixins: [windowMixin],
  data: function () {
    return {
      paymentsChart: {
        show: false,
        group: {
          value: 'hour',
          label: 'Hour'
        },
        groupOptions: [
          {value: 'hour', label: 'Hour'},
          {value: 'day', label: 'Day'},
          {value: 'week', label: 'Week'},
          {value: 'month', label: 'Month'},
          {value: 'year', label: 'Year'}
        ],
        instance: null
      }
    }
  },
  methods: {
    showChart: function () {
      this.paymentsChart.show = true
      LNbits.api
        .request(
          'GET',
          '/api/v1/payments/history?group=' + this.paymentsChart.group.value,
          this.wallet.adminkey
        )
        .then(response => {
          this.$nextTick(() => {
            if (this.paymentsChart.instance) {
              this.paymentsChart.instance.destroy()
            }
            this.paymentsChart.instance = generateChart(
              this.$refs.canvas,
              response.data
            )
          })
        })
        .catch(err => {
          LNbits.utils.notifyApiError(err)
          this.paymentsChart.show = false
        })
    }
  },
  template: `
    <span id="payment-chart">
        <q-btn dense flat round icon="show_chart" color="grey" @click="showChart" >
            <q-tooltip>
                <span v-text="$t('chart_tooltip')"></span>
            </q-tooltip>
        </q-btn>

        <q-dialog v-model="paymentsChart.show" position="top">
            <q-card class="q-pa-sm" style="width: 800px; max-width: unset">
                <q-card-section>
                    <div class="row q-gutter-sm justify-between">
                        <div class="text-h6">Payments Chart</div>
                        <q-select label="Group" filled dense v-model="paymentsChart.group"
                        style="min-width: 120px"
                        :options="paymentsChart.groupOptions"
                        >
                        </q-select>
                    </div>
                    <canvas ref="canvas" width="600" height="400"></canvas>
                </q-card-section>
            </q-card>
        </q-dialog>
    </span>
    `
})
