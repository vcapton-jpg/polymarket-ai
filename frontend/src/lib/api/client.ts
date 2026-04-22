/**
 * Minimal API client. Single place where JWT + base URL logic lives.
 *
 * Base URL priority:
 *   1. `VITE_API_URL` (absolute URL, e.g. `https://api.getforesight.io/api`)
 *   2. `/api` — resolved by Vite proxy in dev, nginx in prod.
 *
 * Auth: the token (if any) is read from localStorage under STORAGE_KEYS.token
 * on every call. We do NOT memoize so that login/logout are reflected
 * immediately without needing to rebuild the client.
 */

import { STORAGE_KEYS } from "@/lib/storageKeys"

const BASE = (import.meta.env.VITE_API_URL ?? "/api").replace(/\/$/, "")

export class ApiError extends Error {
  readonly status: number
  readonly body: unknown

  constructor(status: number, message: string, body?: unknown) {
    super(message)
    this.name = "ApiError"
    this.status = status
    this.body = body
  }
}

function authHeaders(): Record<string, string> {
  if (typeof window === "undefined") return {}
  try {
    const tok = window.localStorage.getItem(STORAGE_KEYS.token)
    return tok ? { Authorization: `Bearer ${tok}` } : {}
  } catch {
    return {}
  }
}

function buildUrl(path: string): string {
  if (/^https?:\/\//.test(path)) return path
  const p = path.startsWith("/") ? path : `/${path}`
  return `${BASE}${p}`
}

async function parseError(res: Response): Promise<never> {
  let body: unknown
  try {
    body = await res.json()
  } catch {
    body = await res.text().catch(() => null)
  }
  const detail =
    (body && typeof body === "object" && "detail" in body && (body as { detail: unknown }).detail) ||
    null
  const message =
    typeof detail === "string"
      ? detail
      : Array.isArray(detail)
        ? detail.map((d: { msg?: string }) => d?.msg).filter(Boolean).join("; ") ||
          `Request failed (${res.status})`
        : `Request failed (${res.status})`
  throw new ApiError(res.status, message, body)
}

export async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(buildUrl(path), { headers: authHeaders() })
  if (!res.ok) await parseError(res)
  return res.json() as Promise<T>
}

export async function apiPost<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(buildUrl(path), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  if (!res.ok) await parseError(res)
  if (res.status === 204) return undefined as T
  return res.json() as Promise<T>
}

export async function apiPut<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(buildUrl(path), {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  if (!res.ok) await parseError(res)
  if (res.status === 204) return undefined as T
  return res.json() as Promise<T>
}

export async function apiDelete<T = void>(path: string): Promise<T> {
  const res = await fetch(buildUrl(path), {
    method: "DELETE",
    headers: authHeaders(),
  })
  if (!res.ok) await parseError(res)
  if (res.status === 204) return undefined as T
  return res.json() as Promise<T>
}
