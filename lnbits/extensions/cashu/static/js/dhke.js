async function hashToCurve(secretMessage) {
  console.log(
    '### secretMessage',
    nobleSecp256k1.utils.bytesToHex(secretMessage)
  )
  let point
  while (!point) {
    const hash = await nobleSecp256k1.utils.sha256(secretMessage)
    const hashHex = nobleSecp256k1.utils.bytesToHex(hash)
    const pointX = '02' + hashHex
    console.log('### pointX', pointX)
    try {
      point = nobleSecp256k1.Point.fromHex(pointX)
      console.log('### point', point.toHex())
    } catch (error) {
      secretMessage = await nobleSecp256k1.utils.sha256(secretMessage)
    }
  }
  return point
}

async function step1Alice(secretMessage) {
  // todo: document & validate `secretMessage` format
  secretMessage = uint8ToBase64.encode(secretMessage)
  secretMessage = new TextEncoder().encode(secretMessage)
  const Y = await hashToCurve(secretMessage)
  const rpk = nobleSecp256k1.utils.randomPrivateKey()
  const r = bytesToNumber(rpk)
  const P = nobleSecp256k1.Point.fromPrivateKey(r)
  const B_ = Y.add(P)
  return {B_: B_.toHex(true), r: nobleSecp256k1.utils.bytesToHex(rpk)}
}

function step3Alice(C_, r, A) {
  // const rInt = BigInt(r)
  const rInt = bytesToNumber(r)
  const C = C_.subtract(A.multiply(rInt))
  return C
}
