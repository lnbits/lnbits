window.app.component('lnbits-admin-library', {
  props: ['form-data'],
  template: '#lnbits-admin-library',
  mixins: [window.windowMixin],
  data() {
    return {
      library_images: []
    }
  },
  async created() {
    await this.getUploadedImages()
  },
  methods: {
    onImageInput(e) {
      const file = e.target.files[0]
      if (file) {
        this.uploadImage(file)
      }
    },
    uploadImage(file) {
      const formData = new FormData()
      formData.append('file', file)
      LNbits.api
        .request(
          'POST',
          '/admin/api/v1/images',
          this.g.user.wallets[0].adminkey,
          formData,
          {headers: {'Content-Type': 'multipart/form-data'}}
        )
        .then(() => {
          this.$q.notify({
            type: 'positive',
            message: 'Image uploaded!',
            icon: null
          })
          this.getUploadedImages()
        })
        .catch(LNbits.utils.notifyApiError)
    },
    getUploadedImages() {
      LNbits.api
        .request('GET', '/admin/api/v1/images', this.g.user.wallets[0].inkey)
        .then(response => {
          this.library_images = response.data.map(image => ({
            ...image,
            url: `${window.origin}/${image.directory}/${image.filename}`
          }))
        })
        .catch(LNbits.utils.notifyApiError)
    },
    deleteImage(filename) {
      LNbits.utils
        .confirmDialog('Are you sure you want to delete this image?')
        .onOk(() => {
          LNbits.api
            .request(
              'DELETE',
              `/admin/api/v1/images/${filename}`,
              this.g.user.wallets[0].adminkey
            )
            .then(() => {
              this.$q.notify({
                type: 'positive',
                message: 'Image deleted!',
                icon: null
              })
              this.getUploadedImages()
            })
            .catch(LNbits.utils.notifyApiError)
        })
    }
  }
})
