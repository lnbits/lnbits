window._lnbitsApi = {
  request(method, url, apiKey, data, options = {}) {
    const rootPath = '/lnbits/'
    url = rootPath + url.replace(/^\/+/, '') // Ensure single slash after rootPath
    console.log(`API Request: ${method.toUpperCase()} ${url}`)
    return axios({
      method: method,
      url: url,
      headers: {
        'X-Api-Key': apiKey
      },
      data: data,
      ...options
    })
  },
  getServerHealth() {
    return this.request('get', '/api/v1/health')
  },
  async createInvoice(
    wallet,
    amount,
    memo,
    unit = 'sat',
    lnurlWithdraw = null,
    fiatProvider = null,
    internalMemo = null,
    payment_hash = null
  ) {
    const data = {
      out: false,
      amount: amount,
      memo: memo,
      unit: unit,
      lnurl_withdraw: lnurlWithdraw,
      fiat_provider: fiatProvider,
      payment_hash: payment_hash
    }
    if (internalMemo) {
      data.extra = {
        internal_memo: String(internalMemo)
      }
    }
    return this.request('post', '/api/v1/payments', wallet.inkey, data)
  },
  payInvoice(wallet, bolt11, internalMemo = null) {
    const data = {
      out: true,
      bolt11: bolt11
    }
    if (internalMemo) {
      data.extra = {
        internal_memo: String(internalMemo)
      }
    }
    return this.request('post', '/api/v1/payments', wallet.adminkey, data)
  },
  cancelInvoice(wallet, paymentHash) {
    return this.request('post', '/api/v1/payments/cancel', wallet.adminkey, {
      payment_hash: paymentHash
    })
  },
  settleInvoice(wallet, preimage) {
    return this.request('post', `/api/v1/payments/settle`, wallet.adminkey, {
      preimage: preimage
    })
  },
  createAccount(name) {
    return this.request('post', '/api/v1/account', null, {
      name: name
    })
  },
  register(username, email, password, password_repeat) {
    return this.request('post', '/api/v1/auth/register', null, {
      username,
      email,
      password,
      password_repeat
    })
  },
  reset(reset_key, password, password_repeat) {
    return this.request('put', '/api/v1/auth/reset', null, {
      reset_key,
      password,
      password_repeat
    })
  },
  getAuthUser() {
    return this.request('get', '/api/v1/auth')
  },
  login(username, password) {
    return this.request('post', '/api/v1/auth', null, {username, password})
  },
  loginByProvider(provider, headers, data) {
    return this.request('post', `/api/v1/auth/${provider}`, null, data)
  },
  loginUsr(usr) {
    return this.request('post', '/api/v1/auth/usr', null, {usr})
  },
  logout() {
    return this.request('post', '/api/v1/auth/logout')
  },
  impersonateUser(usr) {
    return this.request('POST', '/api/v1/auth/impersonate', null, {usr})
  },
  stopImpersonation() {
    return this.request('DELETE', '/api/v1/auth/impersonate')
  },
  getAuthenticatedUser() {
    return this.request('get', '/api/v1/auth')
  },
  getWallet(wallet) {
    return this.request('get', '/api/v1/wallet', wallet.inkey)
  },
  createWallet(name, walletType, opts = {}) {
    return this.request('post', '/api/v1/wallet', null, {
      name: name,
      wallet_type: walletType,
      ...opts
    }).catch(LNbits.utils.notifyApiError)
  },
  updateWallet(name, wallet) {
    return this.request('patch', '/api/v1/wallet', wallet.adminkey, {
      name: name
    })
  },
  updateUiCustomization(data = {}) {
    return this.request('patch', '/api/v1/auth/ui', null, data)
  },
  resetWalletKeys(wallet) {
    return this.request('put', `/api/v1/wallet/reset/${wallet.id}`).then(
      res => {
        return res.data
      }
    )
  },
  deleteWallet(wallet) {
    return this.request('delete', `/api/v1/wallet/${wallet.id}`)
  },
  getPayments(wallet, params) {
    return this.request(
      'get',
      '/api/v1/payments/paginated?' + params,
      wallet.inkey
    )
  },
  getPayment(wallet, paymentHash) {
    return this.request('get', '/api/v1/payments/' + paymentHash, wallet.inkey)
  },
  updateBalance(credit, wallet_id) {
    return this.request('PUT', '/users/api/v1/balance', null, {
      amount: credit,
      id: wallet_id
    })
  },
  getCurrencies() {
    return this.request('GET', '/api/v1/currencies').then(response => {
      return ['sats', ...response.data]
    })
  },
  getDefaultSetting(fieldName) {
    return LNbits.api
      .request('GET', `/admin/api/v1/settings/default?field_name=${fieldName}`)
      .catch(LNbits.utils.notifyApiError)
  }
}
