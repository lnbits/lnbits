/* globals Quasar, Vue, _, VueQrcode, windowMixin, LNbits, LOCALE */

Vue.component(VueQrcode.name, VueQrcode)

const pica = window.pica()

const defaultItemData = {
  unit: 'sat'
}

new Vue({
  el: '#vue',
  mixins: [windowMixin],
  data() {
    return {
      selectedWallet: null,
      offlineshop: {
        wordlist: [],
        items: []
      },
      itemDialog: {
        show: false,
        data: {...defaultItemData},
        units: ['sat', 'USD']
      }
    }
  },
  methods: {
    async imageAdded(file) {
      let image = new Image()
      image.src = URL.createObjectURL(file)
      let canvas = document.getElementById('uploading-image')
      image.onload = async () => {
        canvas.setAttribute('width', 300)
        canvas.setAttribute('height', 300)
        await pica.resize(image, canvas)
        this.itemDialog.data.image = canvas.toDataURL()
      }
    },
    imageCleared() {
      this.itemDialog.data.image = null
      let canvas = document.getElementById('uploading-image')
      canvas.setAttribute('height', 0)
      canvas.setAttribute('width', 0)
      let ctx = canvas.getContext('2d')
      ctx.clearRect(0, 0, canvas.width, canvas.height)
    },
    disabledAddItemButton() {
      return (
        !this.itemDialog.data.name ||
        this.itemDialog.data.name.length === 0 ||
        !this.itemDialog.data.price ||
        !this.itemDialog.data.description ||
        !this.itemDialog.data.unit ||
        this.itemDialog.data.unit.length === 0
      )
    },
    changedWallet(wallet) {
      this.selectedWallet = wallet
      this.loadShop()
    },
    loadShop() {
      LNbits.api
        .request(
          'GET',
          '/offlineshop/api/v1/offlineshop',
          this.selectedWallet.inkey
        )
        .then(response => {
          this.offlineshop = response.data
        })
        .catch(err => {
          LNbits.utils.notifyApiError(err)
        })
    },
    addItem() {
      let {name, image, description, price, unit} = this.itemDialog.data

      LNbits.api
        .request(
          'POST',
          '/offlineshop/api/v1/offlineshop/items',
          this.selectedWallet.inkey,
          {
            name,
            description,
            image,
            price,
            unit
          }
        )
        .then(response => {
          this.$q.notify({
            message: `Item '${this.itemDialog.data.name}' added.`,
            timeout: 700
          })
          this.loadShop()
          this.itemsDialog.show = false
          this.itemsDialog.data = {...defaultItemData}
        })
        .catch(err => {
          LNbits.utils.notifyApiError(err)
        })
    },
    toggleItem(itemId) {
      let item = this.offlineshop.items.find(item => item.id === itemId)
      item.enabled = !item.enabled

      LNbits.api
        .request(
          'PUT',
          '/offlineshop/api/v1/offlineshop/items/' + itemId,
          this.selectedWallet.inkey,
          item
        )
        .then(response => {
          this.$q.notify({
            message: `Item ${item.enabled ? 'enabled' : 'disabled'}.`,
            timeout: 700
          })
          this.offlineshop.items = this.offlineshop.items
        })
        .catch(err => {
          LNbits.utils.notifyApiError(err)
        })
    },
    deleteItem(itemId) {
      LNbits.utils
        .confirmDialog('Are you sure you want to delete this item?')
        .onOk(() => {
          LNbits.api
            .request(
              'DELETE',
              '/offlineshop/api/v1/offlineshop/items/' + itemId,
              this.selectedWallet.inkey
            )
            .then(response => {
              this.$q.notify({
                message: `Item deleted.`,
                timeout: 700
              })
              this.offlineshop.items.splice(
                this.offlineshop.items.findIndex(item => item.id === itemId),
                1
              )
            })
            .catch(err => {
              LNbits.utils.notifyApiError(err)
            })
        })
    }
  },
  created() {
    this.selectedWallet = this.g.user.wallets[0]
    this.loadShop()
  }
})
