import {mount} from '@vue/test-utils'
import {expect, test} from 'vitest'
import LnbitsError from '../../../lnbits/static/components/lnbits-error.vue'

// installQuasarPlugin()
export const quasarMock = {
  global: {
    mocks: {
      g: {
        isUserAuthorized: true
      },
      $q: {
        platform: {},
        screen: {},
        dark: false
      }
    },
    stubs: {
      QCard: true,
      QCardSection: true,
      QIcon: true,
      QBtn: true
    }
  }
}
test('displays message and code', () => {
  expect(LnbitsError).toBeTruthy()

  const wrapper = mount(LnbitsError, {
    props: {
      message: 'Page not found!!!',
      code: 404
    },
    ...quasarMock
  })
  expect(wrapper.text()).toContain('Page not found!!!')
  expect(wrapper.text()).toContain('404')
})
