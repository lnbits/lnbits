window.app.component('lnbits-wallet-icon', {
  template: '#lnbits-wallet-icon',
  mixins: [window.windowMixin],
  data() {
    return {
      icon: {
        show: false,
        data: {},
        colorOptions: [
          'primary',
          'purple',
          'orange',
          'green',
          'brown',
          'blue',
          'red',
          'pink'
        ],
        options: [
          'home',
          'star',
          'bolt',
          'paid',
          'savings',
          'store',
          'videocam',
          'music_note',
          'flight',
          'train',
          'directions_car',
          'school',
          'construction',
          'science',
          'sports_esports',
          'sports_tennis',
          'theaters',
          'water',
          'headset_mic',
          'videogame_asset',
          'person',
          'group',
          'pets',
          'sunny',
          'elderly',
          'verified',
          'snooze',
          'mail',
          'forum',
          'shopping_cart',
          'shopping_bag',
          'attach_money',
          'print_connect',
          'dark_mode',
          'light_mode',
          'android',
          'network_wifi',
          'shield',
          'fitness_center',
          'lunch_dining'
        ]
      }
    }
  },
  methods: {
    setSelectedIcon(selectedIcon) {
      this.icon.data.icon = selectedIcon
    },
    setSelectedColor(selectedColor) {
      this.icon.data.color = selectedColor
    },
    setIcon() {
      this.$emit('update-wallet', this.icon.data)
      this.icon.show = false
    }
  }
})
