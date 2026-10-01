// Signing inputs and fee estimates use the wallet's server-configured provider.
export function mempoolJS() {
  const key = LNbits.g.wallet.inkey
  const request = async path => {
    const {data} = await LNbits.api.request(
      'GET',
      '/api/v1/onchain/' + path,
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
