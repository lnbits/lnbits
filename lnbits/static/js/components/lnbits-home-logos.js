window.app.component('lnbits-home-logos', {
  template: '#lnbits-home-logos',
  mixins: [window.windowMixin],
  data() {
    return {
      logos: [
        {
          href: 'https://github.com/ElementsProject/lightning',
          lightSrc: '/static/images/clnl.png',
          darkSrc: '/static/images/cln.png'
        },
        {
          href: 'https://github.com/lightningnetwork/lnd',
          lightSrc: '/static/images/lnd.png',
          darkSrc: '/static/images/lnd.png'
        },
        {
          href: 'https://opennode.com',
          lightSrc: '/static/images/opennodel.png',
          darkSrc: '/static/images/opennode.png'
        },
        {
          href: 'https://lnpay.co/',
          lightSrc: '/static/images/lnpayl.png',
          darkSrc: '/static/images/lnpay.png'
        },
        {
          href: 'https://github.com/rootzoll/raspiblitz',
          lightSrc: '/static/images/blitzl.png',
          darkSrc: '/static/images/blitz.png'
        },
        {
          href: 'https://start9.com/',
          lightSrc: '/static/images/start9l.png',
          darkSrc: '/static/images/start9.png'
        },
        {
          href: 'https://getumbrel.com/',
          lightSrc: '/static/images/umbrell.png',
          darkSrc: '/static/images/umbrel.png'
        },
        {
          href: 'https://mynodebtc.com',
          lightSrc: '/static/images/mynodel.png',
          darkSrc: '/static/images/mynode.png'
        },
        {
          href: 'https://github.com/shesek/spark-wallet',
          lightSrc: '/static/images/sparkl.png',
          darkSrc: '/static/images/spark.png'
        },
        {
          href: 'https://voltage.cloud',
          lightSrc: '/static/images/voltagel.png',
          darkSrc: '/static/images/voltage.png'
        },
        {
          href: 'https://breez.technology/sdk/',
          lightSrc: '/static/images/breezl.png',
          darkSrc: '/static/images/breez.png'
        },
        {
          href: 'https://blockstream.com/lightning/greenlight/',
          lightSrc: '/static/images/greenlightl.png',
          darkSrc: '/static/images/greenlight.png'
        },
        {
          href: 'https://getalby.com',
          lightSrc: '/static/images/albyl.png',
          darkSrc: '/static/images/alby.png'
        },
        {
          href: 'https://zbd.gg',
          lightSrc: '/static/images/zbdl.png',
          darkSrc: '/static/images/zbd.png'
        },
        {
          href: 'https://phoenix.acinq.co/server',
          lightSrc: '/static/images/phoenixdl.png',
          darkSrc: '/static/images/phoenixd.png'
        },
        {
          href: 'https://boltz.exchange/',
          lightSrc: '/static/images/boltzl.svg',
          darkSrc: '/static/images/boltz.svg'
        },
        {
          href: 'https://www.blink.sv/',
          lightSrc: '/static/images/blink_logol.png',
          darkSrc: '/static/images/blink_logo.png'
        }
      ]
    }
  },
  computed: {
    showLogos() {
      return (
        this.g.isSatsDenomination &&
        this.SITE_TITLE == 'LNbits' &&
        this.LNBITS_SHOW_HOME_PAGE_ELEMENTS == true
      )
    }
  }
})
