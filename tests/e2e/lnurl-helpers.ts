import http from 'node:http'

import {apiJson} from './fixtures'
import {type E2EWallet, invoicePaymentRequest} from './extension-helpers'

export class LNURLPayServer {
  private readonly baseUrl: string
  private readonly targetWallet: E2EWallet
  private server?: http.Server
  private serverUrl?: string

  private constructor(baseUrl: string, targetWallet: E2EWallet) {
    this.baseUrl = baseUrl
    this.targetWallet = targetWallet
  }

  static async start(
    baseUrl: string,
    targetWallet: E2EWallet
  ): Promise<LNURLPayServer> {
    const lnurlServer = new LNURLPayServer(baseUrl, targetWallet)
    await lnurlServer.listen()
    return lnurlServer
  }

  get url(): string {
    if (!this.serverUrl) throw new Error('LNURL server is not listening')
    return this.serverUrl
  }

  get lnurl(): string {
    return bech32Encode(
      'lnurl',
      convertBits([...new TextEncoder().encode(this.url)], 8, 5, true)
    )
  }

  async close(): Promise<void> {
    const server = this.server
    if (!server) return
    await new Promise<void>((resolve, reject) => {
      server.close(error => {
        if (error) reject(error)
        else resolve()
      })
    })
  }

  private async listen(): Promise<void> {
    this.server = http.createServer((request, response) => {
      void this.handleRequest(request, response)
    })
    await new Promise<void>((resolve, reject) => {
      this.server?.once('error', reject)
      this.server?.listen(0, '127.0.0.1', () => resolve())
    })
    const address = this.server.address()
    if (!address || typeof address === 'string') {
      throw new Error('LNURL server did not bind a TCP address')
    }
    this.serverUrl = `http://127.0.0.1:${address.port}/pay`
  }

  private async handleRequest(
    request: http.IncomingMessage,
    response: http.ServerResponse
  ): Promise<void> {
    try {
      const requestUrl = new URL(request.url ?? '/', this.url)
      if (requestUrl.pathname === '/pay') {
        sendJson(response, 200, {
          tag: 'payRequest',
          callback: this.callbackUrl(),
          minSendable: 1000,
          maxSendable: 1_000_000,
          metadata: JSON.stringify([['text/plain', 'LNbits e2e LNURL-pay']])
        })
        return
      }

      if (requestUrl.pathname === '/callback') {
        const amountMsat = Number(requestUrl.searchParams.get('amount') ?? '0')
        const invoice = await apiJson(
          this.baseUrl,
          'POST',
          '/api/v1/payments',
          {
            out: false,
            amount: Math.trunc(amountMsat / 1000),
            unit: 'sat',
            memo: 'LNbits e2e LNURL-pay target'
          },
          this.targetWallet.inkey
        )
        sendJson(response, 200, {
          pr: invoicePaymentRequest(invoice),
          routes: []
        })
        return
      }

      sendJson(response, 404, {
        status: 'ERROR',
        reason: 'LNURL route not found.'
      })
    } catch (error) {
      sendJson(response, 500, {
        status: 'ERROR',
        reason: String(error)
      })
    }
  }

  private callbackUrl(): string {
    const url = new URL(this.url)
    url.pathname = '/callback'
    return url.toString()
  }
}

function sendJson(
  response: http.ServerResponse,
  status: number,
  body: Record<string, unknown>
): void {
  const rawBody = JSON.stringify(body)
  response.writeHead(status, {
    'Content-Type': 'application/json',
    'Content-Length': Buffer.byteLength(rawBody)
  })
  response.end(rawBody)
}

const BECH32_CHARSET = 'qpzry9x8gf2tvdw0s3jn54khce6mua7l'

function bech32Encode(hrp: string, data: number[]): string {
  const combined = [...data, ...bech32CreateChecksum(hrp, data)]
  return `${hrp}1${combined.map(value => BECH32_CHARSET[value]).join('')}`
}

function bech32CreateChecksum(hrp: string, data: number[]): number[] {
  const values = [...bech32HrpExpand(hrp), ...data, 0, 0, 0, 0, 0, 0]
  const polymod = bech32Polymod(values) ^ 1
  const result: number[] = []
  for (let index = 0; index < 6; index += 1) {
    result.push((polymod >> (5 * (5 - index))) & 31)
  }
  return result
}

function bech32HrpExpand(hrp: string): number[] {
  const highBits = [...hrp].map(char => char.charCodeAt(0) >> 5)
  const lowBits = [...hrp].map(char => char.charCodeAt(0) & 31)
  return [...highBits, 0, ...lowBits]
}

function bech32Polymod(values: number[]): number {
  const generators = [
    0x3b6a57b2, 0x26508e6d, 0x1ea119fa, 0x3d4233dd, 0x2a1462b3
  ]
  let checksum = 1
  for (const value of values) {
    const top = checksum >> 25
    checksum = ((checksum & 0x1ffffff) << 5) ^ value
    for (let index = 0; index < 5; index += 1) {
      if ((top >> index) & 1) checksum ^= generators[index]
    }
  }
  return checksum
}

function convertBits(
  data: number[],
  fromBits: number,
  toBits: number,
  pad: boolean
): number[] {
  let acc = 0
  let bits = 0
  const result: number[] = []
  const maxValue = (1 << toBits) - 1
  const maxAcc = (1 << (fromBits + toBits - 1)) - 1

  for (const value of data) {
    if (value < 0 || value >> fromBits) {
      throw new Error('Invalid bech32 data value')
    }
    acc = ((acc << fromBits) | value) & maxAcc
    bits += fromBits
    while (bits >= toBits) {
      bits -= toBits
      result.push((acc >> bits) & maxValue)
    }
  }

  if (pad) {
    if (bits > 0) result.push((acc << (toBits - bits)) & maxValue)
  } else if (bits >= fromBits || (acc << (toBits - bits)) & maxValue) {
    throw new Error('Invalid bech32 padding')
  }

  return result
}
