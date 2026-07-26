// API client — 1:1 对应 CONTRACT §2 端点
// 错误兜底：fetch 失败或后端未启动 → 降级到 lib/mock 数据
// 验证：Lighthouse 测试时需 NEXT_PUBLIC_API_BASE=http://localhost:8000

import type {
  City,
  Experience,
  ChatRequest,
  ChatResponse,
  CorePlan,
  SyncStatus,
  Airline,
  Airport,
  GlobalAirportsData,
} from "@/lib/types";
import { MOCK_CITIES } from "@/lib/mock/cities";
import { MOCK_EXPERIENCES } from "@/lib/mock/experiences";
import { MOCK_AIRLINES } from "@/lib/mock/airlines";

// ★ P0-1 治本: BASE 必须去尾 /api, 否则 ${BASE}/api/cities 拼成 /api/api/cities 返 400
//   公网 NEXT_PUBLIC_API_BASE=https://...service.tcloudbase.com/api
//   localhost 模式 NEXT_PUBLIC_API_BASE=http://localhost:8000 (无 /api)
//   两种情况都 .replace(/\/api\/?$/, "") 安全去尾
const BASE = (process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000")
  .replace(/\/api\/?$/, "");

/** fetch 包装：超时 + 错误捕获 */
async function safeFetch<T>(
  path: string,
  init?: RequestInit & { timeoutMs?: number }
): Promise<T | null> {
  const { timeoutMs = 4000, ...rest } = init || {};
  const ac = new AbortController();
  const t = setTimeout(() => ac.abort(), timeoutMs);
  try {
    const res = await fetch(`${BASE}${path}`, {
      ...rest,
      signal: ac.signal,
      headers: { "Content-Type": "application/json", ...(rest?.headers || {}) },
    });
    if (!res.ok) {
      console.warn(`[api] ${path} → HTTP ${res.status}`);
      return null;
    }
    return (await res.json()) as T;
  } catch (err) {
    // 静默降级 — 不污染服务器日志
    console.warn(`[api] ${path} failed:`, err instanceof Error ? err.message : err);
    return null;
  } finally {
    clearTimeout(t);
  }
}

/** 城市列表 — 支持 region/status/letter 过滤 (CONTRACT §2.2) */
export async function getCities(params?: {
  region?: string;
  status?: string;
  letter?: string;
}): Promise<City[]> {
  const qs = new URLSearchParams();
  if (params?.region) qs.set("region", params.region);
  if (params?.status) qs.set("status", params.status);
  if (params?.letter) qs.set("letter", params.letter);
  const q = qs.toString() ? `?${qs}` : "";
  const data = await safeFetch<City[]>(`/api/cities${q}`);
  // dev backend 返空数组时也 fallback 到 MOCK (避免 dev 看到 0 城市)
  if (data && data.length > 0) return data;
  // 降级 mock
  let list = [...MOCK_CITIES];
  if (params?.region) list = list.filter((c) => c.region === params.region);
  if (params?.status) list = list.filter((c) => c.status === params.status);
  if (params?.letter) {
    const letter = params.letter.toUpperCase();
    list = list.filter((c) => c.name.charAt(0).toUpperCase() === letter);
  }
  return list;
}

/** 城市详情 (CONTRACT §2.3) — code URL-encoded */
export async function getCity(code: string): Promise<City | null> {
  const encoded = encodeURIComponent(code);
  const data = await safeFetch<City>(`/api/city/${encoded}`);
  if (data) return data;
  return MOCK_CITIES.find((c) => c.code === code) || null;
}

/** 经验列表 (CONTRACT §2.4) */
export async function getExperiences(params?: {
  category?: string;
  status?: string;
  q?: string;
}): Promise<Experience[]> {
  const qs = new URLSearchParams();
  if (params?.category) qs.set("category", params.category);
  if (params?.status) qs.set("status", params.status);
  if (params?.q) qs.set("q", params.q);
  const q = qs.toString() ? `?${qs}` : "";
  const data = await safeFetch<Experience[]>(`/api/experiences${q}`);
  // dev backend 返空数组时 fallback MOCK
  if (data && data.length > 0) return data;
  let list = [...MOCK_EXPERIENCES];
  if (params?.category) list = list.filter((e) => e.category === params.category || e.topic === params.category);
  if (params?.status) list = list.filter((e) => e.status === params.status);
  if (params?.q) {
    const k = params.q.toLowerCase();
    list = list.filter(
      (e) =>
        e.title.toLowerCase().includes(k) ||
        e.summary.toLowerCase().includes(k) ||
        (e.tags || []).some((t) => t.toLowerCase().includes(k))
    );
  }
  return list;
}

/** 经验详情 (CONTRACT §2.5) */
export async function getExperience(id: string): Promise<Experience | null> {
  const data = await safeFetch<Experience>(`/api/experience/${encodeURIComponent(id)}`);
  if (data) return data;
  return MOCK_EXPERIENCES.find((e) => e.id === id) || null;
}

/** 核心预案 (CONTRACT §2.6) */
export async function getCorePlans(): Promise<CorePlan[]> {
  const data = await safeFetch<CorePlan[]>(`/api/core-plans`);
  return data || [];
}

/** AI 对话 (CONTRACT §2.7) — 必须 references.length >= 1 (NSM-2)
 *  chat 单独 timeoutMs=30000 (LLM cold start warmed 偶发 4-10s, 30s 安全)。
 *  其他 endpoint 仍用 safeFetch 4000 default (lib/api.ts safeFetch 签名不动)。
 */
export async function chat(req: ChatRequest): Promise<ChatResponse | null> {
  const data = await safeFetch<ChatResponse>(`/api/chat`, {
    method: "POST",
    body: JSON.stringify(req),
    timeoutMs: 30000,
  });
  return data;
}

/** 同步状态 (CONTRACT §2.9) */
export async function getSyncStatus(): Promise<SyncStatus | null> {
  return safeFetch<SyncStatus>(`/api/sync/status`);
}

/** 健康检查 (CONTRACT §2.1) */
export async function health(): Promise<{ status: string; version?: string } | null> {
  return safeFetch(`/api/health`);
}

// ===== Sprint C: 航司 (Airlines) =====

/** 航司列表 — 支持 letter/alliance/hub 过滤 */
export async function getAirlines(params?: {
  letter?: string;
  alliance?: string;
  hub?: string;
}): Promise<Airline[]> {
  const qs = new URLSearchParams();
  if (params?.letter) qs.set("letter", params.letter);
  if (params?.alliance) qs.set("alliance", params.alliance);
  if (params?.hub) qs.set("hub", params.hub);
  const q = qs.toString() ? `?${qs}` : "";
  const data = await safeFetch<Airline[]>(`/api/airlines${q}`);
  // dev backend 返空数组时 fallback MOCK
  if (data && data.length > 0) return data;
  // 降级 mock
  let list = [...MOCK_AIRLINES];
  if (params?.letter) {
    const l = params.letter.toUpperCase();
    list = list.filter(
      (a) => a.iata.toUpperCase().startsWith(l) || a.name_cn.startsWith(l)
    );
  }
  if (params?.alliance) list = list.filter((a) => a.alliance === params.alliance);
  return list;
}

/** 航司详情 — IATA 2-letter code (大写) */
export async function getAirline(iata: string): Promise<Airline | null> {
  if (!iata) return null;
  const code = iata.toUpperCase();
  const data = await safeFetch<Airline>(`/api/airlines/${encodeURIComponent(code)}`);
  if (data) return data;
  return MOCK_AIRLINES.find((a) => a.iata === code) || null;
}

/** 航司模糊搜索 — IATA / ICAO / 中文名 / 英文名 / 常用简称 */
export async function searchAirlines(q: string, limit = 20): Promise<Airline[]> {
  if (!q || !q.trim()) return [];
  const data = await safeFetch<Airline[]>(
    `/api/airlines/search?q=${encodeURIComponent(q)}&limit=${limit}`
  );
  // dev backend 返空数组时 fallback MOCK
  if (data && data.length > 0) return data;
  // 降级 mock
  const k = q.trim().toLowerCase();
  return MOCK_AIRLINES.filter((a) => {
    const haystack = `${a.iata} ${a.icao} ${a.name_cn} ${a.name_en} ${a.name_short || ""}`.toLowerCase();
    return haystack.includes(k);
  }).slice(0, limit);
}

// ===== V20: 全球机场（OpenFlights） =====

/** V20 进程内缓存 — 避免每次组件 mount 都 fetch 700KB JSON */
let _airportsCache: Airport[] | null = null;
let _byCountryCache: Record<string, number> | null = null;
let _airportsPromise: Promise<Airport[]> | null = null;

/** 静态 fetch /data/global-airports.json（public/ 静态资源） */
export async function getAirports(): Promise<Airport[]> {
  if (_airportsCache) return _airportsCache;
  if (_airportsPromise) return _airportsPromise;
  _airportsPromise = (async () => {
    try {
      const res = await fetch("/data/global-airports.json", { cache: "force-cache" });
      if (!res.ok) {
        console.warn(`[api] /data/global-airports.json → HTTP ${res.status}`);
        return [];
      }
      const data = (await res.json()) as GlobalAirportsData;
      _airportsCache = data.airports;
      _byCountryCache = data.by_country;
      return data.airports;
    } catch (err) {
      console.warn(`[api] /data/global-airports.json failed:`, err);
      return [];
    } finally {
      _airportsPromise = null;
    }
  })();
  return _airportsPromise;
}

/** 按国家筛机场 */
export async function getAirportsByCountry(country: string): Promise<Airport[]> {
  const all = await getAirports();
  return all.filter((a) => a.country === country);
}

/** 取 by_country 统计（懒加载, 第一次 getAirports 后才有） */
export function getByCountryCounts(): Record<string, number> {
  return _byCountryCache || {};
}
