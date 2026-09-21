// Signing inputs and fee estimates use the wallet's server-configured provider.
export function mempoolJS() {
  const key = LNbits.g.wallet.inkey
  const request = async path => {
    const {data} = await LNbits.api.request(
      'GET',
      '/onchain/api/v1/' + path,
      key
    )
    return data
  }
  return {
    bitcoin: {
      transactions: {
        getTxHex: ({txid}) => request('tx/' + encodeURIComponent(txid) + '/hex')
      },
      fees: {getFeesRecommended: () => request('fees')}
    }
  }
}
