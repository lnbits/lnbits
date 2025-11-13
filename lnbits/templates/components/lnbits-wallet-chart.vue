<template id="lnbits-wallet-chart">
  <div
    :style="!chartDataPointCount ? 'display:none;' : ''"
    class="col-12 col-md-5 q-gutter-y-md"
  >
    <q-card
      :style="g.walletChartConfig.includes('balance') ? '' : 'display: none;'"
    >
      <q-card-section class="q-pa-none">
        <div style="height: 200px" class="q-pa-sm">
          <canvas ref="walletBalanceChart"></canvas>
        </div>
      </q-card-section>
    </q-card>
    <q-card
      :style="
        g.walletChartConfig.includes('balance-in-out') ? '' : 'display: none;'
      "
    >
      <q-card-section class="q-pa-none">
        <div style="height: 200px" class="q-pa-sm">
          <canvas ref="walletBalanceInOut"></canvas>
        </div>
      </q-card-section>
    </q-card>
    <q-card
      :style="
        g.walletChartConfig.includes('payment-in-out') ? '' : 'display: none;'
      "
    >
      <q-card-section class="q-pa-none">
        <div style="height: 200px" class="q-pa-sm">
          <canvas ref="walletPaymentInOut"></canvas>
        </div>
      </q-card-section>
    </q-card>
  </div>
</template>
