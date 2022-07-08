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
  obj.theTime = obj.time * 60 - (Date.now() / 1000 - obj.timestamp)
  obj.time = obj.time + ' min'

  if (obj.time_elapsed) {
    obj.date = ''
  } else {
    obj.date = Quasar.utils.date.formatDate(
      new Date((obj.theTime - 3600) * 1000),
      'HH:mm:ss'
    )
  }
  obj.expanded = false
  obj.displayUrl = ['/satspay/', obj.id].join('')
  obj.expanded = oldObj.expanded
  obj.pendingBalance = oldObj.pendingBalance || 0
  return obj
}
