const tables = {
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
