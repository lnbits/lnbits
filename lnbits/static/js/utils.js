window._lnbitsUtils = {
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
  async digestMessage(message) {
    const msgUint8 = new TextEncoder().encode(message)
    const hashBuffer = await crypto.subtle.digest('SHA-256', msgUint8)
    const hashArray = Array.from(new Uint8Array(hashBuffer))
    const hashHex = hashArray.map(b => b.toString(16).padStart(2, '0')).join('')
    return hashHex
  },
  formatDate(timestamp) {
    return Quasar.date.formatDate(new Date(timestamp * 1000), window.dateFormat)
  },
  formatDateString(isoDateString) {
    return Quasar.date.formatDate(new Date(isoDateString), window.dateFormat)
  },
  formatCurrency(value, currency) {
    return new Intl.NumberFormat(window.LOCALE, {
      style: 'currency',
      currency: currency || 'sat'
    }).format(value)
  },
  formatSat(value) {
    return new Intl.NumberFormat(window.LOCALE).format(value)
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
  prepareFilterQuery(tableConfig, props) {
    tableConfig.filter = tableConfig.filter || {}
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
  }
}
