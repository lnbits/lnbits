Vue.component('lnbits-extension-rating', {
  name: 'lnbits-extension-rating',
  props: ['rating'],
  template: `
    <div style="margin-bottom: 3px">
        <q-rating
          v-model="rating"
          size="1.5em"
          :max="5"
          color="primary"
          ><q-tooltip>
            <span v-text="$t('extension_rating_soon')"></span> </q-tooltip
        ></q-rating>
    </div>
  `
})
