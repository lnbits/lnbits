const tables = {
  paymentTable: {
    columns: [
      {
        name: 'data',
        align: 'left'
      }
    ],
    pagination: {
      rowsPerPage: 10
    },
    filter: ''
  },
  summaryTable: {
    columns: [
      {
        name: 'totalInputs',
        align: 'center',
        label: 'Selected Amount'
      },
      {
        name: 'totalOutputs',
        align: 'center',
        label: 'Payed Amount'
      },
      {
        name: 'fees',
        align: 'center',
        label: 'Fees'
      },
      {
        name: 'change',
        align: 'center',
        label: 'Change'
      }
    ]
  }
}

const tableData = {
  utxos: {
    data: [],
    total: 0
  },
  payment: {
    data: [{address: '', amount: undefined}],
    changeWallet: null,
    changeAddress: {},
    changeAmount: 0,

    feeRate: 1,
    recommededFees: {
      fastestFee: 1,
      halfHourFee: 1,
      hourFee: 1,
      economyFee: 1,
      minimumFee: 1
    },
    fee: 0,
    txSize: 0,
    tx: null,
    psbtBase64: '',
    psbtBase64Signed: '',
    signedTx: null,
    signedTxHex: null,
    sentTxId: null,

    signModes: [
      {
        label: 'Serial Port Device',
        value: 'serial-port'
      },
      {
        label: 'Animated QR',
        value: 'animated-qr',
        disable: true
      }
    ],
    signMode: '',
    show: false,
    showAdvanced: false
  },
  summary: {
    data: [{totalInputs: 0, totalOutputs: 0, fees: 0, change: 0}]
  }
}
