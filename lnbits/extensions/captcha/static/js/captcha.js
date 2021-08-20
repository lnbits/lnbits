var ciframeLoaded = !1,
  captchaStyleAdded = !1

function ccreateIframeElement(t = {}) {
  const e = document.createElement('iframe')
  // e.style.marginLeft = "25px",
  ;(e.style.border = 'none'),
    (e.style.width = '100%'),
    (e.style.height = '100%'),
    (e.scrolling = 'no'),
    (e.id = 'captcha-iframe')
  t.dest, t.amount, t.currency, t.label, t.opReturn
  var captchaid = document
    .getElementById('captchascript')
    .getAttribute('data-captchaid')
  var lnbhostsrc = document.getElementById('captchascript').getAttribute('src')
  var lnbhost = lnbhostsrc.split('/captcha/static/js/captcha.js')[0]
  return (e.src = lnbhost + '/captcha/' + captchaid), e
}
document.addEventListener('DOMContentLoaded', function () {
  if (captchaStyleAdded) console.log('Captcha already added!')
  else {
    console.log('Adding captcha'), (captchaStyleAdded = !0)
    var t = document.createElement('style')
    t.innerHTML =
      "\t/*Button*/\t\t.button-captcha-filled\t\t\t{\t\t\tdisplay: flex;\t\t\talign-items: center;\t\t\tjustify-content: center;\t\t\twidth: 120px;\t\t\tmin-width: 30px;\t\t\theight: 40px;\t\t\tline-height: 2.5;\t\t\ttext-align: center;\t\t\tcursor: pointer;\t\t\t/* Rectangle 2: */\t\t\tbackground: #FF7979;\t\t\tbox-shadow: 0 2px 4px 0 rgba(0,0,0,0.20);\t\t\tborder-radius: 20px;\t\t\t/* Sign up: */\t\t\tfont-family: 'Avenir-Heavy', Futura, Helvetica, Arial;\t\t\tfont-size: 16px;\t\t\tcolor: #FFFFFF;\t\t}\t\t.button-captcha-filled:hover\t\t{\t\t\tbackground:#FFFFFF;\t\t\tcolor: #FF7979;\t\t\tbox-shadow: 0 0 4px 0 rgba(0,0,0,0.20);\t\t}\t\t.button-captcha-filled:active\t\t{\t\t\tbackground:#FFFFFF;\t\t\tcolor: #FF7979;\t\t\t/*Move it down a little bit*/\t\t\tposition: relative;\t\t\ttop: 1px;\t\t}\t\t.button-captcha-filled-dark\t\t\t{\t\t\tdisplay: flex;\t\t\talign-items: center;\t\t\tjustify-content: center;\t\t\twidth: 120px;\t\t\tmin-width: 30px;\t\t\theight: 40px;\t\t\tline-height: 2.5;\t\t\ttext-align: center;\t\t\tcursor: pointer;\t\t\t/* Rectangle 2: */\t\t\tbackground: #161C38;\t\t\tbox-shadow: 0 0px 4px 0 rgba(0,0,0,0.20);\t\t\tborder-radius: 20px;\t\t\t/* Sign up: */\t\t\tfont-family: 'Avenir-Heavy', Futura, Helvetica, Arial;\t\t\tfont-size: 16px;\t\t\tcolor: #FFFFFF;\t\t}\t\t.button-captcha-filled-dark:hover\t\t{\t\t\tbackground:#FFFFFF;\t\t\tcolor: #161C38;\t\t\tbox-shadow: 0 0px 4px 0 rgba(0,0,0,0.20);\t\t}\t\t.button-captcha-filled-dark:active\t\t{\t\t\tbackground:#FFFFFF;\t\t\tcolor: #161C38;\t\t\t/*Move it down a little bit*/\t\t\tposition: relative;\t\t\ttop: 1px;\t\t}\t\t.modal-captcha-container {\t\t    position: fixed;\t\t    z-index: 1000;\t\t    text-align: left;/*Si no añado esto, a veces hereda el text-align:center del body, y entonces el popup queda movido a la derecha, por center + margin left que aplico*/\t\t    left: 0;\t\t    top: 0;\t\t    width: 100%;\t\t    height: 100%;\t\t    background-color: rgba(0, 0, 0, 0.5);\t\t    opacity: 0;\t\t    visibility: hidden;\t\t    transform: scale(1.1);\t\t    transition: visibility 0s linear 0.25s, opacity 0.25s 0s, transform 0.25s;\t\t}\t\t.modal-captcha-content {\t\t    position: absolute;\t\t    top: 50%;\t\t    left: 50%;\t\t    transform: translate(-50%, -50%);\t\t    background-color: white;\t\t    width: 100%;\t\t    height: 100%;\t\t    border-radius: 0.5rem;\t\t    /*Rounded shadowed borders*/\t\t\tbox-shadow: 2px 2px 4px 0 rgba(0,0,0,0.15);\t\t\tborder-radius: 5px;\t\t}\t\t.close-button-captcha {\t\t    float: right;\t\t    width: 1.5rem;\t\t    line-height: 1.5rem;\t\t    text-align: center;\t\t    cursor: pointer;\t\t    margin-right:20px;\t\t    margin-top:10px;\t\t    border-radius: 0.25rem;\t\t    background-color: lightgray;\t\t}\t\t.close-button-captcha:hover {\t\t    background-color: darkgray;\t\t}\t\t.show-modal-captcha {\t\t    opacity: 1;\t\t    visibility: visible;\t\t    transform: scale(1.0);\t\t    transition: visibility 0s linear 0s, opacity 0.25s 0s, transform 0.25s;\t\t}\t\t/* Mobile */\t\t@media screen and (min-device-width: 160px) and ( max-width: 1077px ) /*No tendria ni por que poner un min-device, porq abarca todo lo humano...*/\t\t{\t\t}"
    var e = document.querySelector('script')
    e.parentNode.insertBefore(t, e)
    var i = document.getElementById('captchacheckbox'),
      n = i.dataset,
      o = 'true' === n.dark
    var a = document.createElement('div')
    ;(a.className += ' modal-captcha-container'),
      (a.innerHTML =
        '\t\t<div class="modal-captcha-content">        \t<span class="close-button-captcha" style="display: none;">&times;</span>\t\t</div>\t'),
      document.getElementsByTagName('body')[0].appendChild(a)
    var r = document.getElementsByClassName('modal-captcha-content').item(0)
    document
      .getElementsByClassName('close-button-captcha')
      .item(0)
      .addEventListener('click', d),
      window.addEventListener('click', function (t) {
        t.target === a && d()
      }),
      i.addEventListener('change', function () {
        if (this.checked) {
          // console.log("checkbox checked");
          if (0 == ciframeLoaded) {
            // console.log("n: ", n);
            var t = ccreateIframeElement(n)
            r.appendChild(t), (ciframeLoaded = !0)
          }
          d()
        }
      })
  }

  function d() {
    a.classList.toggle('show-modal-captcha')
  }
})

function receiveMessage(event) {
  if (event.data.includes('paymenthash')) {
    // console.log("paymenthash received: ", event.data);
    document.getElementById('captchapayhash').value = event.data.split('_')[1]
  }
  if (event.data.includes('removetheiframe')) {
    if (event.data.includes('nok')) {
      //invoice was NOT paid
      // console.log("receiveMessage not paid")
      document.getElementById('captchacheckbox').checked = false
    }
    ciframeLoaded = !1
    var element = document.getElementById('captcha-iframe')
    document
      .getElementsByClassName('modal-captcha-container')[0]
      .classList.toggle('show-modal-captcha')
    element.parentNode.removeChild(element)
  }
}
window.addEventListener('message', receiveMessage, false)
