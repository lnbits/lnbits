window.app.component('lnbits-admin-security', {
  props: ['form-data'],
  template: '#lnbits-admin-security',
  mixins: [window.windowMixin],
  data() {
    return {
      logs: [],
      formBlockedIPs: '',
      serverlogEnabled: false,
      nostrAcceptedUrl: '',
      formAllowedIPs: '',
      formCallbackUrlRule: ''
    }
  },
  created() {},
  methods: {
    addAllowedIPs() {
      const allowedIPs = this.formAllowedIPs.trim()
      const allowed_ips = this.formData.lnbits_allowed_ips
      if (
        allowedIPs &&
        allowedIPs.length &&
        !allowed_ips.includes(allowedIPs)
      ) {
        this.formData.lnbits_allowed_ips = [...allowed_ips, allowedIPs]
        this.formAllowedIPs = ''
      }
    },
    removeAllowedIPs(allowed_ip) {
      const allowed_ips = this.formData.lnbits_allowed_ips
      this.formData.lnbits_allowed_ips = allowed_ips.filter(
        a => a !== allowed_ip
      )
    },
    addBlockedIPs() {
      const blockedIPs = this.formBlockedIPs.trim()
      const blocked_ips = this.formData.lnbits_blocked_ips
      if (
        blockedIPs &&
        blockedIPs.length &&
        !blocked_ips.includes(blockedIPs)
      ) {
        this.formData.lnbits_blocked_ips = [...blocked_ips, blockedIPs]
        this.formBlockedIPs = ''
      }
    },
    removeBlockedIPs(blocked_ip) {
      const blocked_ips = this.formData.lnbits_blocked_ips
      this.formData.lnbits_blocked_ips = blocked_ips.filter(
        b => b !== blocked_ip
      )
    },
    addCallbackUrlRule() {
      const allowedCallback = this.formCallbackUrlRule.trim()
      const allowedCallbacks = this.formData.lnbits_callback_url_rules
      if (
        allowedCallback &&
        allowedCallback.length &&
        !allowedCallbacks.includes(allowedCallback)
      ) {
        this.formData.lnbits_callback_url_rules = [
          ...allowedCallbacks,
          allowedCallback
        ]
        this.formCallbackUrlRule = ''
      }
    },
    removeCallbackUrlRule(allowedCallback) {
      const allowedCallbacks = this.formData.lnbits_callback_url_rules
      this.formData.lnbits_callback_url_rules = allowedCallbacks.filter(
        a => a !== allowedCallback
      )
    },
    addNostrUrl() {
      const url = this.nostrAcceptedUrl.trim()
      this.removeNostrUrl(url)
      this.formData.nostr_absolute_request_urls.push(url)
      this.nostrAcceptedUrl = ''
    },
    removeNostrUrl(url) {
      this.formData.nostr_absolute_request_urls =
        this.formData.nostr_absolute_request_urls.filter(b => b !== url)
    },
    async toggleServerLog() {
      this.serverlogEnabled = !this.serverlogEnabled
      if (this.serverlogEnabled) {
        const wsProto = location.protocol !== 'http:' ? 'wss://' : 'ws://'
        const digestHex = await LNbits.utils.digestMessage(this.g.user.id)
        const localUrl =
          wsProto +
          document.domain +
          ':' +
          location.port +
          '/api/v1/ws/' +
          digestHex
        this.ws = new WebSocket(localUrl)
        this.ws.addEventListener('message', async ({data}) => {
          this.logs.push(data.toString())
          const scrollArea = this.$refs.logScroll
          if (scrollArea) {
            const scrollTarget = scrollArea.getScrollTarget()
            const duration = 0
            scrollArea.setScrollPosition(scrollTarget.scrollHeight, duration)
          }
        })
      } else {
        this.ws.close()
      }
    }
  }
})
