import { apiGet, apiPost } from "@/lib/api/client"

export type Quota = {
  used: number
  /** -1 = unlimited (Pro). */
  limit: number
  resets_at: string
}

export async function fetchQuota(): Promise<Quota> {
  return apiGet<Quota>("/me/quota")
}

export async function consumeQuota(): Promise<Quota> {
  return apiPost<Quota>("/me/quota/consume")
}
