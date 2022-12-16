function unescapeBase64Url(str) {
  return (str + '==='.slice((str.length + 3) % 4))
    .replace(/-/g, '+')
    .replace(/_/g, '/')
}

function escapeBase64Url(str) {
  return str.replace(/\+/g, '-').replace(/\//g, '_').replace(/=/g, '')
}

const uint8ToBase64 = (function (exports) {
  'use strict'

  var fromCharCode = String.fromCharCode
  var encode = function encode(uint8array) {
    var output = []

    for (var i = 0, length = uint8array.length; i < length; i++) {
      output.push(fromCharCode(uint8array[i]))
    }

    return btoa(output.join(''))
  }

  var asCharCode = function asCharCode(c) {
    return c.charCodeAt(0)
  }

  var decode = function decode(chars) {
    return Uint8Array.from(atob(chars), asCharCode)
  }

  exports.decode = decode
  exports.encode = encode

  return exports
})({})
