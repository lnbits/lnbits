Vue.component('lnbits-wallet-list', {
  data: function () {
    return {
      user: null,
      activeWallet: null,
      showForm: false,
      walletName: ''
    }
  },
  template: `
    <q-list v-if="user && user.wallets.length" dense class="lnbits-drawer__q-list">
      <q-item-label header>Wallets</q-item-label>
      <q-item v-for="wallet in user.wallets" :key="wallet.id"
        clickable
        :active="activeWallet && activeWallet.id == wallet.id"
        tag="a" :href="wallet.url">
        <q-item-section side>
          <q-avatar size="md"
            :color="(activeWallet && activeWallet.id == wallet.id)
              ? (($q.dark.isActive) ? 'deep-purple-5' : 'deep-purple')
              : 'grey-5'">
            <q-icon name="flash_on" :size="($q.dark.isActive) ? '21px' : '20px'"
              :color="($q.dark.isActive) ? 'blue-grey-10' : 'grey-3'"></q-icon>
          </q-avatar>
        </q-item-section>
        <q-item-section>
          <q-item-label lines="1">{{ wallet.name }}</q-item-label>
          <q-item-label caption>{{ wallet.fsat }} sat</q-item-label>
        </q-item-section>
        <q-item-section side v-show="activeWallet && activeWallet.id == wallet.id">
          <q-icon name="chevron_right" color="grey-5" size="md"></q-icon>
        </q-item-section>
      </q-item>
      <q-item clickable @click="showForm = !showForm">
        <q-item-section side>
          <q-icon :name="(showForm) ? 'remove' : 'add'" color="grey-5" size="md"></q-icon>
        </q-item-section>
        <q-item-section>
          <q-item-label lines="1" class="text-caption">Add a wallet</q-item-label>
        </q-item-section>
      </q-item>
      <q-item v-if="showForm">
        <q-item-section>
          <q-form>
            <q-input filled dense v-model="walletName" label="Name wallet *">
              <template v-slot:append>
                <q-btn round dense flat icon="send" size="sm" @click="createWallet" :disable="walletName == ''"></q-btn>
              </template>
            </q-input>
          </q-form>
        </q-item-section>
      </q-item>
    </q-list>
  `,
  methods: {
    createWallet: function () {
      LNbits.href.createWallet(this.walletName, this.user.id);
    }
  },
  created: function () {
    if (window.user) {
      this.user = LNbits.map.user(window.user);
    }
    if (window.wallet) {
      this.activeWallet = LNbits.map.wallet(window.wallet);
    }
  }
});

Vue.component('lnbits-extension-list', {
  data: function () {
    return {
      extensions: [],
      user: null
    }
  },
  template: `
    <q-list v-if="user" dense class="lnbits-drawer__q-list">
      <q-item-label header>Extensions</q-item-label>
      <q-item v-for="extension in userExtensions" :key="extension.code"
        clickable
        tag="a" :href="[extension.url, '?usr=', user.id].join('')">
        <q-item-section side>
          <q-avatar size="md" color="grey-5">
            <q-icon :name="extension.icon" :size="($q.dark.isActive) ? '21px' : '20px'"
              :color="($q.dark.isActive) ? 'blue-grey-10' : 'grey-3'"></q-icon>
          </q-avatar>
        </q-item-section>
        <q-item-section>
          <q-item-label lines="1">{{ extension.name }}</q-item-label>
        </q-item-section>
      </q-item>
      <q-item clickable tag="a" :href="['/extensions?usr=', user.id].join('')">
        <q-item-section side>
          <q-icon name="clear_all" color="grey-5" size="md"></q-icon>
        </q-item-section>
        <q-item-section>
          <q-item-label lines="1" class="text-caption">Manage extensions</q-item-label>
        </q-item-section>
      </q-item>
    </q-list>
  `,
  computed: {
    userExtensions: function () {
      if (!this.user) return [];
      var userExtensions = this.user.extensions;
      return this.extensions.filter(function (obj) {
        return userExtensions.indexOf(obj.code) !== -1;
      });
    }
  },
  created: function () {
    this.extensions = window.extensions.map(function (data) {
      return LNbits.map.extension(data);
    }).sort(function (a, b) {
      return a.name > b.name;
    });
    if (window.user) {
      this.user = LNbits.map.user(window.user);
    }
  }
});
