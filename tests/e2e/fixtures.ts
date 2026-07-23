import {randomUUID} from 'node:crypto'

import {test as base, expect, type Page, type TestInfo} from '@playwright/test'

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

const detailedScreenshotStates = new WeakMap<
  TestInfo,
  {screenshotIndex: number}
>()

const DETAILED_SCREENSHOT_SCRIPT = `
(() => {
  if (window.__lnbitsDetailedScreenshotsInstalled) return
  window.__lnbitsDetailedScreenshotsInstalled = true

  let nextSnapshot = 0
  let scanScheduled = false
  const visibleElements = new WeakMap()

  const notify = payload => {
    setTimeout(() => {
      try {
        window.__lnbitsDetailedScreenshot({
          ...payload,
          snapshotId: payload.snapshotId || (payload.kind + '-' + Date.now() + '-' + ++nextSnapshot),
          url: payload.url || window.location.href
        })
      } catch (_error) {}
    }, 0)
  }

  const notifyUrl = () => {
    notify({
      kind: 'url',
      label: window.location.href,
      url: window.location.href
    })
  }

  for (const name of ['pushState', 'replaceState']) {
    const original = window.history[name]
    window.history[name] = function (...args) {
      const result = original.apply(this, args)
      setTimeout(notifyUrl, 0)
      return result
    }
  }

  window.addEventListener('hashchange', () => setTimeout(notifyUrl, 0))
  window.addEventListener('popstate', () => setTimeout(notifyUrl, 0))
  window.addEventListener('DOMContentLoaded', () => setTimeout(notifyUrl, 0))
  setTimeout(notifyUrl, 0)

  const groups = [
    { kind: 'dialog', selector: '.q-dialog, [role="dialog"]' },
    { kind: 'toast', selector: '.q-notification' }
  ]

  const isVisible = element => {
    if (!(element instanceof HTMLElement)) return false
    if (element.getAttribute('aria-hidden') === 'true') return false
    if (element.classList.contains('q-dialog--hidden')) return false

    const style = window.getComputedStyle(element)
    if (
      style.display === 'none' ||
      style.visibility === 'hidden' ||
      style.opacity === '0'
    ) {
      return false
    }

    const rect = element.getBoundingClientRect()
    return rect.width > 0 && rect.height > 0
  }

  const textFor = element => (
    element.getAttribute('aria-label') ||
    element.innerText ||
    element.textContent ||
    ''
  ).replace(/\\s+/g, ' ').trim().slice(0, 120)

  const labelFor = element => {
    const headings = element.querySelectorAll([
      '[role="heading"]',
      'h1',
      'h2',
      'h3',
      'h4',
      'h5',
      'h6',
      '.text-h1',
      '.text-h2',
      '.text-h3',
      '.text-h4',
      '.text-h5',
      '.text-h6'
    ].join(', '))

    for (const heading of headings) {
      if (isVisible(heading)) {
        const headingText = textFor(heading)
        if (headingText) return headingText
      }
    }

    return textFor(element)
  }

  const scan = () => {
    for (const group of groups) {
      for (const element of document.querySelectorAll(group.selector)) {
        if (isVisible(element)) {
          const label = labelFor(element)
          if (visibleElements.get(element) !== label) {
            visibleElements.set(element, label)
            notify({
              kind: group.kind,
              label,
              url: window.location.href
            })
          }
        } else {
          visibleElements.delete(element)
        }
      }
    }
  }

  const scheduleScan = () => {
    if (scanScheduled) return
    scanScheduled = true
    requestAnimationFrame(() => {
      scanScheduled = false
      scan()
    })
  }

  const installObserver = () => {
    if (!document.documentElement) return
    new MutationObserver(scheduleScan).observe(document.documentElement, {
      attributes: true,
      attributeFilter: ['aria-hidden', 'class', 'style'],
      childList: true,
      subtree: true
    })
    scheduleScan()
  }

  window.addEventListener('DOMContentLoaded', installObserver)
  setTimeout(installObserver, 0)
})()
`

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
  page: async ({page, lnbitsServer}, use, testInfo) => {
    void lnbitsServer
    await page.addInitScript(
      "window.localStorage.setItem('lnbits.disclaimerShown', 'true')"
    )
    const recorder = await installDetailedScreenshots(page, testInfo)
    page.setDefaultTimeout(60_000)
    try {
      await use(page)
    } finally {
      await recorder.finish()
    }
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

export type DetailedScreenshotHandle = {
  finish(): Promise<void>
}

export async function installDetailedScreenshots(
  page: Page,
  testInfo: TestInfo
): Promise<DetailedScreenshotHandle> {
  const recorder = new DetailedScreenshotRecorder(page, testInfo)
  await recorder.install()
  return recorder
}

type DetailedScreenshotPayload = {
  kind?: unknown
  label?: unknown
  snapshotId?: unknown
  url?: unknown
}

type DetailedScreenshotRequest = {
  kind: 'dialog' | 'toast' | 'url'
  label: string
  snapshotId: string
  url: string
}

class DetailedScreenshotRecorder {
  private readonly capturedUrlKeys = new Set<string>()
  private readonly page: Page
  private readonly pending: DetailedScreenshotRequest[] = []
  private readonly testInfo: TestInfo
  private flushPromise?: Promise<void>
  private flushTimer?: ReturnType<typeof setTimeout>
  private lastQueuedKey = ''
  private readonly state: {screenshotIndex: number}
  private stopped = false

  constructor(page: Page, testInfo: TestInfo) {
    this.page = page
    this.testInfo = testInfo
    this.state = detailedScreenshotStateFor(testInfo)
  }

  async install(): Promise<void> {
    await this.page.exposeBinding(
      '__lnbitsDetailedScreenshot',
      (_source, payload: DetailedScreenshotPayload) => {
        this.queue(this.requestFromPayload(payload))
      }
    )
    await this.page.addInitScript(DETAILED_SCREENSHOT_SCRIPT)
    this.page.on('framenavigated', frame => {
      const url = frame.url()
      this.queue({
        kind: 'url',
        label: url,
        snapshotId: `frame-${Date.now()}`,
        url
      })
    })
  }

  async finish(): Promise<void> {
    this.queue({
      kind: 'url',
      label: this.page.url(),
      snapshotId: `final-${Date.now()}`,
      url: this.page.url()
    })
    this.stopped = true
    if (this.flushTimer) {
      clearTimeout(this.flushTimer)
      this.flushTimer = undefined
    }
    await this.flush()
  }

  private requestFromPayload(
    payload: DetailedScreenshotPayload
  ): DetailedScreenshotRequest | null {
    const kind = typeof payload.kind === 'string' ? payload.kind : ''
    if (!['dialog', 'toast', 'url'].includes(kind)) return null

    const url =
      typeof payload.url === 'string' && payload.url
        ? payload.url
        : this.page.url()
    const label =
      typeof payload.label === 'string' && payload.label ? payload.label : kind
    const snapshotId =
      typeof payload.snapshotId === 'string' && payload.snapshotId
        ? payload.snapshotId
        : `${kind}-${Date.now()}`

    return {
      kind: kind as DetailedScreenshotRequest['kind'],
      label,
      snapshotId,
      url
    }
  }

  private queue(request: DetailedScreenshotRequest | null): void {
    if (this.stopped || !request) return
    if (!request.url || request.url === 'about:blank') return

    const key =
      request.kind === 'url'
        ? `${request.kind}:${request.url}`
        : `${request.kind}:${request.snapshotId}:${request.url}:${request.label}`
    if (request.kind === 'url' && this.capturedUrlKeys.has(key)) return
    if (key === this.lastQueuedKey) return

    this.lastQueuedKey = key
    this.pending.push(request)
    this.scheduleFlush()
  }

  private scheduleFlush(): void {
    if (this.flushTimer) return
    this.flushTimer = setTimeout(() => {
      this.flushTimer = undefined
      void this.flush()
    }, 75)
  }

  private async flush(): Promise<void> {
    if (this.flushPromise) {
      await this.flushPromise
      return
    }

    this.flushPromise = this.flushQueue()
    try {
      await this.flushPromise
    } finally {
      this.flushPromise = undefined
    }
  }

  private async flushQueue(): Promise<void> {
    while (this.pending.length) {
      const request = this.pending.shift()
      if (!request) continue
      await this.capture(request)
    }
  }

  private async capture(request: DetailedScreenshotRequest): Promise<void> {
    if (this.page.isClosed()) return

    if (request.kind === 'url') {
      const key = `${request.kind}:${request.url}`
      if (this.capturedUrlKeys.has(key)) return
      this.capturedUrlKeys.add(key)
    }

    const name = this.screenshotName(request)
    const path = this.testInfo.outputPath(`${name}.png`)
    try {
      await this.page.waitForLoadState('domcontentloaded', {timeout: 2_000})
    } catch (_error) {}
    try {
      await this.page.waitForTimeout(250)
      await this.page.screenshot({path, fullPage: true, timeout: 5_000})
      await this.testInfo.attach(name, {
        path,
        contentType: 'image/png'
      })
    } catch (_error) {}
  }

  private screenshotName(request: DetailedScreenshotRequest): string {
    this.state.screenshotIndex += 1
    return [
      'screenshot',
      this.state.screenshotIndex.toString().padStart(3, '0'),
      request.kind,
      slugFor(request.kind === 'url' ? request.url : request.label)
    ].join('-')
  }
}

function detailedScreenshotStateFor(testInfo: TestInfo): {
  screenshotIndex: number
} {
  const existing = detailedScreenshotStates.get(testInfo)
  if (existing) return existing
  const state = {screenshotIndex: 0}
  detailedScreenshotStates.set(testInfo, state)
  return state
}

function slugFor(value: string): string {
  const slug = value
    .replace(/^[a-z]+:\/\//i, '')
    .split(/[?#]/, 1)[0]
    .replace(/[^A-Za-z0-9._-]+/g, '-')
    .replace(/^[-._]+|[-._]+$/g, '')
    .slice(0, 80)
  return slug || 'capture'
}
