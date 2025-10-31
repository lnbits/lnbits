window.app.component('lnbits-admin-users', {
  props: ['form-data'],
  template: '#lnbits-admin-users',
  mixins: [window.windowMixin],
  data() {
    return {
      formAddUser: '',
      formAddAdmin: ''
    }
  },
  methods: {
    addAllowedUser() {
      let addUser = this.formAddUser
      let allowed_users = this.formData.lnbits_allowed_users
      if (addUser && addUser.length && !allowed_users.includes(addUser)) {
        this.formData.lnbits_allowed_users = [...allowed_users, addUser]
        this.formAddUser = ''
      }
    },
    removeAllowedUser(user) {
      let allowed_users = this.formData.lnbits_allowed_users
      this.formData.lnbits_allowed_users = allowed_users.filter(u => u !== user)
    },
    addAdminUser() {
      let addUser = this.formAddAdmin
      let admin_users = this.formData.lnbits_admin_users
      if (addUser && addUser.length && !admin_users.includes(addUser)) {
        this.formData.lnbits_admin_users = [...admin_users, addUser]
        this.formAddAdmin = ''
      }
    },
    removeAdminUser(user) {
      let admin_users = this.formData.lnbits_admin_users
      this.formData.lnbits_admin_users = admin_users.filter(u => u !== user)
    }
  }
})
