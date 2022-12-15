const sleep = ms => new Promise(r => setTimeout(r, ms))
const retryWithDelay = async function (fn, retryCount = 0) {
  try {
    await sleep(25)
    // Do not return the call directly, use result.
    // Otherwise the error will not be cought in this try-catch block.
    const result = await fn()
    return result
  } catch (err) {
    if (retryCount > 100) throw err
    await sleep((retryCount + 1) * 1000)
    return retryWithDelay(fn, retryCount + 1)
  }
}

const mapCharge = (obj, oldObj = {}) => {
  const charge = {...oldObj, ...obj}

  charge.progress = obj.time_left < 0 ? 1 : 1 - obj.time_left / obj.time
  charge.time = minutesToTime(obj.time)
  charge.timeLeft = minutesToTime(obj.time_left)

  charge.displayUrl = ['/satspay/', obj.id].join('')
  charge.expanded = oldObj.expanded || false
  charge.pendingBalance = oldObj.pendingBalance || 0
  charge.extra = charge.extra ? JSON.parse(charge.extra) : charge.extra
  return charge
}

const mapCSS = (obj, oldObj = {}) => {
  const theme = _.clone(obj)
  return theme
}

const minutesToTime = min =>
  min > 0 ? new Date(min * 1000).toISOString().substring(14, 19) : ''
