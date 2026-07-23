import {randomUUID} from 'node:crypto'

import {test as base, expect, type Page} from '@playwright/test'

export type LNbitsE2EServer = {
  baseUrl: string
  password: string
  username: string
}

const server: LNbitsE2EServer = {
  baseUrl: process.env.LNBITS_E2E_BASE_URL ?? 'http://127.0.0.1:5009',
  username: 'superadmin',
  password: 'secret1234'
}

export const test = base.extend<
  {},
  {
    lnbitsServer: LNbitsE2EServer
  }
>({
  lnbitsServer: [
    async ({}, use) => {
      await completeFirstInstall(server)
      await use(server)
    },
    {scope: 'worker'}
  ],
  page: async ({page, lnbitsServer}, use) => {
    void lnbitsServer
    await page.addInitScript(
      "window.localStorage.setItem('lnbits.disclaimerShown', 'true')"
    )
    page.setDefaultTimeout(60_000)
    await use(page)
  }
})

export {expect}

async function completeFirstInstall(e2eServer: LNbitsE2EServer): Promise<void> {
  const deadline = Date.now() + 90_000
  let lastError = ''

  while (Date.now() < deadline) {
    try {
      const response = await requestJson(
        `${e2eServer.baseUrl}/api/v1/auth/first_install`,
        {
          method: 'PUT',
          data: {
            username: e2eServer.username,
            password: e2eServer.password,
            password_repeat: e2eServer.password,
            first_install_token: ''
          },
          timeoutMs: 2_000
        }
      )
      if (response.status === 200) return
      lastError = `${response.status}: ${JSON.stringify(response.body)}`
    } catch (error) {
      lastError = String(error)
    }
    await delay(500)
  }

  throw new Error(
    `LNbits e2e server did not complete first install. Last error: ${lastError}`
  )
}

type RequestJsonOptions = {
  apiKey?: string
  data?: Record<string, unknown>
  method: string
  timeoutMs?: number
}

export async function apiJson(
  baseUrl: string,
  method: string,
  path: string,
  data?: Record<string, unknown>,
  apiKey?: string,
  timeoutMs = 30_000
): Promise<Record<string, unknown>> {
  const response = await requestJson(`${baseUrl}${path}`, {
    method,
    data,
    apiKey,
    timeoutMs
  })
  if (response.status < 200 || response.status >= 300) {
    throw new Error(
      `${method} ${path} failed with ${response.status}: ${JSON.stringify(response.body)}`
    )
  }
  if (!isRecord(response.body)) {
    throw new Error(
      `${method} ${path} returned non-object JSON: ${JSON.stringify(response.body)}`
    )
  }
  return response.body
}

async function requestJson(
  url: string,
  {method, data, apiKey, timeoutMs = 30_000}: RequestJsonOptions
): Promise<{body: unknown; status: number}> {
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), timeoutMs)

  try {
    const response = await fetch(url, {
      method,
      headers: {
        'Content-Type': 'application/json',
        ...(apiKey ? {'X-Api-Key': apiKey} : {})
      },
      body: data === undefined ? undefined : JSON.stringify(data),
      signal: controller.signal
    })
    const text = await response.text()
    let body: unknown = {}
    try {
      body = text ? JSON.parse(text) : {}
    } catch (_error) {
      body = {detail: text}
    }
    return {status: response.status, body}
  } finally {
    clearTimeout(timeout)
  }
}

export function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

export async function browserJson(
  page: Page,
  method: string,
  path: string,
  data?: Record<string, unknown>,
  apiKey?: string
): Promise<unknown> {
  const response = await page.evaluate(
    async ({method, path, data, apiKey}) => {
      const headers: Record<string, string> = {
        'Content-Type': 'application/json'
      }
      if (apiKey) headers['X-Api-Key'] = apiKey
      const response = await fetch(path, {
        method,
        headers,
        credentials: 'same-origin',
        body: data === undefined ? undefined : JSON.stringify(data)
      })
      const text = await response.text()
      let body: unknown = {}
      try {
        body = text ? JSON.parse(text) : {}
      } catch (_error) {
        body = {detail: text}
      }
      return {status: response.status, body}
    },
    {method, path, data, apiKey}
  )
  if (response.status < 200 || response.status >= 300) {
    throw new Error(
      `${method} ${path} failed with ${response.status}: ${JSON.stringify(response.body)}`
    )
  }
  return response.body
}

export async function waitForResult<T>(
  description: string,
  callback: () => Promise<T | null | undefined>,
  {timeout = 30_000, interval = 500}: {interval?: number; timeout?: number} = {}
): Promise<T> {
  const deadline = Date.now() + timeout
  let lastResult: T | null | undefined
  let lastError: unknown

  while (Date.now() < deadline) {
    try {
      lastError = undefined
      lastResult = await callback()
      if (lastResult !== null && lastResult !== undefined) return lastResult
    } catch (error) {
      lastError = error
    }
    await delay(interval)
  }

  throw new Error(
    `Timed out waiting for ${description}. Last result: ${JSON.stringify(lastResult)}. Last error: ${String(lastError)}`
  )
}

export function delay(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms))
}

export function randomHex(): string {
  return randomUUID().replace(/-/g, '').slice(0, 8)
}
