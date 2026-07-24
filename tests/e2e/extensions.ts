import type {ExtensionUnderTest} from './extension-helpers'

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
