async function hashToCurve(secretMessage) {
  let point
  while (!point) {
    const hash = await nobleSecp256k1.utils.sha256(secretMessage)
    try {
      point = nobleSecp256k1.Point.fromHex(hash)
    } catch (error) {
      // console.error(error)
      // const x = bytesToNumber(hash) + ''
      // const msg = await nobleSecp256k1.utils.sha256(x)
      secretMessage = await nobleSecp256k1.utils.sha256(hash)
      // secretMessage = nobleSecp256k1.utils.bytesToHex(msg)
    }
  }
  return point
}

async function step1Bob(secretMessage) {
  const Y = await hashToCurve(secretMessage)
  const randomBlindingFactor = bytesToNumber(
    nobleSecp256k1.utils.randomPrivateKey()
  )
  const P = nobleSecp256k1.Point.fromPrivateKey(randomBlindingFactor)
  const B_ = Y.add(P)
  return {B_, randomBlindingFactor}
}

function step3Bob(C_, r, A) {
  const C = C_.subtract(A.multiply(r))
  return C
}
