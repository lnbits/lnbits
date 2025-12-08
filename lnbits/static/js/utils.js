window._lnbitsUtils = {
  url_for(url) {
    const _url = new URL(url, window.location.origin)
    _url.searchParams.set('v', WINDOW_SETTINGS.CACHE_KEY)
    return _url.toString()
  },
  loadScript(src) {
    return new Promise((resolve, reject) => {
      const script = document.createElement('script')
      script.src = this.url_for(src)
      script.onload = () => {
        resolve()
      }
      script.onerror = () => {
        reject(new Error(`Failed to load script ${src}`))
      }
      document.body.appendChild(script)
    })
  },
  async loadTemplate(url) {
    return fetch(this.url_for(url))
      .then(response => {
        if (!response.ok) {
          throw new Error(`Failed to load template from ${url}`)
        }
        return response.text()
      })
      .then(html => {
        const template = document.createElement('div')
        template.innerHTML = html.trim()
        document.body.appendChild(template)
      })
  },
  copyText(text, message, position) {
    Quasar.copyToClipboard(text).then(() => {
      Quasar.Notify.create({
        message: message || 'Copied to clipboard!',
        position: position || 'bottom'
      })
    })
  },
  confirmDialog(msg) {
    return Quasar.Dialog.create({
      message: msg,
      ok: {
        flat: true,
        color: 'orange'
      },
      cancel: {
        flat: true,
        color: 'grey'
      }
    })
  },
  async logout() {
    LNbits.utils
      .confirmDialog(
        'Do you really want to logout?' +
          ' Please visit "My Account" page to check your credentials!'
      )
      .onOk(async () => {
        try {
          await LNbits.api.logout()
          window.location = '/'
        } catch (e) {
          LNbits.utils.notifyApiError(e)
        }
      })
  },
  async digestMessage(message) {
    const msgUint8 = new TextEncoder().encode(message)
    const hashBuffer = await crypto.subtle.digest('SHA-256', msgUint8)
    const hashArray = Array.from(new Uint8Array(hashBuffer))
    const hashHex = hashArray.map(b => b.toString(16).padStart(2, '0')).join('')
    return hashHex
  },
  formatTimestamp(timestamp, format = null) {
    format = format || window.dateFormat
    return Quasar.date.formatDate(new Date(timestamp * 1000), format)
  },
  // backwards compatibility for extensions
  formatDateString(isoDateString) {
    this.formatDate(isoDateString)
  },
  formatDate(isoDateString, format = null) {
    format = format || window.dateFormat
    return Quasar.date.formatDate(new Date(isoDateString), format)
  },
  formatTimestampFrom(timestamp) {
    return moment
      .utc(timestamp * 1000)
      .local()
      .fromNow()
  },
  formatDateFrom(isoDateString) {
    const timestampMs = new Date(isoDateString).getTime()
    return moment.utc(timestampMs).local().fromNow()
  },
  formatBalance(amount, denomination = 'sats') {
    if (denomination === 'sats') {
      return LNbits.utils.formatSat(amount) + ' sats'
    }
    return LNbits.utils.formatCurrency(amount / 100, denomination)
  },
  formatCurrency(value, currency) {
    return new Intl.NumberFormat(window.i18n.global.locale, {
      style: 'currency',
      currency: currency || 'sat'
    }).format(value)
  },
  formatSat(value) {
    return new Intl.NumberFormat(window.i18n.global.locale).format(value)
  },
  formatMsat(value) {
    return this.formatSat(value / 1000)
  },
  notifyApiError(error) {
    if (!error.response) {
      return console.error(error)
    }
    const types = {
      400: 'warning',
      401: 'warning',
      500: 'negative'
    }
    Quasar.Notify.create({
      timeout: 5000,
      type: types[error.response.status] || 'warning',
      message:
        error.response.data.message || error.response.data.detail || null,
      caption:
        [error.response.status, ' ', error.response.statusText]
          .join('')
          .toUpperCase() || null,
      icon: null
    })
  },
  search(data, q, field, separator) {
    try {
      const queries = q.toLowerCase().split(separator || ' ')
      return data.filter(obj => {
        let matches = 0
        _.each(queries, q => {
          if (obj[field].indexOf(q) !== -1) matches++
        })
        return matches === queries.length
      })
    } catch (err) {
      return data
    }
  },
  prepareFilterQuery(tableConfig, props, filter) {
    tableConfig.filter = filter || tableConfig.filter || {}
    if (props) {
      tableConfig.pagination = props.pagination
      Object.assign(tableConfig.filter, props.filter)
    }
    const pagination = tableConfig.pagination
    tableConfig.loading = true
    const query = {
      limit: pagination.rowsPerPage,
      offset: (pagination.page - 1) * pagination.rowsPerPage,
      sortby: pagination.sortBy ?? '',
      direction: pagination.descending ? 'desc' : 'asc',
      ...tableConfig.filter
    }
    if (tableConfig.search) {
      query.search = tableConfig.search
    }
    return new URLSearchParams(query)
  },
  exportCSV(columns, data, fileName) {
    const wrapCsvValue = (val, formatFn) => {
      let formatted = formatFn !== void 0 ? formatFn(val) : val

      formatted =
        formatted === void 0 || formatted === null ? '' : String(formatted)

      formatted = formatted.split('"').join('""')

      return `"${formatted}"`
    }

    const content = [
      columns.map(col => {
        return wrapCsvValue(col.label)
      })
    ]
      .concat(
        data.map(row => {
          return columns
            .map(col => {
              return wrapCsvValue(
                typeof col.field === 'function'
                  ? col.field(row)
                  : row[col.field === void 0 ? col.name : col.field],
                col.format
              )
            })
            .join(',')
        })
      )
      .join('\r\n')

    const status = Quasar.exportFile(
      `${fileName || 'table-export'}.csv`,
      content,
      'text/csv'
    )

    if (status !== true) {
      Quasar.Notify.create({
        message: 'Browser denied file download...',
        color: 'negative',
        icon: null
      })
    }
  },
  convertMarkdown(text) {
    const converter = new showdown.Converter()
    converter.setFlavor('github')
    converter.setOption('simpleLineBreaks', true)
    return converter.makeHtml(text)
  },
  async decryptLnurlPayAES(success_action, preimage) {
    let keyb = new Uint8Array(
      preimage.match(/[\da-f]{2}/gi).map(h => parseInt(h, 16))
    )

    return crypto.subtle
      .importKey('raw', keyb, {name: 'AES-CBC', length: 256}, false, [
        'decrypt'
      ])
      .then(key => {
        let ivb = Uint8Array.from(window.atob(success_action.iv), c =>
          c.charCodeAt(0)
        )
        let ciphertextb = Uint8Array.from(
          window.atob(success_action.ciphertext),
          c => c.charCodeAt(0)
        )

        return crypto.subtle.decrypt(
          {name: 'AES-CBC', iv: ivb},
          key,
          ciphertextb
        )
      })
      .then(valueb => {
        let decoder = new TextDecoder('utf-8')
        return decoder.decode(valueb)
      })
  }
}
