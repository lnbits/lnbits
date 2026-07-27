import type {ExtensionUnderTest} from './extension-helpers'

const extensionFixtureUrl =
  process.env.LNBITS_E2E_EXTENSION_FIXTURE_URL ?? 'http://127.0.0.1:5010'

export const SUPPORTCHAT: ExtensionUnderTest = {
  extId: 'supportchat',
  name: 'Support Chat',
  manifestUrl: `${extensionFixtureUrl}/manifest.json`,
  repository: `${extensionFixtureUrl}/manifest.json`,
  configUrl: `${extensionFixtureUrl}/config.json`,
  version: '0.2.0',
  permissionTexts: [
    'Read public extension storage',
    'Append public extension storage',
    'Publish websocket messages'
  ]
}

export const TIPS: ExtensionUnderTest = {
  extId: 'tips',
  name: 'Tips',
  permissionTexts: ['Make background payments']
}

export const BIGPAYMENT: ExtensionUnderTest = {
  extId: 'bigpayment',
  name: 'BigPayment',
  permissionTexts: ['Pay invoices']
}

export const PINGPONG: ExtensionUnderTest = {
  extId: 'pingpong',
  name: 'Ping Pong',
  permissionTexts: ['Make background payments']
}

export const PAYSPLIT: ExtensionUnderTest = {
  extId: 'paysplit',
  name: 'PaySplit',
  permissionTexts: ['Watch wallet payments']
}
