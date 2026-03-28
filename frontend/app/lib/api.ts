const FALLBACK_API_BASE = "http://localhost:8000";

export function getApiBaseUrl(): string {
  const envBase = process.env.NEXT_PUBLIC_API_BASE_URL?.trim();
  return envBase && envBase.length > 0 ? envBase.replace(/\/+$/, "") : FALLBACK_API_BASE;
}
