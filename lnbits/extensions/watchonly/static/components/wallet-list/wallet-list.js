async function walletList(path) {
  const template = await loadTemplateAsync(path)
  Vue.component('wallet-list', {
    name: 'wallet-list',
    template,

    props: [
      'adminkey',
      'inkey',
      'sats-denominated',
      'addresses',
      'network',
      'serial-signer-ref'
    ],
    data: function () {
      return {
        walletAccounts: [],
        address: {},
        showQrCodeDialog: false,
        qrCodeValue: null,
        formDialog: {
          show: false,

          addressType: {
            label: 'Segwit (P2WPKH)',
            id: 'wpkh',
            pathMainnet: "m/84'/0'/0'",
            pathTestnet: "m/84'/1'/0'"
          },
          useSerialPort: false,
          data: {
            title: '',
            masterpub: ''
          }
        },
        accountPath: '',
        filter: '',
        showCreating: false,
        addressTypeOptions: [
          {
            label: 'Legacy (P2PKH)',
            id: 'pkh',
            pathMainnet: "m/44'/0'/0'",
            pathTestnet: "m/44'/1'/0'"
          },
          {
            label: 'Segwit (P2WPKH)',
            id: 'wpkh',
            pathMainnet: "m/84'/0'/0'",
            pathTestnet: "m/84'/1'/0'"
          },
          {
            label: 'Wrapped Segwit (P2SH-P2WPKH)',
            id: 'sh',
            pathMainnet: "m/49'/0'/0'",
            pathTestnet: "m/49'/1'/0'"
          },
          {
            label: 'Taproot (P2TR)',
            id: 'tr',
            pathMainnet: "m/86'/0'/0'",
            pathTestnet: "m/86'/1'/0'"
          }
        ],

        walletsTable: {
          columns: [
            {
              name: 'new',
              align: 'left',
              label: ''
            },
            {
              name: 'title',
              align: 'left',
              label: 'Title',
              field: 'title'
            },
            {
              name: 'amount',
              align: 'left',
              label: 'Amount'
            },
            {
              name: 'type',
              align: 'left',
              label: 'Type',
              field: 'type'
            },
            {name: 'id', align: 'left', label: 'ID', field: 'id'}
          ],
          pagination: {
            rowsPerPage: 10
          },
          filter: ''
        }
      }
    },
    watch: {
      immediate: true,
      async network(newNet, oldNet) {
        if (newNet !== oldNet) {
          await this.refreshWalletAccounts()
          this.handleAddressTypeChanged(this.addressTypeOptions[1])
        }
      }
    },

    methods: {
      satBtc(val, showUnit = true) {
        return satOrBtc(val, showUnit, this.satsDenominated)
      },

      addWalletAccount: async function () {
        this.showCreating = true
        const data = _.omit(this.formDialog.data, 'wallet')
        data.network = this.network
        await this.createWalletAccount(data)
        this.showCreating = false
      },
      createWalletAccount: async function (data) {
        try {
          const meta = {accountPath: this.accountPath}
          if (this.formDialog.useSerialPort) {
            const {xpub, fingerprint} = await this.fetchXpubFromHww()
            if (!xpub) return
            meta.xpub = xpub
            const path = this.accountPath.substring(2)
            const outputType = this.formDialog.addressType.id
            if (outputType === 'sh') {
              data.masterpub = `${outputType}(wpkh([${fingerprint}/${path}]${xpub}/{0,1}/*))`
            } else {
              data.masterpub = `${outputType}([${fingerprint}/${path}]${xpub}/{0,1}/*)`
            }
          }
          data.meta = JSON.stringify(meta)
          const response = await LNbits.api.request(
            'POST',
            '/watchonly/api/v1/wallet',
            this.adminkey,
            data
          )
          this.walletAccounts.push(mapWalletAccount(response.data))
          this.formDialog.show = false

          await this.refreshWalletAccounts()
        } catch (error) {
          LNbits.utils.notifyApiError(error)
        }
      },
      fetchXpubFromHww: async function () {
        const error = findAccountPathIssues(this.accountPath)
        if (error) {
          this.$q.notify({
            type: 'warning',
            message: 'Invalid derivation path.',
            caption: error,
            timeout: 10000
          })
          return
        }
        await this.serialSignerRef.hwwXpub(this.accountPath)
        return await this.serialSignerRef.isFetchingXpub()
      },
      deleteWalletAccount: function (walletAccountId) {
        LNbits.utils
          .confirmDialog(
            'Are you sure you want to delete this watch only wallet?'
          )
          .onOk(async () => {
            try {
              await LNbits.api.request(
                'DELETE',
                '/watchonly/api/v1/wallet/' + walletAccountId,
                this.adminkey
              )
              this.walletAccounts = _.reject(
                this.walletAccounts,
                function (obj) {
                  return obj.id === walletAccountId
                }
              )
              await this.refreshWalletAccounts()
            } catch (error) {
              this.$q.notify({
                type: 'warning',
                message:
                  'Error while deleting wallet account. Please try again.',
                timeout: 10000
              })
            }
          })
      },

      getWatchOnlyWallets: async function () {
        try {
          const {data} = await LNbits.api.request(
            'GET',
            `/watchonly/api/v1/wallet?network=${this.network}`,
            this.inkey
          )
          return data
        } catch (error) {
          this.$q.notify({
            type: 'warning',
            message: 'Failed to fetch wallets.',
            timeout: 10000
          })
          LNbits.utils.notifyApiError(error)
        }
        return []
      },
      refreshWalletAccounts: async function () {
        this.walletAccounts = []
        const wallets = await this.getWatchOnlyWallets()
        this.walletAccounts = wallets.map(w => mapWalletAccount(w))
        this.$emit('accounts-update', this.walletAccounts)
      },
      getAmmountForWallet: function (walletId) {
        const amount = this.addresses
          .filter(a => a.wallet === walletId)
          .reduce((t, a) => t + a.amount || 0, 0)
        return this.satBtc(amount)
      },
      closeFormDialog: function () {
        this.formDialog.data = {
          is_unique: false
        }
      },
      getAccountDescription: function (accountType) {
        return getAccountDescription(accountType)
      },
      openGetFreshAddressDialog: async function (walletId) {
        const {data} = await LNbits.api.request(
          'GET',
          `/watchonly/api/v1/address/${walletId}`,
          this.inkey
        )
        const addressData = mapAddressesData(data)

        addressData.note = `Shared on ${currentDateTime()}`
        const lastActiveAddress =
          this.addresses
            .filter(
              a =>
                a.wallet === addressData.wallet && !a.isChange && a.hasActivity
            )
            .pop() || {}
        addressData.gapLimitExceeded =
          !addressData.isChange &&
          addressData.addressIndex >
            lastActiveAddress.addressIndex + DEFAULT_RECEIVE_GAP_LIMIT

        const wallet = this.walletAccounts.find(w => w.id === walletId) || {}
        wallet.address_no = addressData.addressIndex
        this.$emit('new-receive-address', {addressData, wallet})
      },
      showAddAccountDialog: function () {
        this.formDialog.show = true
        this.formDialog.useSerialPort = false
      },
      getXpubFromDevice: async function () {
        try {
          if (!this.serialSignerRef.isConnected()) {
            this.$q.notify({
              type: 'warning',
              message: 'Please connect to a hardware Device first!',
              timeout: 10000
            })
            return
          }
          if (!this.serialSignerRef.isAuthenticated()) {
            await this.serialSignerRef.hwwShowPasswordDialog()
            const authenticated = await this.serialSignerRef.isAuthenticating()
            if (!authenticated) return
          }
          this.formDialog.show = true
          this.formDialog.useSerialPort = true
        } catch (error) {
          this.$q.notify({
            type: 'warning',
            message: 'Cannot fetch Xpub!',
            caption: `${error}`,
            timeout: 10000
          })
        }
      },
      handleAddressTypeChanged: function (value = {}) {
        const addressType =
          this.addressTypeOptions.find(t => t.id === value.id) || {}
        this.accountPath = addressType[`path${this.network}`]
      },
      // todo: bad. base.js not present in custom components
      copyText: function (text, message, position) {
        var notify = this.$q.notify
        Quasar.utils.copyToClipboard(text).then(function () {
          notify({
            message: message || 'Copied to clipboard!',
            position: position || 'bottom'
          })
        })
      },
      openQrCodeDialog: function (qrCodeValue) {
        this.qrCodeValue = qrCodeValue
        this.showQrCodeDialog = true
      }
    },
    created: async function () {
      if (this.inkey) {
        await this.refreshWalletAccounts()
        this.handleAddressTypeChanged(this.addressTypeOptions[1])
      }
    }
  })
}
