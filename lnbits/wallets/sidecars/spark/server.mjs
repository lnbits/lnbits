import http from 'node:http'

import {SparkWallet} from '@buildonspark/spark-sdk'

const PORT = parseInt(process.env.SPARK_SIDECAR_PORT || '8765', 10)
const HOST = process.env.SPARK_SIDECAR_HOST || '127.0.0.1'
const API_KEY = process.env.SPARK_SIDECAR_API_KEY || ''
const MNEMONIC = process.env.SPARK_MNEMONIC || ''
const NETWORK = process.env.SPARK_NETWORK || 'MAINNET'
const PAY_WAIT_MS = parseInt(process.env.SPARK_PAY_WAIT_MS || '4000', 10)
const PAY_POLL_MS = parseInt(process.env.SPARK_PAY_POLL_MS || '500', 10)
const ACCOUNT_NUMBER = process.env.SPARK_ACCOUNT_NUMBER
  ? parseInt(process.env.SPARK_ACCOUNT_NUMBER, 10)
  : undefined

if (!MNEMONIC) {
  console.error('Missing SPARK_MNEMONIC for Spark sidecar.')
  process.exit(1)
}

let walletPromise
const paymentHashToRequestId = new Map()
async function getWallet() {
  if (!walletPromise) {
    walletPromise = SparkWallet.initialize({
      mnemonicOrSeed: MNEMONIC,
      accountNumber: ACCOUNT_NUMBER,
      options: {network: NETWORK}
    }).then(({wallet}) => wallet)
  }
  return walletPromise
}

async function shutdown() {
  try {
    if (walletPromise) {
      const wallet = await walletPromise
      if (wallet && typeof wallet.cleanupConnections === 'function') {
        await wallet.cleanupConnections()
      } else if (wallet && typeof wallet.cleanup === 'function') {
        wallet.cleanup()
      }
    }
  } catch (error) {
    console.error('Error during Spark sidecar shutdown:', error)
  } finally {
    process.exit(0)
  }
}

process.on('SIGINT', shutdown)
process.on('SIGTERM', shutdown)

function sendJson(res, statusCode, payload) {
  res.writeHead(statusCode, {'content-type': 'application/json'})
  res.end(JSON.stringify(payload))
}

async function readJson(req) {
  const chunks = []
  for await (const chunk of req) {
    chunks.push(chunk)
  }
  if (chunks.length === 0) {
    return {}
  }
  return JSON.parse(Buffer.concat(chunks).toString('utf8'))
}

function feeToMsat(fee) {
  if (!fee || fee.originalValue === undefined || !fee.originalUnit) {
    return null
  }
  const value = Number(fee.originalValue)
  if (!Number.isFinite(value)) {
    return null
  }
  switch (fee.originalUnit) {
    case 'MILLISATOSHI':
      return BigInt(Math.round(value)).toString()
    case 'SATOSHI':
      return BigInt(Math.round(value * 1000)).toString()
    case 'BITCOIN':
      return BigInt(Math.round(value * 100_000_000_000)).toString()
    default:
      return BigInt(Math.round(value * 1000)).toString()
  }
}

const SEND_SUCCESS_STATUSES = new Set([
  'LIGHTNING_PAYMENT_SUCCEEDED',
  'TRANSFER_COMPLETED',
  'PREIMAGE_PROVIDED'
])
const SEND_FAILURE_STATUSES = new Set([
  'LIGHTNING_PAYMENT_FAILED',
  'TRANSFER_FAILED',
  'PREIMAGE_PROVIDING_FAILED',
  'USER_TRANSFER_VALIDATION_FAILED',
  'USER_SWAP_RETURN_FAILED'
])

function isSendTerminal(status) {
  return SEND_SUCCESS_STATUSES.has(status) || SEND_FAILURE_STATUSES.has(status)
}

async function waitForSendStatus(wallet, requestId, timeoutMs) {
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) {
    const payment = await wallet.getLightningSendRequest(requestId)
    if (payment && isSendTerminal(payment.status)) {
      return payment
    }
    await new Promise(resolve => setTimeout(resolve, PAY_POLL_MS))
  }
  return null
}

const server = http.createServer(async (req, res) => {
  const url = new URL(
    req.url || '/',
    `http://${req.headers.host || 'localhost'}`
  )

  if (API_KEY && req.headers['x-api-key'] !== API_KEY) {
    return sendJson(res, 401, {error: 'Unauthorized'})
  }

  try {
    if (req.method === 'GET' && url.pathname === '/health') {
      return sendJson(res, 200, {status: 'ok'})
    }

    if (req.method === 'POST' && url.pathname === '/v1/balance') {
      const wallet = await getWallet()
      const balance = await wallet.getBalance()
      const sats = BigInt(balance.balance)
      return sendJson(res, 200, {
        balance_sats: sats.toString(),
        balance_msat: (sats * 1000n).toString()
      })
    }

    if (req.method === 'POST' && url.pathname === '/v1/invoices') {
      const wallet = await getWallet()
      const body = await readJson(req)
      const amountSats = Number(body.amount_sats)
      if (!Number.isFinite(amountSats) || amountSats < 0) {
        return sendJson(res, 400, {error: 'Invalid amount_sats'})
      }
      const invoice = await wallet.createLightningInvoice({
        amountSats,
        memo: body.memo || undefined,
        descriptionHash: body.description_hash || undefined,
        expirySeconds: body.expiry_seconds || undefined
      })
      return sendJson(res, 200, {
        checking_id: invoice.id,
        payment_request: invoice.invoice.encodedInvoice,
        payment_hash: invoice.invoice.paymentHash,
        status: invoice.status,
        preimage: invoice.paymentPreimage || null
      })
    }

    if (req.method === 'POST' && url.pathname === '/v1/payments') {
      const wallet = await getWallet()
      const body = await readJson(req)
      const bolt11 = body.bolt11
      if (!bolt11) {
        return sendJson(res, 400, {error: 'Missing bolt11'})
      }
      const maxFeeSats = Number(body.max_fee_sats || 0)
      const amountSatsToSend = body.amount_sats
        ? Number(body.amount_sats)
        : undefined
      const paymentHash = body.payment_hash || null
      let payment = await wallet.payLightningInvoice({
        invoice: bolt11,
        maxFeeSats,
        amountSatsToSend
      })
      if (
        PAY_WAIT_MS > 0 &&
        payment &&
        payment.id &&
        !isSendTerminal(payment.status)
      ) {
        const refreshed = await waitForSendStatus(
          wallet,
          payment.id,
          PAY_WAIT_MS
        )
        if (refreshed) {
          payment = refreshed
        }
      }
      if (paymentHash && payment?.id) {
        paymentHashToRequestId.set(paymentHash, payment.id)
      }
      return sendJson(res, 200, {
        checking_id: paymentHash || payment.id,
        status: payment.status,
        fee_msat: feeToMsat(payment.fee),
        preimage: payment.paymentPreimage || null
      })
    }

    const parts = url.pathname.split('/').filter(Boolean)
    if (parts.length === 3 && parts[0] === 'v1' && parts[1] === 'invoices') {
      const wallet = await getWallet()
      const invoice = await wallet.getLightningReceiveRequest(parts[2])
      if (!invoice) {
        return sendJson(res, 404, {error: 'Not found'})
      }
      return sendJson(res, 200, {
        checking_id: invoice.id,
        status: invoice.status,
        payment_hash: invoice.invoice.paymentHash,
        preimage: invoice.paymentPreimage || null
      })
    }

    if (parts.length === 3 && parts[0] === 'v1' && parts[1] === 'payments') {
      const wallet = await getWallet()
      const requestedId = parts[2]
      const lookupId = paymentHashToRequestId.get(requestedId) || requestedId
      const payment = await wallet.getLightningSendRequest(lookupId)
      if (!payment) {
        return sendJson(res, 404, {error: 'Not found'})
      }
      return sendJson(res, 200, {
        checking_id: requestedId,
        status: payment.status,
        fee_msat: feeToMsat(payment.fee),
        preimage: payment.paymentPreimage || null
      })
    }

    return sendJson(res, 404, {error: 'Not found'})
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    return sendJson(res, 500, {error: message})
  }
})

server.listen(PORT, HOST, () => {
  console.log(`Spark sidecar listening on ${HOST}:${PORT}`)
})

server.on('error', err => {
  if (err && err.code === 'EADDRINUSE') {
    console.error(`Spark sidecar port ${HOST}:${PORT} already in use.`)
    process.exit(1)
  }
  throw err
})
