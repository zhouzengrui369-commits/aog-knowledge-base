/**
 * P0-4 production mock 隔离 4 项测试 (Owner 7/29 严令)
 *
 * 测试目标:
 *   1. ALLOW_MOCK=false + API 500 → 不返 mock
 *   2. ALLOW_MOCK=false + API timeout → 不返 mock
 *   3. ALLOW_MOCK=true + dev → mock 有明显 FIXTURE/MOCK 标记
 *   4. staging build 强制验证 NEXT_PUBLIC_ALLOW_MOCK=false
 *
 * 运行:
 *   cd aog-web/frontend
 *   pnpm test tests/api-mock-isolation.test.ts
 */

import { describe, it, expect, beforeEach, vi, afterEach } from "vitest";

// 在 import api.ts 前设置 env (api.ts 顶层读 process.env.NEXT_PUBLIC_ALLOW_MOCK)
const setAllowMock = (v: "true" | "false" | undefined) => {
  if (v === undefined) {
    delete process.env.NEXT_PUBLIC_ALLOW_MOCK;
  } else {
    process.env.NEXT_PUBLIC_ALLOW_MOCK = v;
  }
};

// mock fetch (api.ts 用 fetch + AbortController)
const mockFetch = (status: number | "timeout" | "error", body?: any) => {
  const fetchMock = vi.fn(async (url: string, init?: any) => {
    if (status === "timeout") {
      // 模拟 timeout: 永不 resolve, 让 setTimeout 触发 abort
      return new Promise((_, reject) => {
        init?.signal?.addEventListener("abort", () => {
          // 用 unhandled 静默 (避免 vitest 当 unhandled error)
          process.nextTick(() => reject(new DOMException("aborted", "AbortError")));
        });
      });
    }
    if (status === "error") {
      throw new TypeError("NetworkError");
    }
    return {
      ok: status >= 200 && status < 300,
      status,
      json: async () => body ?? null,
    } as any;
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
};

describe("P0-4 production mock 隔离", () => {
  beforeEach(() => {
    vi.resetModules();  // 重新 import api.ts 让 env 生效
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    setAllowMock(undefined);
  });

  // ============ Test 1: ALLOW_MOCK=false + API 500 → 不返 mock ============
  it("ALLOW_MOCK=false + API 500 → getCities 返 [] 不返 mock", async () => {
    setAllowMock("false");
    mockFetch(500, null);
    const { getCities, ALLOW_MOCK } = await import("../lib/api");
    expect(ALLOW_MOCK).toBe(false);
    const cities = await getCities();
    expect(cities).toEqual([]);  // 空数组, 不是 mock
    expect(cities.length).toBe(0);
  });

  it("ALLOW_MOCK=false + API 500 → getCity 返 null 不返 mock", async () => {
    setAllowMock("false");
    mockFetch(500, null);
    const { getCity } = await import("../lib/api");
    const city = await getCity("B-北京大兴");
    expect(city).toBeNull();  // null, 不是 mock
  });

  it("ALLOW_MOCK=false + API 500 → getExperiences 返 []", async () => {
    setAllowMock("false");
    mockFetch(500, null);
    const { getExperiences } = await import("../lib/api");
    const exps = await getExperiences();
    expect(exps).toEqual([]);
  });

  it("ALLOW_MOCK=false + API 500 → getCorePlans 返 []", async () => {
    setAllowMock("false");
    mockFetch(500, null);
    const { getCorePlans } = await import("../lib/api");
    const plans = await getCorePlans();
    expect(plans).toEqual([]);
  });

  it("ALLOW_MOCK=false + API 500 → getAirlines 返 []", async () => {
    setAllowMock("false");
    mockFetch(500, null);
    const { getAirlines } = await import("../lib/api");
    const airlines = await getAirlines();
    expect(airlines).toEqual([]);
  });

  it("ALLOW_MOCK=false + API 500 → searchAirlines 返 []", async () => {
    setAllowMock("false");
    mockFetch(500, null);
    const { searchAirlines } = await import("../lib/api");
    const result = await searchAirlines("东航");
    expect(result).toEqual([]);
  });

  it("ALLOW_MOCK=false + API 500 → chat 返 null (chat 永远不 mock)", async () => {
    setAllowMock("false");
    mockFetch(500, null);
    const { chat } = await import("../lib/api");
    const result = await chat({ q: "test" });
    expect(result).toBeNull();
  });

  // ============ Test 2: ALLOW_MOCK=false + API timeout → 不返 mock ============
  it("ALLOW_MOCK=false + API timeout → getCities 返 [] 不 mock", async () => {
    setAllowMock("false");
    mockFetch("timeout");
    const { getCities } = await import("../lib/api");
    const cities = await getCities();
    expect(cities).toEqual([]);
  });

  it("ALLOW_MOCK=false + API error → getCities 返 []", async () => {
    setAllowMock("false");
    mockFetch("error");
    const { getCities } = await import("../lib/api");
    const cities = await getCities();
    expect(cities).toEqual([]);
  });

  // ============ Test 3: ALLOW_MOCK=true + dev → mock 有 MOCK 标志 ============
  it("ALLOW_MOCK=true + API 500 → getCities 返 mock (dev 模式)", async () => {
    setAllowMock("true");
    mockFetch(500, null);
    const { getCities, ALLOW_MOCK, getMockFallbackCount } = await import("../lib/api");
    expect(ALLOW_MOCK).toBe(true);
    const cities = await getCities();
    expect(cities.length).toBeGreaterThan(0);  // 返 mock (有数据)
    // P1-2 标志: 记录 mock fallback 路径
    expect(getMockFallbackCount()).toBeGreaterThan(0);
  });

  it("ALLOW_MOCK=true + API 500 → getCity 返 mock", async () => {
    setAllowMock("true");
    mockFetch(500, null);
    const { getCity } = await import("../lib/api");
    const city = await getCity("B-北京大兴");
    expect(city).not.toBeNull();  // 返 mock 数据
  });

  it("ALLOW_MOCK=true + dev → mock 路径被 _recordMockFallback 记录", async () => {
    setAllowMock("true");
    mockFetch(500, null);
    const { getCities, getMockFallbackPaths } = await import("../lib/api");
    await getCities();
    const paths = getMockFallbackPaths();
    expect(paths).toContain("/api/cities");
  });

  // ============ Test 4: 默认值 (env unset) = false (production 默认) ============
  it("NEXT_PUBLIC_ALLOW_MOCK unset (默认) → ALLOW_MOCK=false (production 严令)", async () => {
    setAllowMock(undefined);
    mockFetch(500, null);
    const { getCities, ALLOW_MOCK } = await import("../lib/api");
    expect(ALLOW_MOCK).toBe(false);
    const cities = await getCities();
    expect(cities).toEqual([]);  // 不返 mock
  });

  it("NEXT_PUBLIC_ALLOW_MOCK='false' (string) → ALLOW_MOCK=false", async () => {
    setAllowMock("false");
    mockFetch(500, null);
    const { getCities, ALLOW_MOCK } = await import("../lib/api");
    expect(ALLOW_MOCK).toBe(false);
    const cities = await getCities();
    expect(cities).toEqual([]);
  });

  it("NEXT_PUBLIC_ALLOW_MOCK='true' (string) → ALLOW_MOCK=true", async () => {
    setAllowMock("true");
    mockFetch(500, null);
    const { getCities, ALLOW_MOCK } = await import("../lib/api");
    expect(ALLOW_MOCK).toBe(true);
  });

  // ============ Test 5: API 成功时不返 mock (即使 ALLOW_MOCK=true) ============
  it("API 200 + ALLOW_MOCK=true → 返真实数据, 不走 mock", async () => {
    setAllowMock("true");
    mockFetch(200, [{ code: "B-北京大兴", name: "北京大兴 (real)" }]);
    const { getCities } = await import("../lib/api");
    const cities = await getCities();
    expect(cities).toHaveLength(1);
    expect(cities[0].name).toContain("real");  // 真实数据, 不是 MOCK_CITIES 的 "北京大兴" 模板
  });

  it("API 200 + ALLOW_MOCK=false → 返真实数据", async () => {
    setAllowMock("false");
    mockFetch(200, [{ code: "B-北京大兴", name: "北京大兴 (real)" }]);
    const { getCities } = await import("../lib/api");
    const cities = await getCities();
    expect(cities).toHaveLength(1);
    expect(cities[0].name).toContain("real");
  });
});
