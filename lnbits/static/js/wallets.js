window.WalletsPageLogic = {
  mixins: [window.windowMixin],
  data() {
    return {
      user: null,
      tab: 'wallets',
      wallets: [],
      walletsTable: {
        columns: [
          {
            name: 'name',
            align: 'left',
            label: 'Name',
            field: 'name',
            sortable: true
          },
          {
            name: 'currency',
            align: 'left',
            label: 'Currency',
            field: 'currency',
            sortable: true
          },
          {
            name: 'balance_msat',
            align: 'left',
            label: 'Balance',
            field: 'balance_msat',
            sortable: false
          },
          {
            name: 'id',
            align: 'left',
            label: 'Id',
            field: 'id',
            sortable: true
          }
        ],
        pagination: {
          sortBy: 'updated_at',
          rowsPerPage: 12,
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
  methods: {
    async updateAccount() {
      try {
        const {data} = await LNbits.api.request(
          'PUT',
          '/api/v1/auth/update',
          null,
          {
            user_id: this.user.id,
            username: this.user.username,
            email: this.user.email,
            extra: this.user.extra
          }
        )
        this.user = data
        this.hasUsername = !!data.username
        Quasar.Notify.create({
          type: 'positive',
          message: 'Account updated.'
        })
      } catch (e) {
        LNbits.utils.notifyApiError(e)
      }
    },

    async getUserWallets(props) {
      try {
        this.walletsTable.loading = true
        const params = LNbits.utils.prepareFilterQuery(this.walletsTable, props)
        const {data} = await LNbits.api.request(
          'GET',
          `/api/v1/wallet/paginated?${params}`,
          null
        )
        console.log('### data', data)
        console.log('### total', data.total)
        this.wallets = data.data
        this.walletsTable.pagination.rowsNumber = data.total
      } catch (e) {
        LNbits.utils.notifyApiError(e)
      } finally {
        this.walletsTable.loading = false
      }
    },

    async addApiACL() {
      if (!this.apiAcl.newAclName) {
        this.$q.notify({
          type: 'warning',
          message: 'Name is required.'
        })
        return
      }

      try {
        const {data} = await LNbits.api.request(
          'PUT',
          '/api/v1/auth/acl',
          null,
          {
            id: this.apiAcl.newAclName,
            name: this.apiAcl.newAclName,
            password: this.apiAcl.password
          }
        )
        this.apiAcl.data = data.access_control_list
        const acl = this.apiAcl.data.find(
          t => t.name === this.apiAcl.newAclName
        )

        this.handleApiACLSelected(acl.id)
        this.apiAcl.showNewAclDialog = false
        this.$q.notify({
          type: 'positive',
          message: 'Access Control List created.'
        })
      } catch (e) {
        LNbits.utils.notifyApiError(e)
      } finally {
        this.apiAcl.name = ''
        this.apiAcl.password = ''
      }

      this.apiAcl.showNewAclDialog = false
    }
  },
  async created() {
    await this.getUserWallets()
  }
}
