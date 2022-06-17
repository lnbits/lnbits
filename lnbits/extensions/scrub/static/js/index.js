/* globals Quasar, Vue, _, VueQrcode, windowMixin, LNbits, LOCALE */

Vue.component(VueQrcode.name, VueQrcode)

var locationPath = [
  window.location.protocol,
  '//',
  window.location.host,
  window.location.pathname
].join('')

var mapScrubLink = obj => {
  obj._data = _.clone(obj)
  obj.date = Quasar.utils.date.formatDate(
    new Date(obj.time * 1000),
    'YYYY-MM-DD HH:mm'
  )
  obj.amount = new Intl.NumberFormat(LOCALE).format(obj.amount)
  obj.print_url = [locationPath, 'print/', obj.id].join('')
  obj.pay_url = [locationPath, obj.id].join('')
  return obj
}

new Vue({
  el: '#vue',
  mixins: [windowMixin],
  data() {
    return {
      currencies: [],
      fiatRates: {},
      checker: null,
      payLinks: [],
      payLinksTable: {
        pagination: {
          rowsPerPage: 10
        }
      },
      formDialog: {
        show: false,
        fixedAmount: true,
        data: {}
      },
      qrCodeDialog: {
        show: false,
        data: null
      }
    }
  },
  methods: {
    getScrubLinks() {
      LNbits.api
        .request(
          'GET',
          '/scrub/api/v1/links?all_wallets=true',
          this.g.user.wallets[0].inkey
        )
        .then(response => {
          this.payLinks = response.data.map(mapScrubLink)
        })
        .catch(err => {
          clearInterval(this.checker)
          LNbits.utils.notifyApiError(err)
        })
    },
    closeFormDialog() {
      this.resetFormData()
    },
    openQrCodeDialog(linkId) {
      var link = _.findWhere(this.payLinks, {id: linkId})
      if (link.currency) this.updateFiatRate(link.currency)

      this.qrCodeDialog.data = {
        id: link.id,
        amount:
          (link.min === link.max ? link.min : `${link.min} - ${link.max}`) +
          ' ' +
          (link.currency || 'sat'),
        currency: link.currency,
        comments: link.comment_chars
          ? `${link.comment_chars} characters`
          : 'no',
        webhook: link.webhook_url || 'nowhere',
        success:
          link.success_text || link.success_url
            ? 'Display message "' +
              link.success_text +
              '"' +
              (link.success_url ? ' and URL "' + link.success_url + '"' : '')
            : 'do nothing',
        lnurl: link.lnurl,
        pay_url: link.pay_url,
        print_url: link.print_url
      }
      this.qrCodeDialog.show = true
    },
    openUpdateDialog(linkId) {
      const link = _.findWhere(this.payLinks, {id: linkId})
      if (link.currency) this.updateFiatRate(link.currency)

      this.formDialog.data = _.clone(link._data)
      this.formDialog.show = true
      this.formDialog.fixedAmount =
        this.formDialog.data.min === this.formDialog.data.max
    },
    sendFormData() {
      const wallet = _.findWhere(this.g.user.wallets, {
        id: this.formDialog.data.wallet
      })
      let data = Object.freeze(this.formDialog.data)
      console.log(wallet, data)

      if (data.id) {
        this.updateScrubLink(wallet, data)
      } else {
        this.createScrubLink(wallet, data)
      }
    },
    resetFormData() {
      this.formDialog = {
        show: false,
        fixedAmount: true,
        data: {}
      }
    },
    updateScrubLink(wallet, data) {
      let values = _.omit(
        _.pick(
          data,
          'description',
          'min',
          'max',
          'webhook_url',
          'success_text',
          'success_url',
          'comment_chars',
          'currency'
        ),
        (value, key) =>
          (key === 'webhook_url' ||
            key === 'success_text' ||
            key === 'success_url') &&
          (value === null || value === '')
      )

      LNbits.api
        .request(
          'PUT',
          '/scrub/api/v1/links/' + data.id,
          wallet.adminkey,
          values
        )
        .then(response => {
          this.payLinks = _.reject(this.payLinks, obj => obj.id === data.id)
          this.payLinks.push(mapScrubLink(response.data))
          this.formDialog.show = false
          this.resetFormData()
        })
        .catch(err => {
          LNbits.utils.notifyApiError(err)
        })
    },
    createScrubLink(wallet, data) {
      LNbits.api
        .request('POST', '/scrub/api/v1/links', wallet.adminkey, data)
        .then(response => {
          console.log('RES', response)
          this.getScrubLinks()
          this.formDialog.show = false
          this.resetFormData()
        })
        .catch(err => {
          LNbits.utils.notifyApiError(err)
        })
    },
    deleteScrubLink(linkId) {
      var link = _.findWhere(this.payLinks, {id: linkId})

      LNbits.utils
        .confirmDialog('Are you sure you want to delete this pay link?')
        .onOk(() => {
          LNbits.api
            .request(
              'DELETE',
              '/scrub/api/v1/links/' + linkId,
              _.findWhere(this.g.user.wallets, {id: link.wallet}).adminkey
            )
            .then(response => {
              this.payLinks = _.reject(this.payLinks, obj => obj.id === linkId)
            })
            .catch(err => {
              LNbits.utils.notifyApiError(err)
            })
        })
    },
    updateFiatRate(currency) {
      LNbits.api
        .request('GET', '/scrub/api/v1/rate/' + currency, null)
        .then(response => {
          let rates = _.clone(this.fiatRates)
          rates[currency] = response.data.rate
          this.fiatRates = rates
        })
        .catch(err => {
          LNbits.utils.notifyApiError(err)
        })
    }
  },
  created() {
    if (this.g.user.wallets.length) {
      var getScrubLinks = this.getScrubLinks
      getScrubLinks()
      // this.checker = setInterval(() => {
      //   getScrubLinks()
      // }, 20000)
    }
    LNbits.api
      .request('GET', '/scrub/api/v1/currencies')
      .then(response => {
        this.currencies = ['satoshis', ...response.data]
      })
      .catch(err => {
        LNbits.utils.notifyApiError(err)
      })
  }
})
