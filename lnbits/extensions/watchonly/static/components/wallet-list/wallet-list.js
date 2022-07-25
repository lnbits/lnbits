async function walletList(path) {
  const template = await loadTemplateAsync(path)
  Vue.component('wallet-list', {
    name: 'wallet-list',
    template,

    props: ['adminkey', 'inkey', 'sats-denominated', 'addresses'],
    data: function () {
      return {
        walletAccounts: [],
        address: {},
        formDialog: {
          show: false,
          data: {}
        },
        filter: '',
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

    methods: {
      satBtc(val, showUnit = true) {
        return satOrBtc(val, showUnit, this['sats_denominated'])
      },

      addWalletAccount: async function () {
        const data = _.omit(this.formDialog.data, 'wallet')
        await this.createWalletAccount(data)
      },
      createWalletAccount: async function (data) {
        try {
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
              this.walletAccounts = _.reject(this.walletAccounts, function (
                obj
              ) {
                return obj.id === walletAccountId
              })
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
            '/watchonly/api/v1/wallet',
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
        const lastAcctiveAddress =
          this.addresses
            .filter(
              a =>
                a.wallet === addressData.wallet && !a.isChange && a.hasActivity
            )
            .pop() || {}
        addressData.gapLimitExceeded =
          !addressData.isChange &&
          addressData.addressIndex >
            lastAcctiveAddress.addressIndex + DEFAULT_RECEIVE_GAP_LIMIT

        const wallet = this.walletAccounts.find(w => w.id === walletId) || {}
        wallet.address_no = addressData.addressIndex
        this.$emit('new-receive-address', addressData)
      }
    },
    created: async function () {
      if (this.inkey) {
        await this.refreshWalletAccounts()
      }
    }
  })
}
