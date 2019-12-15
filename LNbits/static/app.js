/** @format */

const user = window.user
const user_wallets = window.user_wallets
const wallet = window.wallet
const transactions = window.transactions

var thehash = ''
var theinvoice = ''
var outamount = ''
var outmemo = ''

// API CALLS

function postAjax(url, data, thekey, success) {
  var params =
    typeof data == 'string'
      ? data
      : Object.keys(data)
          .map(function(k) {
            return encodeURIComponent(k) + '=' + encodeURIComponent(data[k])
          })
          .join('&')
  var xhr = window.XMLHttpRequest
    ? new XMLHttpRequest()
    : new ActiveXObject('Microsoft.XMLHTTP')
  xhr.open('POST', url)
  xhr.onreadystatechange = function() {
    if (xhr.readyState > 3 && xhr.status == 200) {
      success(xhr.responseText)
    }
  }
  xhr.setRequestHeader('Grpc-Metadata-macaroon', thekey)
  xhr.setRequestHeader('Content-Type', 'application/json')
  xhr.send(params)
  return xhr
}

function getAjax(url, thekey, success) {
  var xhr = window.XMLHttpRequest
    ? new XMLHttpRequest()
    : new ActiveXObject('Microsoft.XMLHTTP')
  xhr.open('GET', url, true)
  xhr.onreadystatechange = function() {
    if (xhr.readyState > 3 && xhr.status == 200) {
      success(xhr.responseText)
    }
  }
  xhr.setRequestHeader('Grpc-Metadata-macaroon', thekey)
  xhr.setRequestHeader('Content-Type', 'application/json')
  xhr.send()
  return xhr
}

function sendfundsinput() {
  document.getElementById('sendfunds').innerHTML =
    "<br/><br/><div class='row'><div class='col-md-4'>" +
    "<textarea id='pasteinvoice' class='form-control' rows='3' placeholder='Paste an invoice'></textarea></div></div>" +
    "<br/><div class='row'><div class='col-md-4'><button type='submit' onclick='sendfundspaste()' class='btn btn-primary'>" +
    "Submit</button><button style='margin-left:20px;' type='submit' class='btn btn-primary' onclick='scanQRsend()'>" +
    'Use camera to scan an invoice</button></div></div><br/><br/>'
  document.getElementById('receive').innerHTML = ''
}

function sendfundspaste() {
  invoice = document.getElementById('pasteinvoice').value
  theinvoice = decode(invoice)
  outmemo = theinvoice.data.tags[1].value
  outamount = Number(theinvoice.human_readable_part.amount) / 1000
  if (outamount > Number(wallet.balance)) {
    document.getElementById('sendfunds').innerHTML =
      "<div class='row'><div class='col-md-6'>" +
      "<h3><b style='color:red;'>Not enough funds!</b></h3>" +
      "<button style='margin-left:20px;' type='submit' class='btn btn-primary' onclick='cancelsend()'>Continue</button>" +
      '</br/></br/></div></div>'
  } else {
    document.getElementById('sendfunds').innerHTML =
      "<div class='row'><div class='col-md-6'>" +
      '<h3><b>Invoice details</b></br/>Amount: ' +
      outamount +
      '<br/>Memo: ' +
      outmemo +
      '</h3>' +
      "<h4 style='word-wrap: break-word;'>" +
      invoice +
      '</h4>' +
      "<button type='submit' class='btn btn-primary' onclick='sendfunds(" +
      JSON.stringify(invoice) +
      ")'>Send funds</button>" +
      "<button style='margin-left:20px;' type='submit' class='btn btn-primary' onclick='cancelsend()'>Cancel payment</button>" +
      '</br/></br/></div></div>'
  }
}

function receive() {
  document.getElementById('receive').innerHTML =
    "<br/><div class='row'><div id='QRCODE'>" +
    "<div class='col-sm-2'><input type='number' class='form-control' id='amount' placeholder='Amount' max='1000000' required></div>" +
    "<div class='col-sm-2'><input type='text' class='form-control' id='memo' placeholder='Memo' required></div>" +
    "<div class='col-sm-2'><input type='button' id='getinvoice' onclick='received()' class='btn btn-primary' value='Create invoice' /></div>" +
    '</div></div><br/>'
  document.getElementById('sendfunds').innerHTML = ''
}

function received() {
  memo = document.getElementById('memo').value
  amount = document.getElementById('amount').value
  postAjax(
    '/v1/invoices',
    JSON.stringify({value: amount, memo: memo}),
    wallet.inkey,
    function(data) {
      theinvoice = JSON.parse(data).pay_req
      thehash = JSON.parse(data).payment_hash
      document.getElementById('QRCODE').innerHTML =
        "<div class='col-md-4'><div class='box'><div class='box-header'>" +
        "<center><a href='lightning:" +
        theinvoice +
        "'><div id='qrcode'></div></a>" +
        "<p style='word-wrap: break-word;'>" +
        theinvoice +
        '</p></div></div></div></center>'

      new QRCode(document.getElementById('qrcode'), {
        text: theinvoice,
        width: 300,
        height: 300,
        colorDark: '#000000',
        colorLight: '#ffffff',
        correctLevel: QRCode.CorrectLevel.M
      })
      getAjax('/v1/invoice/' + thehash, wallet.inkey, function(datab) {
        console.log(JSON.parse(datab).PAID)
        if (JSON.parse(datab).PAID == 'TRUE') {
          window.location.href = 'wallet?wal=' + wallet.id + '&usr=' + user
        }
      })
    }
  )
}

function cancelsend() {
  window.location.href = 'wallet?wal=' + wallet.id + '&usr=' + user
}

function sendfunds(invoice) {
  var url = '/v1/channels/transactions'
  postAjax(
    url,
    JSON.stringify({payment_request: invoice}),
    wallet.adminkey,
    function(data) {
      thehash = JSON.parse(data).payment_hash
      console.log(JSON.parse(data))
      if (JSON.parse(data).PAID == 'TRUE') {
        window.location.href = 'wallet?wal=' + wallet.id + '&usr=' + user
      }
    }
  )
}

function scanQRsend() {
  document.getElementById('sendfunds').innerHTML =
    "<br/><br/><div class='row'><div class='col-md-4'>" +
    "<div id='loadingMessage'>🎥 Unable to access video stream (please make sure you have a webcam enabled)</div>" +
    "<canvas id='canvas' hidden></canvas><div id='output' hidden><div id='outputMessage'></div>" +
    "<br/><span id='outputData'></span></div></div></div><button type='submit' class='btn btn-primary' onclick='cancelsend()'>Cancel</button><br/><br/>"
  var video = document.createElement('video')
  var canvasElement = document.getElementById('canvas')
  var canvas = canvasElement.getContext('2d')
  var loadingMessage = document.getElementById('loadingMessage')
  var outputContainer = document.getElementById('output')
  var outputMessage = document.getElementById('outputMessage')
  var outputData = document.getElementById('outputData')
  function drawLine(begin, end, color) {
    canvas.beginPath()
    canvas.moveTo(begin.x, begin.y)
    canvas.lineTo(end.x, end.y)
    canvas.lineWidth = 4
    canvas.strokeStyle = color
    canvas.stroke()
  }
  // Use facingMode: environment to attemt to get the front camera on phones
  navigator.mediaDevices
    .getUserMedia({video: {facingMode: 'environment'}})
    .then(function(stream) {
      video.srcObject = stream
      video.setAttribute('playsinline', true) // required to tell iOS safari we don't want fullscreen
      video.play()
      requestAnimationFrame(tick)
    })
  function tick() {
    loadingMessage.innerText = '⌛ Loading video...'
    if (video.readyState === video.HAVE_ENOUGH_DATA) {
      loadingMessage.hidden = true
      canvasElement.hidden = false
      outputContainer.hidden = false
      canvasElement.height = video.videoHeight
      canvasElement.width = video.videoWidth
      canvas.drawImage(video, 0, 0, canvasElement.width, canvasElement.height)
      var imageData = canvas.getImageData(
        0,
        0,
        canvasElement.width,
        canvasElement.height
      )
      var code = jsQR(imageData.data, imageData.width, imageData.height, {
        inversionAttempts: 'dontInvert'
      })
      if (code) {
        drawLine(
          code.location.topLeftCorner,
          code.location.topRightCorner,
          '#FF3B58'
        )
        drawLine(
          code.location.topRightCorner,
          code.location.bottomRightCorner,
          '#FF3B58'
        )
        drawLine(
          code.location.bottomRightCorner,
          code.location.bottomLeftCorner,
          '#FF3B58'
        )
        drawLine(
          code.location.bottomLeftCorner,
          code.location.topLeftCorner,
          '#FF3B58'
        )
        outputMessage.hidden = true
        outputData.parentElement.hidden = false
        outputData.innerText = JSON.stringify(code.data)
        theinvoice = decode(code.data)
        outmemo = theinvoice.data.tags[1].value
        outamount = Number(theinvoice.human_readable_part.amount) / 1000
        if (outamount > Number(wallet.balance)) {
          document.getElementById('sendfunds').innerHTML =
            "<div class='row'><div class='col-md-6'>" +
            "<h3><b style='color:red;'>Not enough funds!</b></h3>" +
            "<button style='margin-left:20px;' type='submit' class='btn btn-primary' onclick='cancelsend()'>Continue</button>" +
            '</br/></br/></div></div>'
        } else {
          document.getElementById('sendfunds').innerHTML =
            "<div class='row'><div class='col-md-6'>" +
            '<h3><b>Invoice details</b></br/>Amount: ' +
            outamount +
            '<br/>Memo: ' +
            outmemo +
            '</h3>' +
            "<h4 style='word-wrap: break-word;'>" +
            JSON.stringify(code.data) +
            '</h4>' +
            "<button type='submit' class='btn btn-primary' onclick='sendfunds(" +
            JSON.stringify(code.data) +
            ")'>Send funds</button>" +
            "<button style='margin-left:20px;' type='submit' class='btn btn-primary' onclick='cancelsend()'>Cancel payment</button>" +
            '</br/></br/></div></div>'
        }
      } else {
        outputMessage.hidden = false
        outputData.parentElement.hidden = true
      }
    }
    requestAnimationFrame(tick)
  }
}

function deletewallet() {
  var url = 'deletewallet?wal=' + wallet.id + '&usr=' + user
  window.location.href = url
}

function sidebarmake() {
  document.getElementById('sidebarmake').innerHTML =
    "<li><div class='form-group'>" +
    "<input  style='width:70%;float:left;' type='text' class='form-control' id='walname' placeholder='Name wallet' required>" +
    "<button style='width:30%;float:left;' type='button' class='btn btn-primary' onclick='newwallet()'>Submit</button>" +
    '</div></li><br/><br/>'
}

function newwallet() {
  walname = document.getElementById('walname').value
  window.location.href = 'wallet?usr=' + user + '&nme=' + walname
}

function drawChart(transactions) {
  var linechart = []
  var transactionsHTML = ''
  var balance = 0

  for (var i = 0; i < transactions.length; i++) {
    var tx = transactions[i]
    var datime = convertTimestamp(tx.time)

    // make the transactions table
    transactionsHTML +=
      "<tr><td  style='width: 50%'>" +
      tx.memo +
      '</td><td>' +
      datime +
      '</td><td>' +
      parseFloat(tx.amount / 1000) +
      '</td></tr>'

    // make the line chart
    balance += parseInt(tx.amount / 1000)
    linechart.push({y: datime, balance: balance})
  }

  document.getElementById('transactions').innerHTML = transactionsHTML

  if (linechart[0] != '') {
    document.getElementById('satschart').innerHTML =
      "<div class='row'><div class='col-md-6'><div class='box box-info'><div class='box-header'>" +
      "<h3 class='box-title'>Spending</h3></div><div class='box-body chart-responsive'>" +
      "<div class='chart' id='line-chart' style='height: 300px;'></div></div></div></div></div>"
  }

  console.log(linechart)
  var line = new Morris.Line({
    element: 'line-chart',
    resize: true,
    data: linechart,
    xkey: 'y',
    ykeys: ['balance'],
    labels: ['balance'],
    lineColors: ['#3c8dbc'],
    hideHover: 'auto'
  })
}

function convertTimestamp(timestamp) {
  var d = new Date(timestamp * 1000),
    yyyy = d.getFullYear(),
    mm = ('0' + (d.getMonth() + 1)).slice(-2),
    dd = ('0' + d.getDate()).slice(-2),
    hh = d.getHours(),
    h = hh,
    min = ('0' + d.getMinutes()).slice(-2),
    ampm = 'AM',
    time
  time = yyyy + '-' + mm + '-' + dd + ' ' + h + ':' + min
  return time
}

if (transactions.length) {
  drawChart(transactions)
}

if (wallet) {
  postAjax('/v1/checkpending', '', wallet.adminkey, function(data) {})
}
