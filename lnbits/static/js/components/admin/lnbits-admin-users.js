window.app.component('lnbits-admin-users', {
  props: ['form-data'],
  template: '#lnbits-admin-users',
  data() {
    return {
      formAddUser: '',
      formAddAdmin: '',
      formAddActivationCode: '',
      showReusableActivationCode: false
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
    },
    addOneTimeActivationCode() {
      const code = this.formAddActivationCode
      const activationCodes =
        this.formData.lnbits_register_one_time_activation_codes
      if (code?.length && !activationCodes.includes(code)) {
        this.formData.lnbits_register_one_time_activation_codes = [
          ...activationCodes,
          code
        ]
        this.formAddActivationCode = ''
      }
    },
    removeOneTimeActivationCode(code) {
      const codes = this.formData.lnbits_register_one_time_activation_codes
      this.formData.lnbits_register_one_time_activation_codes = codes.filter(
        u => u !== code
      )
    }
  }
})
