/**
 * P0-4 production mock 隔离测试用例。
 *
 * 由 api-mock-isolation.test.ts 统一导入，使定向 CI 入口可以同时注册
 * mock 隔离和后续 P0 回归，而不会在全量 Vitest 时重复发现本文件。
 */
import { describe, it, expect, beforeEach, vi, afterEach } from "vitest";

const setAllowMock = (v: "true" | "false" | undefined) => {
  if (v === undefined) {
    delete process.env.NEXT_PUBLIC_ALLOW_MOCK;
  } else {
    process.env.NEXT_PUBLIC_ALLOW_MOCK = v;
  }
};

const mockFetch = (status: number | "timeout" | "error", body?: any) => {
  const fetchMock = vi.fn(async (url: string, init?: any) => {
    if (status === "timeout") {
      return new Promise((_, reject) => {
        init?.signal?.addEventListener("abort", () => {
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
    vi.resetModules();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    setAllowMock(undefined);
  });

  it("ALLOW_MOCK=false + API 500 → getCities 返 [] 不返 mock", async () => {
    setAllowMock("false");
    mockFetch(500, null);
    const { getCities, ALLOW_MOCK } = await import("../lib/api");
    expect(ALLOW_MOCK).toBe(false);
    const cities = await getCities();
    expect(cities).toEqual([]);
    expect(cities.length).toBe(0);
  });

  it("ALLOW_MOCK=false + API 500 → getCity 返 null 不返 mock", async () => {
    setAllowMock("false");
    mockFetch(500, null);
    const { getCity } = await import("../lib/api");
    const city = await getCity("B-北京大兴");
    expect(city).toBeNull();
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

  it("ALLOW_MOCK=false + API 500 → chat 返 null", async () => {
    setAllowMock("false");
    mockFetch(500, null);
    const { chat } = await import("../lib/api");
    const result = await chat({ q: "test" });
    expect(result).toBeNull();
  });

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

  it("ALLOW_MOCK=true + API 500 → getCities 返 mock", async () => {
    setAllowMock("true");
    mockFetch(500, null);
    const { getCities, ALLOW_MOCK, getMockFallbackCount } = await import("../lib/api");
    expect(ALLOW_MOCK).toBe(true);
    const cities = await getCities();
    expect(cities.length).toBeGreaterThan(0);
    expect(getMockFallbackCount()).toBeGreaterThan(0);
  });

  it("ALLOW_MOCK=true + API 500 → getCity 返 mock", async () => {
    setAllowMock("true");
    mockFetch(500, null);
    const { getCity } = await import("../lib/api");
    const city = await getCity("B-北京大兴");
    expect(city).not.toBeNull();
  });

  it("ALLOW_MOCK=true + dev → mock 路径被记录", async () => {
    setAllowMock("true");
    mockFetch(500, null);
    const { getCities, getMockFallbackPaths } = await import("../lib/api");
    await getCities();
    const paths = getMockFallbackPaths();
    expect(paths).toContain("/api/cities");
  });

  it("NEXT_PUBLIC_ALLOW_MOCK unset → production 默认 false", async () => {
    setAllowMock(undefined);
    mockFetch(500, null);
    const { getCities, ALLOW_MOCK } = await import("../lib/api");
    expect(ALLOW_MOCK).toBe(false);
    const cities = await getCities();
    expect(cities).toEqual([]);
  });

  it("NEXT_PUBLIC_ALLOW_MOCK='false' → ALLOW_MOCK=false", async () => {
    setAllowMock("false");
    mockFetch(500, null);
    const { getCities, ALLOW_MOCK } = await import("../lib/api");
    expect(ALLOW_MOCK).toBe(false);
    const cities = await getCities();
    expect(cities).toEqual([]);
  });

  it("NEXT_PUBLIC_ALLOW_MOCK='true' → ALLOW_MOCK=true", async () => {
    setAllowMock("true");
    mockFetch(500, null);
    const { ALLOW_MOCK } = await import("../lib/api");
    expect(ALLOW_MOCK).toBe(true);
  });

  it("API 200 + ALLOW_MOCK=true → 返真实数据", async () => {
    setAllowMock("true");
    mockFetch(200, [{ code: "B-北京大兴", name: "北京大兴 (real)" }]);
    const { getCities } = await import("../lib/api");
    const cities = await getCities();
    expect(cities).toHaveLength(1);
    expect(cities[0].name).toContain("real");
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
