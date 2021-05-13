new Vue({
    el: '#vue',
    mixins: [windowMixin],
    data: function () {
      return {
        form:{
          show:false,
          data:{}
        },
        table:{
          users:{
            columns:[
              { name: 'b1', align: 'left', label: '', field: ''},
              { name: 'id', align: 'left', label: 'ID', field: 'id', sortable: true},
              { name: 'credits', align: 'center', label: 'Credits', field: 'credits', sortable: true},
              { name: 'active', align: 'center', label: 'Active', field: 'active', sortable: true},
              { name: 'uid', align: 'left', label: 'User ID', field: 'uid', sortable: true},
              { name: 'wid', align: 'left', label: 'Wallet ID', field: 'wid', sortable: true },
            ],
            data:[]
          }
        }
      }
    },
    methods:{
      async sendFormData(auto){
        let payload, res
        auto
        ?(
          payload = {},
          res = (await LNbits.api.request('POST',`/winlose/api/v1/users?local=true`,this.g.user.wallets[0].inkey,
          payload)).data,
          res.success &&(
            this.$q.notify({
              timeout: 5000,
              type: 'positive',
              message: `User Created`,
              // caption: response.data.lnurl_response
            }),
            this.table.users.data.push(this.usersTableData([res.success])[0]),
            this.form.show = false, this.formReset()
          )
        )
        :(console.log(auto))
      },
      formReset(){
        this.form.data ={}
      },
      exportCSV(){},
      init(p){
        const action ={}
        action.loadUsers = async () =>{
            const {data} = await LNbits.api
            .request(
            'GET',
            `/winlose/api/v1/users?local=true`,
            this.g.user.wallets[0].inkey
        )
            return data
        }
        return action[p.func](p)
    },
    usersTableData(data){
      if(!data.length)return
      const evtsData = data.map(x=> ({
          id: x.id,
          uid: x.usr_id,
          wid: x.payout_wallet,
          credits: x.credits,
          active: x.active == 1 ? true : false
      }))
      return evtsData
      },
      async userActive(id){
        let item =  this.table.users.data.find(x=> x.id == id), change, res, payload={}
        change = !item.active
        item.active = change
        payload.id = id, payload.payload = change, payload.set = 'active'
        res = (await LNbits.api.request('PUT',`/winlose/api/v1/users`,this.g.user.wallets[0].inkey,
          payload)).data
        res.success &&  this.$q.notify({
          timeout: 5000,
          type: 'primary',
          message: res.success,
          // caption: response.data.lnurl_response
        })
      },
      async deleteUser(id){
        const {data} = await LNbits.api
          .request('DELETE',`/winlose/api/v1/users/${id}`,this.g.user.wallets[0].inkey)
        data.success &&(
          this.table.users.data = this.table.users.data.filter(x=> x.id !== id),
          this.$q.notify({
            timeout: 5000,
            type: 'primary',
            message: `User - ${data.success.id} successfully deleted!`,
            // caption: response.data.lnurl_response
          })
        )
      }
    },
    created: async function () {
      let users = await this.init({func:'loadUsers'})
      users.success && (this.table.users.data = this.usersTableData(users.success))
    }
  })