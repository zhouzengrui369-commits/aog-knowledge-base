import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

function source(path: string): string {
  return readFileSync(resolve(process.cwd(), path), "utf8");
}

describe("R5 knowledge review and browsing policy", () => {
  it("adds a visible knowledge review entry and explains status-aware retrieval", () => {
    const nav = source("components/nav-bar.tsx");
    const page = source("app/review/page.tsx");
    expect(nav).toContain("知识审核");
    expect(nav).toContain('href: "/review"');
    expect(page).toContain("待审核知识可见、可检索、可核对");
    expect(page).toContain("知识可见 / AI 可检索 ≠ 已核验执行依据");
    expect(page).toContain("可供 AI 状态感知检索");
    expect(page).toContain("不提供一键批准、批量改状态或数据源写回");
  });

  it("keeps review candidate contacts read-only", () => {
    const candidate = source("components/review-candidate.tsx");
    expect(candidate).toContain("候选联系人");
    expect(candidate).toContain("非公开联系方式保持脱敏");
    expect(candidate).toContain("审核模式不提供 tel:/mailto: 操作入口");
    expect(candidate).not.toContain('href={`tel:');
    expect(candidate).not.toContain('href={`mailto:');
  });

  it("loads the authenticated candidate copy in normal knowledge browsing", () => {
    const detail = source("components/city-detail-client.tsx");
    const candidate = source("components/candidate-city-tabs.tsx");
    expect(detail).toContain("getReviewCity(found.code)");
    expect(detail).toContain("待核验知识，可浏览 / 可供 AI 检索");
    expect(detail).toContain("CandidateCityTabs");
    expect(candidate).toContain("待核验知识已展开");
    expect(candidate).toContain("可以浏览，也可以供 AI 检索");
    expect(candidate).toContain("实际处置前需要核验");
  });

  it("separates AI retrieval from operational authority on review detail", () => {
    const detail = source("components/review-city-detail-client.tsx");
    expect(detail).toContain("可读、可供 AI 检索，但尚不是已核验执行依据");
    expect(detail).toContain("AI 可以转述这份知识库记录");
    expect(detail).toContain("AI 检索");
    expect(detail).toContain("执行依据");
    expect(detail).toContain("R5 也不会在这里自动修改审核状态");
  });
});
