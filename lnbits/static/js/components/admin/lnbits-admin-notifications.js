window.app.component('lnbits-admin-notifications', {
  props: ['form-data'],
  template: '#lnbits-admin-notifications',
  mixins: [window.windowMixin],
  data() {
    return {
      nostrNotificationIdentifier: '',
      emailNotificationAddress: ''
    }
  },
  methods: {
    sendTestEmail() {
      LNbits.api
        .request(
          'GET',
          '/admin/api/v1/testemail',
          this.g.user.wallets[0].adminkey
        )
        .then(response => {
          if (response.data.status === 'error') {
            throw new Error(response.data.message)
          }
          this.$q.notify({
            message: 'Test email sent!',
            color: 'positive'
          })
        })
        .catch(error => {
          this.$q.notify({
            message: error.message,
            color: 'negative'
          })
        })
    },
    addNostrNotificationIdentifier() {
      const identifer = this.nostrNotificationIdentifier.trim()
      const identifiers = this.formData.lnbits_nostr_notifications_identifiers
      if (identifer && identifer.length && !identifiers.includes(identifer)) {
        this.formData.lnbits_nostr_notifications_identifiers = [
          ...identifiers,
          identifer
        ]
        this.nostrNotificationIdentifier = ''
      }
    },
    removeNostrNotificationIdentifier(identifer) {
      const identifiers = this.formData.lnbits_nostr_notifications_identifiers
      this.formData.lnbits_nostr_notifications_identifiers = identifiers.filter(
        m => m !== identifer
      )
    },
    addEmailNotificationAddress() {
      const email = this.emailNotificationAddress.trim()
      const emails = this.formData.lnbits_email_notifications_to_emails
      if (email && email.length && !emails.includes(email)) {
        this.formData.lnbits_email_notifications_to_emails = [...emails, email]
        this.emailNotificationAddress = ''
      }
    },
    removeEmailNotificationAddress(email) {
      const emails = this.formData.lnbits_email_notifications_to_emails
      this.formData.lnbits_email_notifications_to_emails = emails.filter(
        m => m !== email
      )
    }
  }
})
