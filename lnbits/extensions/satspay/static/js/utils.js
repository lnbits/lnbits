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
  obj._data = _.clone(obj)

  obj.progress = obj.time_left < 0 ? 1 : 1 - obj.time_left / obj.time
  obj.time = minutesToShortTime(obj.time)
  obj.timeLeft = minutesToTime(obj.time_left)

  obj.expanded = false
  obj.displayUrl = ['/satspay/', obj.id].join('')
  obj.expanded = oldObj.expanded
  obj.pendingBalance = oldObj.pendingBalance || 0
  return obj
}

const minutesToTime = min =>
  min > 0 ? new Date(min * 1000).toISOString().substring(11, 19) : ''

const minutesToShortTime = min =>
  min > 0 ? new Date(min * 1000).toISOString().substring(14, 22) : ''
