import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

function source(path: string): string {
  return readFileSync(resolve(process.cwd(), path), "utf8");
}

describe("AOG production UI contracts", () => {
  it("uses live statistics and removes false experience counts", () => {
    const runtime = [
      source("components/hero.tsx"),
      source("app/home-data.tsx"),
      source("app/not-found.tsx"),
      source("app/experiences/page.tsx"),
    ].join("\n");
    expect(runtime).not.toContain("18 份实战经验");
    expect(runtime).not.toContain("18 个实战经验");
    expect(runtime).not.toContain("8686 条知识片段");
    expect(runtime).toContain("getProductionStats");
  });

  it("does not hardcode the wrong airport on the 404 page", () => {
    const text = source("app/not-found.tsx");
    expect(text).not.toContain("PKX · 华东");
    expect(text).not.toContain("上海浦东</div>");
    expect(text).toContain("getCities");
    expect(text).toContain("getExperiences");
  });

  it("keeps unfinished course versions out of navigation", () => {
    const text = source("components/nav-bar.tsx");
    expect(text).not.toContain("课件");
    expect(text).not.toContain(">v2<");
  });

  it("never renders model chain-of-thought in production", () => {
    const text = source("components/chat-widget.tsx");
    expect(text).toContain("DEBUG_THOUGHTS");
    expect(text).toContain("stripPrivateProtocol");
    expect(text).not.toContain("思考中");
    expect(text).not.toContain("思考过程");
    expect(text).not.toContain("dangerouslySetInnerHTML");
  });

  it("keeps exactly one global and one inline AI entry", () => {
    const layout = source("app/layout.tsx");
    const hero = source("components/hero.tsx");
    const city = source("components/city-detail-client.tsx");
    const experience = source("app/experience/[id]/page.tsx");
    const list = source("app/experiences/list-client.tsx");
    expect((layout.match(/<ChatWidget/g) || []).length).toBe(1);
    expect(hero).toContain("aog:ask");
    expect(city).not.toContain("aog:ask");
    expect(experience).not.toContain("问 AI");
    expect(list).not.toContain("用 AI 总结");
  });

  it("fails closed for unverified city data and defines SLA ownership", () => {
    const detail = source("components/city-detail-client.tsx");
    const tabs = source("components/city-tabs.tsx");
    expect(detail).toContain("数据未审核，禁止用于实际处置");
    expect(detail).toContain("执行责任方：当班航材 AOG 工程师");
    expect(detail).toContain("不代表航司、机场、供应商或本平台对外 SLA");
    expect(tabs).toContain("city.data_available !== false");
    expect(tabs).toContain("重复记录已按单位、电话、邮箱和职责去重");
  });

  it("uses cookie authentication instead of localStorage credentials", () => {
    const text = source("components/auth-gate.tsx");
    expect(text).toContain('credentials: "include"');
    expect(text).not.toContain("localStorage");
    expect(text).toContain("sessionStorage");
  });

  it("removes static access-count fallback", () => {
    const text = source("lib/city-stats.ts");
    expect(text).not.toContain("data.view_count");
    expect(text).toContain("right.view_count");
    expect(text).toContain("left.view_count");
  });
});
