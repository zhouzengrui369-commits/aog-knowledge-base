import { describe, expect, it } from "vitest";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const TEST_DIR = dirname(fileURLToPath(import.meta.url));
const FRONTEND_ROOT = resolve(TEST_DIR, "..");
const DETAIL_PAGE = join(FRONTEND_ROOT, "app", "experience", "[id]", "page.tsx");

function productionSourceFiles(root: string): string[] {
  const files: string[] = [];
  for (const name of readdirSync(root)) {
    const path = join(root, name);
    const stat = statSync(path);
    if (stat.isDirectory()) {
      files.push(...productionSourceFiles(path));
    } else if (/\.(ts|tsx|js|jsx)$/.test(name) && !name.endsWith(".test.ts")) {
      files.push(path);
    }
  }
  return files;
}

describe("P0-1 experience content integrity", () => {
  it("renders API content_md instead of an empty article shell", () => {
    const source = readFileSync(DETAIL_PAGE, "utf8");
    expect(source).toContain('parseContent(exp.content_md || "")');
    expect(source).toContain("<ExperienceContentView sections={sections} />");
  });

  it("keeps development diagnostics behind NEXT_PUBLIC_DEBUG", () => {
    const source = readFileSync(DETAIL_PAGE, "utf8");
    expect(source).toContain('process.env.NEXT_PUBLIC_DEBUG === "true"');
    expect(source).not.toContain("build 时跳过");
  });

  it("contains no production developer markers", () => {
    const roots = [
      join(FRONTEND_ROOT, "app"),
      join(FRONTEND_ROOT, "components"),
      join(FRONTEND_ROOT, "lib"),
    ];
    const violations: string[] = [];
    const marker = /build 时跳过|\bTODO\b|\bPLACEHOLDER\b/g;

    for (const root of roots) {
      for (const file of productionSourceFiles(root)) {
        const source = readFileSync(file, "utf8");
        if (marker.test(source)) violations.push(file.replace(FRONTEND_ROOT, ""));
        marker.lastIndex = 0;
      }
    }

    expect(violations).toEqual([]);
  });
});
