"use client";

import * as React from "react";
import Link from "next/link";
import { cn, firstLetter } from "@/lib/utils";
import type { City } from "@/lib/types";

const ALPHA = "ABCDEFGHIJKLMNOPQRSTUVWXYZ".split("");

interface Props {
  cities: City[];
  className?: string;
}

/** 字母导航 — 点字母 in-page 展开该字母城市列表 */
export function AlphabetNav({ cities, className }: Props) {
  const [expanded, setExpanded] = React.useState<string | null>(null);

  // 按首字母分组
  const byAlpha = React.useMemo(() => {
    const map: Record<string, City[]> = {};
    for (const c of cities) {
      // 用 code 前缀（B-/S-/G-/C- ...）作为 Latin 首字母分组，
      // 城市 name 是中文，firstLetter(c.name) 会返回 CJK 字符导致所有按钮变灰
      const k = firstLetter(c.code);
      (map[k] = map[k] || []).push(c);
    }
    // 组内按 name 排序（中文 locale）
    for (const k of Object.keys(map)) {
      map[k].sort((a, b) => a.name.localeCompare(b.name, "zh-CN"));
    }
    return map;
  }, [cities]);

  // 点外部关闭
  React.useEffect(() => {
    if (!expanded) return;
    const handler = (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      if (!target.closest("[data-alpha-panel]") && !target.closest("[data-alpha-btn]")) {
        setExpanded(null);
      }
    };
    document.addEventListener("click", handler);
    return () => document.removeEventListener("click", handler);
  }, [expanded]);

  return (
    <div className={cn("space-y-3", className)}>
      {/* 字母按钮行 */}
      <div className="flex flex-wrap gap-1">
        {ALPHA.map((letter) => {
          const list = byAlpha[letter] || [];
          const has = list.length > 0;
          const isOpen = expanded === letter;
          return (
            <button
              key={letter}
              type="button"
              data-alpha-btn
              disabled={!has}
              onClick={() => has && setExpanded(isOpen ? null : letter)}
              aria-expanded={isOpen}
              className={cn(
                "alpha-btn grid h-9 w-9 place-items-center rounded-md border text-sm font-medium transition",
                has
                  ? isOpen
                    ? "border-primary bg-primary text-white"
                    : "border-ink-100 bg-white text-ink-700 hover:border-primary hover:bg-primary-50 hover:text-primary"
                  : "border-transparent bg-transparent text-ink-300"
              )}
              title={has ? `${letter} · ${list.length} 个城市` : `${letter} 无数据`}
            >
              {letter}
            </button>
          );
        })}
      </div>

      {/* 展开的城市列表 */}
      {expanded && byAlpha[expanded] && (
        <div
          data-alpha-panel
          className="rounded-md border border-ink-100 bg-white p-4 shadow-soft"
        >
          <div className="mb-3 flex items-center justify-between">
            <h3 className="text-sm font-medium text-ink-700">
              <span className="text-primary">{expanded}</span> 开头 · {byAlpha[expanded].length} 个城市
            </h3>
            <button
              onClick={() => setExpanded(null)}
              className="text-xs text-ink-500 hover:text-ink-900"
            >
              收起 ×
            </button>
          </div>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5">
            {byAlpha[expanded].map((c) => (
              <Link
                key={c.code}
                href={`/city/${encodeURIComponent(c.code)}`}
                className="rounded-md border border-ink-100 px-3 py-2 text-sm transition hover:border-primary hover:bg-primary-50"
              >
                <div className="truncate font-medium text-ink-900">{c.name}</div>
                <div className="truncate text-xs text-ink-500">
                  {c.iata && c.iata !== "—" ? `${c.iata} · ` : ""}
                  {c.region}
                </div>
              </Link>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
