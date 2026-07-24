import type {ExtensionUnderTest} from './extension-helpers'

export const TIPS: ExtensionUnderTest = {
  extId: 'tips',
  name: 'Tips',
  manifestUrl:
    'https://raw.githubusercontent.com/lnbits/tips/refs/heads/main/manifest.json',
  repository: 'lnbits/tips',
  permissionTexts: ['Make background payments']
}

export const BIGPAYMENT: ExtensionUnderTest = {
  extId: 'bigpayment',
  name: 'BigPayment',
  manifestUrl:
    'https://raw.githubusercontent.com/lnbits/bigpayment/refs/heads/main/manifest.json',
  repository: 'lnbits/bigpayment',
  permissionTexts: ['Pay invoices']
}

export const PINGPONG: ExtensionUnderTest = {
  extId: 'pingpong',
  name: 'Ping Pong',
  manifestUrl:
    'https://raw.githubusercontent.com/lnbits/pingpong/refs/heads/main/manifest.json',
  repository: 'lnbits/pingpong',
  permissionTexts: ['Make background payments']
}

export const PAYSPLIT: ExtensionUnderTest = {
  extId: 'paysplit',
  name: 'PaySplit',
  manifestUrl:
    'https://raw.githubusercontent.com/lnbits/paysplit/refs/heads/main/manifest.json',
  repository: 'lnbits/paysplit',
  permissionTexts: ['Watch wallet payments']
}

export const LIVE_EXTENSIONS = [TIPS, BIGPAYMENT, PINGPONG, PAYSPLIT]
