import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

function source(path: string): string {
  return readFileSync(resolve(process.cwd(), path), "utf8");
}

describe("R5 knowledge review plane", () => {
  it("adds a visible knowledge review entry and read-only queue", () => {
    const nav = source("components/nav-bar.tsx");
    const page = source("app/review/page.tsx");
    expect(nav).toContain("知识审核");
    expect(nav).toContain('href: "/review"');
    expect(page).toContain("待审核知识可见、可核对");
    expect(page).toContain("审核浏览层 ≠ 生产执行层");
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

  it("links hidden operational content to the separate review plane", () => {
    const detail = source("components/city-detail-client.tsx");
    expect(detail).toContain("数据未审核，禁止用于实际处置");
    expect(detail).toContain("进入知识审核（只读）");
    expect(detail).toContain("运营页面继续隐藏未核验数据");
  });

  it("states review visibility is not operational or AI eligibility", () => {
    const detail = source("components/review-city-detail-client.tsx");
    expect(detail).toContain("候选内容可读，但不可用于实际处置");
    expect(detail).toContain("AOG AI 仍不会把它作为 VERIFIED 上下文");
    expect(detail).toContain("R5 也不会在这里修改审核状态");
  });
});
