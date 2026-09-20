import {blockTimeToDate} from './utils.js'
export const mapAddressesData = a => ({
  id: a.id,
  address: a.address,
  amount: a.amount,
  wallet: a.wallet,
  note: a.note,

  isChange: a.branch_index === 1,
  addressIndex: a.address_index,
  hasActivity: a.has_activity
})

export const mapInputToSentHistory = (tx, addressData, vin) => ({
  sent: true,
  txId: tx.txid,
  address: addressData.address,
  isChange: addressData.isChange,
  amount: vin.prevout.value,
  date: blockTimeToDate(tx.status.block_time),
  timestamp: tx.status.block_time,
  height: tx.status.block_height,
  confirmed: tx.status.confirmed,
  fee: tx.fee,
  expanded: false
})

export const mapOutputToReceiveHistory = (tx, addressData, vout) => ({
  received: true,
  txId: tx.txid,
  address: addressData.address,
  isChange: addressData.isChange,
  amount: vout.value,
  date: blockTimeToDate(tx.status.block_time),
  timestamp: tx.status.block_time,
  height: tx.status.block_height,
  confirmed: tx.status.confirmed,
  fee: tx.fee,
  expanded: false
})

export const mapUtxoToPsbtInput = utxo => ({
  tx_id: utxo.txId,
  vout: utxo.vout,
  amount: utxo.amount,
  address: utxo.address,
  branch_index: utxo.isChange ? 1 : 0,
  address_index: utxo.addressIndex,
  wallet: utxo.wallet,
  accountType: utxo.accountType,
  accountPath: utxo.accountPath,
  txHex: ''
})

export const mapAddressDataToUtxo = (wallet, addressData, utxo) => ({
  id: addressData.id,
  address: addressData.address,
  isChange: addressData.isChange,
  addressIndex: addressData.addressIndex,
  wallet: addressData.wallet,
  accountType: addressData.accountType,
  accountPath: wallet.meta.accountPath,
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

export const mapWalletAccount = function (o) {
  return Object.assign({}, o, {
    date: o.time
      ? Quasar.date.formatDate(new Date(o.time * 1000), 'YYYY-MM-DD HH:mm')
      : '',
    meta: o.meta ? JSON.parse(o.meta) : null,
    label: o.title,
    expanded: false
  })
}

export const mapDerivationPathToTrezor = function (path = '') {
  return path
    .split('/')
    .filter(p => p !== 'm')
    .map(p => (p.endsWith("'") ? +p.slice(0, -1) | 0x80000000 : +p))
}

export const mapOutputAccountTypeToTrezor = function (accountType) {
  switch (accountType) {
    case 'p2pkh':
      return 'PAYTOADDRESS'
    case 'p2wpkh':
      return 'PAYTOWITNESS'
    case 'p2sh':
      return 'PAYTOP2SHWITNESS'
    case 'p2tr':
      return 'PAYTOTAPROOT'
    default:
      return undefined
  }
}

export const mapInputAccountTypeToTrezor = function (accountType) {
  switch (accountType) {
    case 'p2pkh':
      return 'SPENDADDRESS'
    case 'p2wpkh':
      return 'SPENDWITNESS'
    case 'p2sh':
      return 'SPENDP2SHWITNESS'
    case 'p2tr':
      return 'SPENDTAPROOT'
    default:
      return undefined
  }
}
