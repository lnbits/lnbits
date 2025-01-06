window.UsersPageLogic = {
  mixins: [window.windowMixin],
  data() {
    return {
      paymentsWallet: {},
      cancel: {},
      users: [],
      wallets: [],
      searchData: {
        user: '',
        username: '',
        email: '',
        pubkey: ''
      },
      paymentPage: {
        show: false
      },
      activeWallet: {
        userId: null,
        show: false
      },
      activeUser: {
        data: null,
        showUserId: false,
        show: false
      },

      createWalletDialog: {
        data: {},
        show: false
      },
      walletTable: {
        columns: [
          {
            name: 'name',
            align: 'left',
            label: 'Name',
            field: 'name'
          },
          {
            name: 'id',
            align: 'left',
            label: 'Wallet Id',
            field: 'id'
          },
          {
            name: 'currency',
            align: 'left',
            label: 'Currency',
            field: 'currency'
          },
          {
            name: 'balance_msat',
            align: 'left',
            label: 'Balance',
            field: 'balance_msat'
          }
        ],
        pagination: {
          sortBy: 'name',
          rowsPerPage: 10,
          page: 1,
          descending: true,
          rowsNumber: 10
        },
        search: null,
        hideEmpty: true,
        loading: false
      },
      usersTable: {
        columns: [
          {
            name: 'admin',
            align: 'left',
            label: 'Admin',
            field: 'admin',
            sortable: false
          },
          {
            name: 'wallet_id',
            align: 'left',
            label: 'Wallets',
            field: 'wallet_id',
            sortable: false
          },
          {
            name: 'user',
            align: 'left',
            label: 'User Id',
            field: 'user',
            sortable: false
          },

          {
            name: 'username',
            align: 'left',
            label: 'Username',
            field: 'username',
            sortable: false
          },

          {
            name: 'email',
            align: 'left',
            label: 'Email',
            field: 'email',
            sortable: false
          },
          {
            name: 'pubkey',
            align: 'left',
            label: 'Public Key',
            field: 'pubkey',
            sortable: false
          },
          {
            name: 'balance_msat',
            align: 'left',
            label: 'Balance',
            field: 'balance_msat',
            sortable: true
          },

          {
            name: 'transaction_count',
            align: 'left',
            label: 'Payments',
            field: 'transaction_count',
            sortable: true
          },

          {
            name: 'last_payment',
            align: 'left',
            label: 'Last Payment',
            field: 'last_payment',
            sortable: true
          }
        ],
        pagination: {
          sortBy: 'balance_msat',
          rowsPerPage: 10,
          page: 1,
          descending: true,
          rowsNumber: 10
        },
        search: null,
        hideEmpty: true,
        loading: false
      }
    }
  },
  watch: {
    'usersTable.hideEmpty': function (newVal, _) {
      if (newVal) {
        this.usersTable.filter = {
          'transaction_count[gt]': 0
        }
      } else {
        this.usersTable.filter = {}
      }
      this.fetchUsers()
    }
  },
  created() {
    this.fetchUsers()
  },

  methods: {
    formatDate(date) {
      return LNbits.utils.formatDateString(date)
    },
    formatSat(value) {
      return LNbits.utils.formatSat(Math.floor(value / 1000))
    },
    backToUsersPage() {
      this.activeUser.show = false
      this.paymentPage.show = false
      this.activeWallet.show = false
      this.fetchUsers()
    },
    handleBalanceUpdate() {
      this.fetchWallets(this.activeWallet.userId)
    },
    resetPassword(user_id) {
      return LNbits.api
        .request('PUT', `/users/api/v1/user/${user_id}/reset_password`)
        .then(res => {
          LNbits.utils
            .confirmDialog(
              'A reset key has been generated. Click OK to copy the rest key to your clipboard.'
            )
            .onOk(() => {
              const url = window.location.origin + '?reset_key=' + res.data
              this.copyText(url)
            })
        })
        .catch(LNbits.utils.notifyApiError)
    },
    createUser() {
      LNbits.api
        .request('POST', '/users/api/v1/user', null, this.activeUser.data)
        .then(resp => {
          Quasar.Notify.create({
            type: 'positive',
            message: 'User created!',
            icon: null
          })

          this.activeUser.setPassword = true
          this.activeUser.data = resp.data
          this.fetchUsers()
        })
        .catch(LNbits.utils.notifyApiError)
    },
    updateUser() {
      LNbits.api
        .request(
          'PUT',
          `/users/api/v1/user/${this.activeUser.data.id}`,
          null,
          this.activeUser.data
        )
        .then(() => {
          Quasar.Notify.create({
            type: 'positive',
            message: 'User updated!',
            icon: null
          })
          this.activeUser.data = null
          this.activeUser.show = false
          this.fetchUsers()
        })
        .catch(LNbits.utils.notifyApiError)
    },
    createWallet() {
      const userId = this.activeWallet.userId
      if (!userId) {
        Quasar.Notify.create({
          type: 'warning',
          message: 'No user selected!',
          icon: null
        })
        return
      }
      LNbits.api
        .request(
          'POST',
          `/users/api/v1/user/${userId}/wallet`,
          null,
          this.createWalletDialog.data
        )
        .then(() => {
          this.fetchWallets(userId)
          Quasar.Notify.create({
            type: 'positive',
            message: 'Wallet created!'
          })
        })
        .catch(LNbits.utils.notifyApiError)
    },
    deleteUser(user_id) {
      LNbits.utils
        .confirmDialog('Are you sure you want to delete this user?')
        .onOk(() => {
          LNbits.api
            .request('DELETE', `/users/api/v1/user/${user_id}`)
            .then(() => {
              this.fetchUsers()
              Quasar.Notify.create({
                type: 'positive',
                message: 'User deleted!',
                icon: null
              })
              this.activeUser.data = null
              this.activeUser.show = false
            })
            .catch(LNbits.utils.notifyApiError)
        })
    },
    undeleteUserWallet(user_id, wallet) {
      LNbits.api
        .request(
          'PUT',
          `/users/api/v1/user/${user_id}/wallet/${wallet}/undelete`
        )
        .then(() => {
          this.fetchWallets(user_id)
          Quasar.Notify.create({
            type: 'positive',
            message: 'Undeleted user wallet!',
            icon: null
          })
        })
        .catch(LNbits.utils.notifyApiError)
    },
    deleteUserWallet(user_id, wallet, deleted) {
      const dialogText = deleted
        ? 'Wallet is already deleted, are you sure you want to permanently delete this user wallet?'
        : 'Are you sure you want to delete this user wallet?'
      LNbits.utils.confirmDialog(dialogText).onOk(() => {
        LNbits.api
          .request('DELETE', `/users/api/v1/user/${user_id}/wallet/${wallet}`)
          .then(() => {
            this.fetchWallets(user_id)
            Quasar.Notify.create({
              type: 'positive',
              message: 'User wallet deleted!',
              icon: null
            })
          })
          .catch(LNbits.utils.notifyApiError)
      })
    },
    copyWalletLink(walletId) {
      const url = `${window.location.origin}/wallet?usr=${this.activeWallet.userId}&wal=${walletId}`
      this.copyText(url)
    },

    fetchUsers(props) {
      const params = LNbits.utils.prepareFilterQuery(this.usersTable, props)
      LNbits.api
        .request('GET', `/users/api/v1/user?${params}`)
        .then(res => {
          this.usersTable.loading = false
          this.usersTable.pagination.rowsNumber = res.data.total
          this.users = res.data.data
        })
        .catch(LNbits.utils.notifyApiError)
    },
    fetchWallets(userId) {
      LNbits.api
        .request('GET', `/users/api/v1/user/${userId}/wallet`)
        .then(res => {
          this.wallets = res.data
          this.activeWallet.userId = userId
          this.activeWallet.show = true
        })
        .catch(LNbits.utils.notifyApiError)
    },

    toggleAdmin(userId) {
      LNbits.api
        .request('GET', `/users/api/v1/user/${userId}/admin`)
        .then(() => {
          this.fetchUsers()
          Quasar.Notify.create({
            type: 'positive',
            message: 'Toggled admin!',
            icon: null
          })
        })
        .catch(LNbits.utils.notifyApiError)
    },
    exportUsers() {
      console.log('export users')
    },
    async showAccountPage(user_id) {
      this.activeUser.showPassword = false
      this.activeUser.showUserId = false
      this.activeUser.setPassword = false
      if (!user_id) {
        this.activeUser.data = {extra: {}}
        this.activeUser.show = true
        return
      }
      try {
        const {data} = await LNbits.api.request(
          'GET',
          `/users/api/v1/user/${user_id}`
        )
        this.activeUser.data = data

        this.activeUser.show = true
      } catch (error) {
        console.warn(error)
        Quasar.Notify.create({
          type: 'warning',
          message: 'Failed to get user!'
        })
        this.activeUser.show = false
      }
    },
    showPayments(wallet_id) {
      this.paymentsWallet = this.wallets.find(wallet => wallet.id === wallet_id)
      this.paymentPage.show = true
    },
    searchUserBy(fieldName) {
      const fieldValue = this.searchData[fieldName]
      this.usersTable.filter = {}
      if (fieldValue) {
        this.usersTable.filter[fieldName] = fieldValue
      }

      this.fetchUsers()
    },
    shortify(value) {
      valueLength = (value || '').length
      if (valueLength <= 10) {
        return value
      }
      return `${value.substring(0, 5)}...${value.substring(valueLength - 5, valueLength)}`
    }
  }
}
