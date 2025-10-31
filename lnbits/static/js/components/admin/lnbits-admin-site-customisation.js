window.app.component('lnbits-admin-site-customisation', {
  props: ['form-data'],
  template: '#lnbits-admin-site-customisation',
  mixins: [window.windowMixin],
  data() {
    return {
      lnbits_theme_options: [
        'classic',
        'bitcoin',
        'flamingo',
        'cyber',
        'freedom',
        'mint',
        'autumn',
        'monochrome',
        'salvador'
      ],
      colors: [
        'primary',
        'secondary',
        'accent',
        'positive',
        'negative',
        'info',
        'warning',
        'red',
        'yellow',
        'orange'
      ],
      reactionOptions: [
        'none',
        'confettiBothSides',
        'confettiFireworks',
        'confettiStars',
        'confettiTop'
      ],
      globalBorderOptions: [
        'retro-border',
        'hard-border',
        'neon-border',
        'no-border'
      ]
    }
  },
  methods: {}
})
