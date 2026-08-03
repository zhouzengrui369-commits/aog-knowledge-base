const BASE = (process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000").replace(/\/api\/?$/, "");

export interface ProductionStats {
  cities: number;
  mapped_cities: number;
  experiences: number;
  core_plans: number;
  airlines: number;
  knowledge_chunks: number;
  verified_cities: number;
  unverified_cities: number;
  total_city_views: number;
  source: "sqlite";
}

export async function productionFetch<T>(path: string, timeoutMs = 5000): Promise<T | null> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(`${BASE}${path}`, {
      credentials: "include",
      cache: "no-store",
      signal: controller.signal,
      headers: { Accept: "application/json" },
    });
    return response.ok ? (await response.json()) as T : null;
  } catch {
    return null;
  } finally {
    window.clearTimeout(timeout);
  }
}

export function getProductionStats(): Promise<ProductionStats | null> {
  return productionFetch<ProductionStats>("/api/stats");
}
