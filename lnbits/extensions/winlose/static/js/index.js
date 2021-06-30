new Vue({
  el: '#vue',
  mixins: [windowMixin],
  data: function () {
    return {
      form: {
        show: false,
        data: {},
        settings: false
      },
      table: {
        users: {
          columns: [
            {name: 'b1', align: 'left', label: '', field: ''},
            {
              name: 'id',
              align: 'left',
              label: 'ID',
              field: 'id',
              sortable: true
            },
            {
              name: 'credits',
              align: 'center',
              label: 'Credits',
              field: 'credits',
              sortable: true
            },
            {
              name: 'active',
              align: 'center',
              label: 'Active',
              field: 'active',
              sortable: true
            },
            {
              name: 'uid',
              align: 'left',
              label: 'User ID',
              field: 'uid',
              sortable: true
            },
            {
              name: 'wid',
              align: 'left',
              label: 'Wallet ID',
              field: 'wid',
              sortable: true
            }
          ],
          data: [],
          visibleColumns: ['b1', 'id', 'credits', 'active']
        },
        logs: {
          columns: [
            {
              name: 'usr',
              align: 'left',
              label: 'User',
              field: 'usr',
              sortable: true
            },
            {
              name: 'wl',
              align: 'left',
              label: 'Win/Lose',
              field: 'wl',
              sortable: true
            },
            {
              name: 'credits',
              align: 'center',
              label: 'Credits',
              field: 'credits',
              sortable: true
            },
            {
              name: 'sats',
              align: 'center',
              label: 'Sats',
              field: 'sats',
              sortable: true
            },
            {
              name: 'multi',
              align: 'center',
              label: 'Multi',
              field: 'multi',
              sortable: true
            },
            {
              name: 'cmd',
              align: 'left',
              label: 'Command',
              field: 'cmd',
              sortable: true
            },
            {
              name: 'time',
              align: 'left',
              label: 'Time',
              field: 'time',
              sortable: true
            }
          ],
          data: [],
          visibleColumns: ['wl', 'credits', 'sats', 'multi', 'cmd', 'time'],
          limit: ''
        }
      },
      user: {
        wl: [],
        show: false,
        data: {},
        settings: {
          data: {}
        }
      },
      api: {
        base_url: location.origin
      }
    }
  },
  methods: {
    async sendFormData(auto) {
      if (!this.user.settings.data.hasOwnProperty('data'))
        return this.$q.notify({
          timeout: 5000,
          type: 'negative',
          message: 'Settings are required before creating an account'
        })
      let payload, res
      auto
        ? ((payload = {}),
          this.form.data.id && (payload.id = this.form.data.id),
          (res = (
            await LNbits.api.request(
              'POST',
              `/winlose/api/v1/users?local=true`,
              this.g.user.wallets[0].inkey,
              payload
            )
          ).data),
          res.success &&
            (this.$q.notify({
              timeout: 5000,
              type: 'positive',
              message: `User Created`
              // caption: response.data.lnurl_response
            }),
            this.table.users.data.push(this.usersTableData([res.success])[0]),
            (this.form.show = false),
            this.formReset()))
        : ((payload = {...this.form.data}),
          (payload.auto = false),
          (res = (
            await LNbits.api.request(
              'POST',
              `/winlose/api/v1/users?local=true`,
              this.g.user.wallets[0].inkey,
              payload
            )
          ).data),
          res.success &&
            (this.$q.notify({
              timeout: 5000,
              type: 'positive',
              message: `User Created`
              // caption: response.data.lnurl_response
            }),
            this.table.users.data.push(this.usersTableData([res.success])[0]),
            (this.form.show = false),
            this.formReset()))
    },
    async sendSettingsForm() {
      const payload = {...this.form.data}
      const res = (
        await LNbits.api.request(
          'POST',
          `/winlose/api/v1/settings`,
          this.g.user.wallets[0].inkey,
          payload
        )
      ).data
      res.success &&
        (this.$q.notify({
          timeout: 5000,
          type: 'positive',
          message: 'User settings updated'
          // caption: response.data.lnurl_response
        }),
        (this.form.settings = false),
        (this.user.settings.data = res.success))
    },
    async logsLimit(id) {
      const limit = !this.table.logs.limit
        ? ''
        : `&limit=${this.table.logs.limit}`
      const {data} = await LNbits.api.request(
        'GET',
        `/winlose/api/v1/users?local=true&id=${id}&logs=true${limit}`,
        this.g.user.wallets[0].inkey
      )
      data.success &&
        ((this.table.logs.data = this.logsTableData(data.success.logs)),
        (this.table.logs.limit = ''))
    },
    showSettingsForm() {
      this.form.data = this.user.settings.data
      this.form.settings = true
    },
    formReset() {
      this.form.data = {}
    },
    exportCSV(table) {
      table == 'users' &&
        LNbits.utils.exportCSV(
          this.table.users.columns.filter((x, i) => i > 0),
          this.table.users.data
        )

      table == 'logs' &&
        LNbits.utils.exportCSV(this.table.logs.columns, this.table.logs.data)
    },
    init(p) {
      const action = {}
      action.loadUsers = async () => {
        const {data} = await LNbits.api.request(
          'GET',
          `/winlose/api/v1/users?local=true`,
          this.g.user.wallets[0].inkey
        )
        return data
      }
      action.loadSettings = async () => {
        const {data} = await LNbits.api.request(
          'GET',
          `/winlose/api/v1/settings`,
          this.g.user.wallets[0].inkey
        )
        return data
      }
      return action[p.func](p)
    },
    usersTableData(data) {
      if (!data.length) return
      const evtsData = data.map(x => ({
        id: x.id,
        uid: x.usr_id,
        wid: x.payout_wallet,
        credits: x.credits,
        active: x.active == 1 ? true : false
      }))
      return evtsData
    },
    logsTableData(data) {
      if (!data.length) return
      const logsData = data.map(x => ({
        id: x.id,
        usr: x.usr,
        wl: x.wl,
        credits: x.credits,
        sats: x.sats,
        multi: x.multi,
        cmd: x.cmd,
        time: moment(x.time * 1000).format('llll')
      }))
      return logsData
    },
    async showUserInfo(id) {
      this.user.show = true
      this.user.data = this.table.users.data.find(x => x.id == id)
      const {data} = await LNbits.api.request(
        'GET',
        `/winlose/api/v1/users?local=true&id=${id}&logs=true`,
        this.g.user.wallets[0].inkey
      )
      data.success &&
        ((this.table.logs.data = this.logsTableData(data.success.logs)),
        (this.user.data.balance = LNbits.utils.formatSat(
          data.success.usr.balance
        )),
        (this.user.data.credits = data.success.usr.credits),
        (this.user.data.id = id))
    },
    async userActive(id) {
      let item = this.table.users.data.find(x => x.id == id),
        change,
        res,
        payload = {}
      change = !item.active
      item.active = change
      ;(payload.id = id), (payload.payload = change), (payload.set = 'active')
      res = (
        await LNbits.api.request(
          'PUT',
          `/winlose/api/v1/users`,
          this.g.user.wallets[0].inkey,
          payload
        )
      ).data
      res.success &&
        this.$q.notify({
          timeout: 5000,
          type: 'primary',
          message: res.success
          // caption: response.data.lnurl_response
        })
    },
    async deleteUser(id) {
      const wlonly = this.user.wl[0] ? '?wl_only=true' : ''
      const {data} = await LNbits.api.request(
        'DELETE',
        `/winlose/api/v1/users/${id}${wlonly}`,
        this.g.user.wallets[0].adminkey
      )
      data.success &&
        ((this.table.users.data = this.table.users.data.filter(
          x => x.id !== id
        )),
        this.$q.notify({
          timeout: 5000,
          type: 'primary',
          message: `User - ${data.success.id} successfully deleted!`
          // caption: response.data.lnurl_response
        }))
    },
    confirm(p) {
      if (p.check) {
        this.user.wl = []
        this.$q
          .dialog({
            title: p.title || 'Confirm',
            message: p.msg || 'Would you like to continue?',
            options: {
              type: 'checkbox',
              model: this.user.wl,
              // inline: true
              items: [
                {label: 'WinLose Only', value: true, color: 'deep-purple'}
              ]
            },
            cancel: true,
            persistent: true
          })
          .onOk(data => {
            p?.ok == 'deleteUser' &&
              ((this.user.wl = !data.length ? [false] : data),
              this.deleteUser(p.id))
          })
          .onCancel(() => {})
          .onDismiss(() => {})
      } else {
        this.$q
          .dialog({
            title: p.title || 'Confirm',
            message: p.msg || 'Would you like to continue?',
            cancel: true,
            persistent: true
          })
          .onOk(() => {
            p?.ok == '' && this.deleteUser(p.id)
          })
          .onCancel(() => {})
          .onDismiss(() => {})
      }
    },
    checkForm() {
      let choice = true
      this.form.data.uid !== null ||
        (this.form.data.uid !== '' && (choice = false))
      this.form.data.wid !== null ||
        (this.form.data.wid !== '' && (choice = false))
      return choice
    }
  },
  created: async function () {
    let users = await this.init({func: 'loadUsers'})
    users.success &&
      (this.table.users.data = this.usersTableData(users.success.usr))
    let settings = await this.init({func: 'loadSettings'})
    settings.success && (this.user.settings.data = settings.success)
  }
})
