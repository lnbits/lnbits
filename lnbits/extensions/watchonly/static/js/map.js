const mapAddressesData = a => ({
  id: a.id,
  address: a.address,
  amount: a.amount,
  wallet: a.wallet,
  note: a.note,

  branchIndex: a.branch_index,
  addressIndex: a.address_index,
  hasActivity: a.has_activity
})

const mapInputToSentHistory = (tx, addressData, vin) => ({
  sent: true,
  txId: tx.txid,
  address: addressData.address,
  isChange: addressData.branchIndex === 1,
  amount: vin.prevout.value,
  date: blockTimeToDate(tx.status.block_time),
  height: tx.status.block_height,
  confirmed: tx.status.confirmed,
  fee: tx.fee,
  expanded: false
})

const mapOutputToReceiveHistory = (tx, addressData, vout) => ({
  received: true,
  txId: tx.txid,
  address: addressData.address,
  isChange: addressData.branchIndex === 1,
  amount: vout.value,
  date: blockTimeToDate(tx.status.block_time),
  height: tx.status.block_height,
  confirmed: tx.status.confirmed,
  fee: tx.fee,
  expanded: false
})

const mapUtxoToPsbtInput = utxo => ({
  tx_id: utxo.txId,
  vout: utxo.vout,
  amount: utxo.amount,
  address: utxo.address,
  branch_index: utxo.branchIndex,
  address_index: utxo.addressIndex,
  masterpub_fingerprint: utxo.masterpubFingerprint,
  accountType: utxo.accountType,
  txHex: ''
})

const mapAddressDataToUtxo = (wallet, addressData, utxo) => ({
  id: addressData.id,
  address: addressData.address,
  isChange: addressData.branchIndex === 1,
  addressIndex: addressData.addressIndex,
  branchIndex: addressData.branchIndex,
  wallet: addressData.wallet,
  accountType: addressData.accountType,
  masterpubFingerprint: wallet.fingerprint,
  txId: utxo.txid,
  vout: utxo.vout,
  confirmed: utxo.status.confirmed,
  amount: utxo.value,
  date: blockTimeToDate(utxo.status?.block_time),
  sort: utxo.status?.block_time,
  expanded: false,
  selected: false
})

const mapWalletAccount = function (obj) {
  obj._data = _.clone(obj)
  obj.date = obj.time
    ? Quasar.utils.date.formatDate(
        new Date(obj.time * 1000),
        'YYYY-MM-DD HH:mm'
      )
    : ''
  obj.label = obj.title // for drop-downs
  obj.expanded = false
  return obj
}
