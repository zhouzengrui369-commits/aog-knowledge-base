// API client — 1:1 对应 CONTRACT §2 端点
// 错误兜底：fetch 失败或后端未启动 → 降级到 lib/mock 数据
// ★ P1-2 治本: 5 个 mock fallback 场景有 isMockFallback 标志, UI 顶部红框 "演示数据" 提示
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

// ★ P1-2 治本: 5 个 mock fallback 场景计数 (写到 window 让 UI useEffect 监听)
function _recordMockFallback(path: string) {
  _mockFallbackCount++;
  if (typeof window !== "undefined") {
    const w = window as any;
    if (!w.__aogMockFallback) w.__aogMockFallback = new Set<string>();
    w.__aogMockFallback.add(path);
  }
}
let _mockFallbackCount = 0;
export function getMockFallbackCount() { return _mockFallbackCount; }
export function resetMockFallbackCount() { _mockFallbackCount = 0; }
export function getMockFallbackPaths(): string[] {
  if (typeof window === "undefined") return [];
  const w = window as any;
  if (!w.__aogMockFallback) return [];
  return Array.from(w.__aogMockFallback) as string[];
}

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
  // 降级 mock — ★ P1-2 治本: 记录到全局 set, UI 端读 set 显红框
  _recordMockFallback("/api/cities");
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
  // ★ P1-2 治本: 记录 mock fallback
  _recordMockFallback(`/api/city/${encoded}`);
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
  // ★ P1-2 治本: 记录 mock fallback
  _recordMockFallback("/api/experiences");
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
  // ★ P1-2 治本: 记录 mock fallback
  _recordMockFallback(`/api/experience/${encodeURIComponent(id)}`);
  return MOCK_EXPERIENCES.find((e) => e.id === id) || null;
}

/** 核心预案 (CONTRACT §2.6) */
export async function getCorePlans(): Promise<CorePlan[]> {
  const data = await safeFetch<CorePlan[]>(`/api/core-plans`);
  if (data) return data;
  // ★ P1-2 治本: 记录 mock fallback
  _recordMockFallback("/api/core-plans");
  return [];
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
  if (data) return data;
  // ★ P1-2 治本: 记录 mock fallback (chat 走 null 时不返 mock, 改返 null 让 UI 显错)
  _recordMockFallback("/api/chat");
  return null;
}

/** 流式 chat (SSE) — NJX 7/27 15:44 反馈 AI 答案要打字机效果
 *
 *  V30 (NJX 7/27 22:14 拍板 🅰️): 后端 /api/chat/stream emit 4 类 SSE event:
 *    1. event: refs       data: {references, model}              ← 立刻返, 不等 LLM
 *    2. event: token      data: {content_delta}                   ← LLM 每 yield 一段就 emit
 *    3. event: sections   data: {sections: ChatSection[]}        ← LLM 流完后, parser 解析成功才 emit (V30 治本)
 *    4. event: done       data: {latency_ms}                      ← 结束
 *    5. event: error      data: {error}                           ← 异常
 *
 *  回调:
 *    onRefs({references, model})                     ← event=refs 触发
 *    onToken(delta)                                  ← event=token 触发 (前端逐字渲染)
 *    onSections(sections)                            ← event=sections 触发 (V30: 切到结构化渲染)
 *    onDone(latency_ms)                              ← event=done 触发
 *    onError(message)                                ← event=error 或 fetch 失败触发
 */
export interface ChatStreamCallbacks {
  onRefs?: (refs: { references: ChatResponse["references"]; model: string }) => void;
  onToken?: (delta: string) => void;
  onSections?: (sections: NonNullable<ChatResponse["sections"]>) => void;
  onDone?: (latencyMs: number) => void;
  onError?: (message: string) => void;
}

export async function chatStream(req: ChatRequest, cbs: ChatStreamCallbacks): Promise<void> {
  const ac = new AbortController();
  const timeout = setTimeout(() => ac.abort(), 90000);  // 90s 总超时
  try {
    const res = await fetch(`${BASE}/api/chat/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(req),
      signal: ac.signal,
    });
    if (!res.ok || !res.body) {
      cbs.onError?.(`HTTP ${res.status}`);
      return;
    }
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      // 按 \n\n 切 SSE event
      let idx: number;
      while ((idx = buffer.indexOf("\n\n")) !== -1) {
        const raw = buffer.slice(0, idx);
        buffer = buffer.slice(idx + 2);
        // 解析 event: ... \ndata: ...
        let event = "message";
        let dataStr = "";
        for (const line of raw.split("\n")) {
          if (line.startsWith("event:")) {
            event = line.slice(6).trim();
          } else if (line.startsWith("data:")) {
            dataStr += line.slice(5).trim();
          }
        }
        if (!dataStr) continue;
        if (event === "refs") {
          try {
            const payload = JSON.parse(dataStr);
            cbs.onRefs?.({
              references: payload.references || [],
              model: payload.model || "unknown",
            });
          } catch (e) {
            console.warn("[chatStream] refs parse failed:", e);
          }
        } else if (event === "token") {
          cbs.onToken?.(dataStr);
        } else if (event === "sections") {
          // V30 治本: 后端 parser 解析成功, emit sections 数组
          // 前端拿到后用 React 组件渲染, 覆盖之前流式 markdown 显示
          try {
            const payload = JSON.parse(dataStr);
            if (Array.isArray(payload.sections)) {
              cbs.onSections?.(payload.sections as NonNullable<ChatResponse["sections"]>);
            }
          } catch (e) {
            console.warn("[chatStream] sections parse failed:", e);
          }
        } else if (event === "done") {
          try {
            const payload = JSON.parse(dataStr);
            cbs.onDone?.(payload.latency_ms || 0);
          } catch {
            cbs.onDone?.(0);
          }
        } else if (event === "error") {
          try {
            const payload = JSON.parse(dataStr);
            cbs.onError?.(payload.error || "unknown error");
          } catch {
            cbs.onError?.(dataStr);
          }
        }
      }
    }
  } catch (err) {
    cbs.onError?.(err instanceof Error ? err.message : String(err));
  } finally {
    clearTimeout(timeout);
  }
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
  // ★ P1-2 治本: 记录 mock fallback
  _recordMockFallback("/api/airlines");
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
  // ★ P1-2 治本: 记录 mock fallback
  _recordMockFallback(`/api/airlines/${encodeURIComponent(code)}`);
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
  // ★ P1-2 治本: 记录 mock fallback
  _recordMockFallback("/api/airlines/search");
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
