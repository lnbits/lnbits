window.app.component('lnbits-admin-site-customisation', {
  props: ['form-data'],
  template: '#lnbits-admin-site-customisation',
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
  methods: {
    onBackgroundImageInput(e) {
      const file = e.target.files[0]
      if (file) {
        this.uploadBackgroundImage(file)
      }
      e.target.value = null
    },
    async uploadBackgroundImage(file) {
      const formData = new FormData()
      formData.append('file', file)
      try {
        const {data} = await LNbits.api.request(
          'POST',
          '/api/v1/assets?public_asset=true',
          null,
          formData,
          {
            headers: {'Content-Type': 'multipart/form-data'}
          }
        )
        const assetUrl = `${window.location.origin}/api/v1/assets/${data.id}/thumbnail`
        this.formData.lnbits_default_bgimage = assetUrl
        Quasar.Notify.create({
          type: 'positive',
          message: 'Background image uploaded.',
          icon: null
        })
      } catch (e) {
        LNbits.utils.notifyApiError(e)
      }
    }
  }
})
