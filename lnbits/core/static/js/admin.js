new Vue({
	el: '#vue',
	mixins: [windowMixin],
	data: function () {
		return {
			disclaimerDialog: {
				show: false,
				data: {}
			},
			walletName: '',
			primaryColor: '#FF00FF',
			secondColor: '#027be3',
			multiple: null,

			options: [
				'lnurlw (mint LNURL withdraws) ',
				'lnurlp (mint LNURL pays)',
				'usermanager (API for managing users/wallets)',
				'events (manage payments & registration for an event)',
				'lndhub (link LNbits wallet to Zeus or BlueWallet)',
				'lntickets (pay per words support ticket system)',
				'paywall (paywall content)',
				'tpos (quick, shareable point of sale terminal)',
				'amilk (lnurl milker *warning extremely resource heavy)'
			]
		}
	},
	methods: {
		createWallet: function () {
			LNbits.href.createWallet(this.walletName)
		},
		processing: function () {
			this.$q.notify({
				timeout: 0,
				message: 'Processing...',
				icon: null
			})
		}
	}
})
