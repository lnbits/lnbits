// import { installQuasarPlugin } from '@quasar/quasar-app-extension-testing-unit-vitest';
import {mount} from '@vue/test-utils'
import {expect, test} from 'vitest'
import {createApp} from 'vue'
import {Quasar} from 'quasar'
import LnbitsError from '../../../lnbits/static/components/lnbits-error.vue'

test('displays message and code', () => {
  const app = createApp({})
  app.use(Quasar)

  const wrapper = mount(LnbitsError, {
    global: {
      plugins: [Quasar]
    },
    props: {
      message: 'Page not found!!!',
      code: 404
    }
  })
  expect(wrapper.text()).toContain('Page not found!!!')
  expect(wrapper.text()).toContain('404')
})
