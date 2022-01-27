/* globals Quasar, Vue, _, VueQrcode, windowMixin, LNbits, LOCALE */

Vue.component(VueQrcode.name, VueQrcode)

const pica = window.pica()

new Vue({
  el: '#vue',
  mixins: [windowMixin],
  data: function () {
    return {
      products: [],
      orders: [],
      stalls: [],
      zones: [],
      shippedModel: false,
      shippingZoneOptions: [
        'Australia',
        'Austria',
        'Belgium',
        'Brazil',
        'Canada',
        'Denmark',
        'Finland',
        'France*',
        'Germany',
        'Greece',
        'Hong Kong',
        'Hungary',
        'Ireland',
        'Indonesia',
        'Israel',
        'Italy',
        'Japan',
        'Kazakhstan',
        'Korea',
        'Luxembourg',
        'Malaysia',
        'Mexico',
        'Netherlands',
        'New Zealand',
        'Norway',
        'Poland',
        'Portugal',
        'Russia',
        'Saudi Arabia',
        'Singapore',
        'Spain',
        'Sweden',
        'Switzerland',
        'Thailand',
        'Turkey',
        'Ukraine',
        'United Kingdom**',
        'United States***',
        'Vietnam',
        'China'
      ],
      categories: [
        'Fashion (clothing and accessories)',
        'Health (and beauty)',
        'Toys (and baby equipment)',
        'Media (Books and CDs)',
        'Groceries (Food and Drink)',
        'Technology (Phones and Computers)',
        'Home (furniture and accessories)',
        'Gifts (flowers, cards, etc)'
      ],
      relayOptions: [
        'wss://nostr-relay.herokuapp.com/ws',
        'wss://nostr-relay.bigsun.xyz/ws',
        'wss://freedom-relay.herokuapp.com/ws'
      ],
      label: '',
      ordersTable: {
        columns: [
          {
            name: 'product',
            align: 'left',
            label: 'Product',
            field: 'product'
          },
          {
            name: 'quantity',
            align: 'left',
            label: 'Quantity',
            field: 'quantity'
          },
          {
            name: 'address',
            align: 'left',
            label: 'Address',
            field: 'address'
          },
          {
            name: 'invoiceid',
            align: 'left',
            label: 'InvoiceID',
            field: 'invoiceid'
          },
          {name: 'paid', align: 'left', label: 'Paid', field: 'paid'},
          {name: 'shipped', align: 'left', label: 'Shipped', field: 'shipped'}
        ],
        pagination: {
          rowsPerPage: 10
        }
      },
      productsTable: {
        columns: [
          {
            name: 'stall',
            align: 'left',
            label: 'Stall',
            field: 'stall'
          },
          {
            name: 'product',
            align: 'left',
            label: 'Product',
            field: 'product'
          },
          {
            name: 'description',
            align: 'left',
            label: 'Description',
            field: 'description'
          },
          {
            name: 'categories',
            align: 'left',
            label: 'Categories',
            field: 'categories'
          },
          {name: 'price', align: 'left', label: 'Price', field: 'price'},
          {
            name: 'quantity',
            align: 'left',
            label: 'Quantity',
            field: 'quantity'
          },
          {name: 'id', align: 'left', label: 'ID', field: 'id'}
        ],
        pagination: {
          rowsPerPage: 10
        }
      },
      stallTable: {
        columns: [
          {
            name: 'id',
            align: 'left',
            label: 'ID',
            field: 'id'
          },
          {
            name: 'name',
            align: 'left',
            label: 'Name',
            field: 'name'
          },
          {
            name: 'wallet',
            align: 'left',
            label: 'Wallet',
            field: 'wallet'
          },
          {
            name: 'publickey',
            align: 'left',
            label: 'Public key',
            field: 'publickey'
          },
          {
            name: 'privatekey',
            align: 'left',
            label: 'Private key',
            field: 'privatekey'
          }
        ],
        pagination: {
          rowsPerPage: 10
        }
      },
      zonesTable: {
        columns: [
          {
            name: 'id',
            align: 'left',
            label: 'ID',
            field: 'id'
          },
          {
            name: 'countries',
            align: 'left',
            label: 'Countries',
            field: 'countries'
          },
          {
            name: 'cost',
            align: 'left',
            label: 'Cost',
            field: 'cost'
          }
        ],
        pagination: {
          rowsPerPage: 10
        }
      },
      productDialog: {
        show: false,
        data: {}
      },
      stallDialog: {
        show: false,
        data: {}
      },
      zoneDialog: {
        show: false,
        data: {}
      },
      shopDialog: {
        show: false,
        data: {activate: false}
      },
      orderDialog: {
        show: false,
        data: {}
      },
      relayDialog: {
        show: false,
        data: {}
      }
    }
  },
  computed: {
    categoryOther: function () {
      cats = trim(this.productDialog.data.categories.split(','))
      for (let i = 0; i < cats.length; i++) {
        if (cats[i] == 'Others') {
          return true
        }
      }
      return false
    }
  },
  methods: {
    ////////////////////////////////////////
    ////////////////STALLS//////////////////
    ////////////////////////////////////////
    getStalls: function () {
      var self = this
      LNbits.api
        .request(
          'GET',
          '/diagonalley/api/v1/stalls?all_wallets',
          this.g.user.wallets[0].inkey
        )
        .then(function (response) {
          self.stalls = response.data.map(function (obj) {
            console.log(obj)
            return mapDiagonAlley(obj)
          })
        })
    },
    openStallUpdateDialog: function (linkId) {
      var self = this
      var link = _.findWhere(self.stalls, {id: linkId})

      this.stallDialog.data = _.clone(link._data)
      this.stallDialog.show = true
    },
    sendStallFormData: function () {
      if (this.stallDialog.data.id) {
      } else {
        var data = {
          name: this.stallDialog.data.name,
          wallet: this.stallDialog.data.wallet,
          publickey: this.stallDialog.data.publickey,
          privatekey: this.stallDialog.data.privatekey,
          relays: this.stallDialog.data.relays
        }
      }

      if (this.stallDialog.data.id) {
        this.updateStall(this.stallDialog.data)
      } else {
        this.createStall(data)
      }
    },
    updateStall: function (data) {
      var self = this
      LNbits.api
        .request(
          'PUT',
          '/diagonalley/api/v1/stalls' + data.id,
          _.findWhere(self.g.user.wallets, {
            id: self.stallDialog.data.wallet
          }).inkey,
          _.pick(data, 'name', 'wallet', 'publickey', 'privatekey')
        )
        .then(function (response) {
          self.stalls = _.reject(self.stalls, function (obj) {
            return obj.id == data.id
          })
          self.stalls.push(mapDiagonAlley(response.data))
          self.stallDialog.show = false
          self.stallDialog.data = {}
          data = {}
        })
        .catch(function (error) {
          LNbits.utils.notifyApiError(error)
        })
    },
    createStall: function (data) {
      var self = this
      LNbits.api
        .request(
          'POST',
          '/diagonalley/api/v1/stalls',
          _.findWhere(self.g.user.wallets, {
            id: self.stallDialog.data.wallet
          }).inkey,
          data
        )
        .then(function (response) {
          self.stalls.push(mapDiagonAlley(response.data))
          self.stallDialog.show = false
          self.stallDialog.data = {}
          data = {}
        })
        .catch(function (error) {
          LNbits.utils.notifyApiError(error)
        })
    },
    deleteStall: function (stallId) {
      var self = this
      var stall = _.findWhere(self.stalls, {id: stallId})

      LNbits.utils
        .confirmDialog('Are you sure you want to delete this Stall link?')
        .onOk(function () {
          LNbits.api
            .request(
              'DELETE',
              '/diagonalley/api/v1/stalls/' + stallId,
              _.findWhere(self.g.user.wallets, {id: stall.wallet}).inkey
            )
            .then(function (response) {
              self.stalls = _.reject(self.stalls, function (obj) {
                return obj.id == stallId
              })
            })
            .catch(function (error) {
              LNbits.utils.notifyApiError(error)
            })
        })
    },
    exportStallsCSV: function () {
      LNbits.utils.exportCSV(this.stallsTable.columns, this.stalls)
    },
    ////////////////////////////////////////
    ///////////////PRODUCTS/////////////////
    ////////////////////////////////////////
    getProducts: function () {
      var self = this

      LNbits.api
        .request(
          'GET',
          '/diagonalley/api/v1/products?all_stalls',
          this.g.user.wallets[0].inkey
        )
        .then(function (response) {
          self.products = response.data.map(function (obj) {
            return mapDiagonAlley(obj)
          })
        })
    },
    openProductUpdateDialog: function (linkId) {
      var self = this
      var link = _.findWhere(self.products, {id: linkId})

      self.productDialog.data = _.clone(link._data)
      self.productDialog.show = true
    },
    sendProductFormData: function () {
      if (this.productDialog.data.id) {
      } else {
        var data = {
          product: this.productDialog.data.product,
          categories:
            this.productDialog.data.categories +
            this.productDialog.categoriesextra,
          description: this.productDialog.data.description,
          image: this.productDialog.data.image,
          price: this.productDialog.data.price,
          quantity: this.productDialog.data.quantity
        }
      }
      if (this.productDialog.data.id) {
        this.updateProduct(this.productDialog.data)
      } else {
        this.createProduct(data)
      }
    },
    imageAdded(file) {
      let blobURL = URL.createObjectURL(file)
      let image = new Image()
      image.src = blobURL
      image.onload = async () => {
        let canvas = document.createElement('canvas')
        canvas.setAttribute('width', 100)
        canvas.setAttribute('height', 100)
        await pica.resize(image, canvas, {
          quality: 0,
          alpha: true,
          unsharpAmount: 95,
          unsharpRadius: 0.9,
          unsharpThreshold: 70
        })
        this.productDialog.data.image = canvas.toDataURL()
        this.productDialog = {...this.productDialog}
      }
    },
    imageCleared() {
      this.productDialog.data.image = null
      this.productDialog = {...this.productDialog}
    },
    updateProduct: function (data) {
      var self = this
      LNbits.api
        .request(
          'PUT',
          '/diagonalley/api/v1/products' + data.id,
          _.findWhere(self.g.user.wallets, {
            id: self.productDialog.data.wallet
          }).inkey,
          _.pick(
            data,
            'shopname',
            'relayaddress',
            'shippingzone1',
            'zone1cost',
            'shippingzone2',
            'zone2cost',
            'email'
          )
        )
        .then(function (response) {
          self.products = _.reject(self.products, function (obj) {
            return obj.id == data.id
          })
          self.products.push(mapDiagonAlley(response.data))
          self.productDialog.show = false
          self.productDialog.data = {}
        })
        .catch(function (error) {
          LNbits.utils.notifyApiError(error)
        })
    },
    createProduct: function (data) {
      var self = this
      LNbits.api
        .request(
          'POST',
          '/diagonalley/api/v1/products',
          _.findWhere(self.g.user.wallets, {
            id: self.productDialog.data.wallet
          }).inkey,
          data
        )
        .then(function (response) {
          self.products.push(mapDiagonAlley(response.data))
          self.productDialog.show = false
          self.productDialog.data = {}
        })
        .catch(function (error) {
          LNbits.utils.notifyApiError(error)
        })
    },
    deleteProduct: function (productId) {
      var self = this
      var product = _.findWhere(this.products, {id: productId})

      LNbits.utils
        .confirmDialog('Are you sure you want to delete this products link?')
        .onOk(function () {
          LNbits.api
            .request(
              'DELETE',
              '/diagonalley/api/v1/products/' + productId,
              _.findWhere(self.g.user.wallets, {id: product.wallet}).inkey
            )
            .then(function (response) {
              self.products = _.reject(self.products, function (obj) {
                return obj.id == productId
              })
            })
            .catch(function (error) {
              LNbits.utils.notifyApiError(error)
            })
        })
    },
    exportProductsCSV: function () {
      LNbits.utils.exportCSV(this.productsTable.columns, this.products)
    },
    ////////////////////////////////////////
    //////////////////ZONE//////////////////
    ////////////////////////////////////////
    getZones: function () {
      var self = this

      LNbits.api
        .request(
          'GET',
          '/diagonalley/api/v1/zones?all_wallets',
          this.g.user.wallets[0].inkey
        )
        .then(function (response) {
          self.zones = response.data.map(function (obj) {
            return mapDiagonAlley(obj)
          })
        })
    },
    openZoneUpdateDialog: function (linkId) {
      var self = this
      var link = _.findWhere(self.zones, {id: linkId})

      this.zoneDialog.data = _.clone(link._data)
      this.zoneDialog.show = true
    },
    sendZoneFormData: function () {
      if (this.zoneDialog.data.id) {
      } else {
        var data = {
          countries: toString(this.zoneDialog.data.countries),
          cost: parseInt(this.zoneDialog.data.cost)
        }
      }

      if (this.zoneDialog.data.id) {
        this.updateZone(this.zoneDialog.data)
      } else {
        this.createZone(data)
      }
    },
    updateZone: function (data) {
      var self = this
      LNbits.api
        .request(
          'PUT',
          '/diagonalley/api/v1/zones' + data.id,
          _.findWhere(self.g.user.wallets, {
            id: self.zoneDialog.data.wallet
          }).inkey,
          _.pick(data, 'countries', 'cost')
        )
        .then(function (response) {
          self.zones = _.reject(self.zones, function (obj) {
            return obj.id == data.id
          })
          self.zones.push(mapDiagonAlley(response.data))
          self.zoneDialog.show = false
          self.zoneDialog.data = {}
          data = {}
        })
        .catch(function (error) {
          LNbits.utils.notifyApiError(error)
        })
    },
    createZone: function (data) {
      var self = this
      console.log(self.g.user.wallets[0])
      console.log(data)
      LNbits.api
        .request(
          'POST',
          '/diagonalley/api/v1/zones',
          self.g.user.wallets[0].inkey,
          data
        )
        .then(function (response) {
          self.zones.push(mapDiagonAlley(response.data))
          self.zoneDialog.show = false
          self.zoneDialog.data = {}
          data = {}
        })
        .catch(function (error) {
          LNbits.utils.notifyApiError(error)
        })
    },
    deleteZone: function (zoneId) {
      var self = this
      var zone = _.findWhere(self.zones, {id: zoneId})

      LNbits.utils
        .confirmDialog('Are you sure you want to delete this Zone link?')
        .onOk(function () {
          LNbits.api
            .request(
              'DELETE',
              '/diagonalley/api/v1/zones/' + zoneId,
              _.findWhere(self.g.user.wallets, {id: zone.wallet}).inkey
            )
            .then(function (response) {
              self.zones = _.reject(self.zones, function (obj) {
                return obj.id == zoneId
              })
            })
            .catch(function (error) {
              LNbits.utils.notifyApiError(error)
            })
        })
    },
    exportZonesCSV: function () {
      LNbits.utils.exportCSV(this.zonesTable.columns, this.zones)
    },
    ////////////////////////////////////////
    //////////////////SHOP//////////////////
    ////////////////////////////////////////
    getShops: function () {
      var self = this

      LNbits.api
        .request(
          'GET',
          '/diagonalley/api/v1/shops?all_wallets',
          this.g.user.wallets[0].inkey
        )
        .then(function (response) {
          self.shops = response.data.map(function (obj) {
            return mapDiagonAlley(obj)
          })
        })
    },
    openShopUpdateDialog: function (linkId) {
      var self = this
      var link = _.findWhere(self.shops, {id: linkId})

      this.shopDialog.data = _.clone(link._data)
      this.shopDialog.show = true
    },
    sendShopFormData: function () {
      if (this.shopDialog.data.id) {
      } else {
        var data = {
          countries: this.shopDialog.data.countries,
          cost: this.shopDialog.data.cost
        }
      }

      if (this.shopDialog.data.id) {
        this.updateZone(this.shopDialog.data)
      } else {
        this.createZone(data)
      }
    },
    updateShop: function (data) {
      var self = this
      LNbits.api
        .request(
          'PUT',
          '/diagonalley/api/v1/shops' + data.id,
          _.findWhere(self.g.user.wallets, {
            id: self.shopDialog.data.wallet
          }).inkey,
          _.pick(data, 'countries', 'cost')
        )
        .then(function (response) {
          self.shops = _.reject(self.shops, function (obj) {
            return obj.id == data.id
          })
          self.shops.push(mapDiagonAlley(response.data))
          self.shopDialog.show = false
          self.shopDialog.data = {}
          data = {}
        })
        .catch(function (error) {
          LNbits.utils.notifyApiError(error)
        })
    },
    createShop: function (data) {
      var self = this
      console.log('cuntywoo')
      LNbits.api
        .request(
          'POST',
          '/diagonalley/api/v1/shops',
          _.findWhere(self.g.user.wallets, {
            id: self.shopDialog.data.wallet
          }).inkey,
          data
        )
        .then(function (response) {
          self.shops.push(mapDiagonAlley(response.data))
          self.shopDialog.show = false
          self.shopDialog.data = {}
          data = {}
        })
        .catch(function (error) {
          LNbits.utils.notifyApiError(error)
        })
    },
    deleteShop: function (shopId) {
      var self = this
      var shop = _.findWhere(self.shops, {id: shopId})

      LNbits.utils
        .confirmDialog('Are you sure you want to delete this Shop link?')
        .onOk(function () {
          LNbits.api
            .request(
              'DELETE',
              '/diagonalley/api/v1/shops/' + shopId,
              _.findWhere(self.g.user.wallets, {id: shop.wallet}).inkey
            )
            .then(function (response) {
              self.shops = _.reject(self.shops, function (obj) {
                return obj.id == shopId
              })
            })
            .catch(function (error) {
              LNbits.utils.notifyApiError(error)
            })
        })
    },
    exportShopsCSV: function () {
      LNbits.utils.exportCSV(this.shopsTable.columns, this.shops)
    },
    ////////////////////////////////////////
    ////////////////ORDERS//////////////////
    ////////////////////////////////////////
    getOrders: function () {
      var self = this

      LNbits.api
        .request(
          'GET',
          '/diagonalley/api/v1/orders?all_wallets',
          this.g.user.wallets[0].inkey
        )
        .then(function (response) {
          self.orders = response.data.map(function (obj) {
            return mapDiagonAlley(obj)
          })
        })
    },
    createOrder: function () {
      var data = {
        address: this.orderDialog.data.address,
        email: this.orderDialog.data.email,
        quantity: this.orderDialog.data.quantity,
        shippingzone: this.orderDialog.data.shippingzone
      }
      var self = this

      LNbits.api
        .request(
          'POST',
          '/diagonalley/api/v1/orders',
          _.findWhere(self.g.user.wallets, {id: self.orderDialog.data.wallet})
            .inkey,
          data
        )
        .then(function (response) {
          self.orders.push(mapDiagonAlley(response.data))
          self.orderDialog.show = false
          self.orderDialog.data = {}
        })
        .catch(function (error) {
          LNbits.utils.notifyApiError(error)
        })
    },
    deleteOrder: function (orderId) {
      var self = this
      var order = _.findWhere(self.orders, {id: orderId})

      LNbits.utils
        .confirmDialog('Are you sure you want to delete this order link?')
        .onOk(function () {
          LNbits.api
            .request(
              'DELETE',
              '/diagonalley/api/v1/orders/' + orderId,
              _.findWhere(self.g.user.wallets, {id: order.wallet}).inkey
            )
            .then(function (response) {
              self.orders = _.reject(self.orders, function (obj) {
                return obj.id == orderId
              })
            })
            .catch(function (error) {
              LNbits.utils.notifyApiError(error)
            })
        })
    },
    shipOrder: function (order_id) {
      var self = this

      LNbits.api
        .request(
          'GET',
          '/diagonalley/api/v1/orders/shipped/' + order_id,
          this.g.user.wallets[0].inkey
        )
        .then(function (response) {
          self.orders = response.data.map(function (obj) {
            return mapDiagonAlley(obj)
          })
        })
    },
    exportOrdersCSV: function () {
      LNbits.utils.exportCSV(this.ordersTable.columns, this.orders)
    }
  },
  created: function () {
    if (this.g.user.wallets.length) {
      this.getStalls()
      this.getProducts()
      this.getZones()
      this.getOrders()
    }
  }
})
