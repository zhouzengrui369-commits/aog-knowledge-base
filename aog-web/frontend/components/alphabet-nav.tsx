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

/** 字母导航 — 按首字母过滤点击城市跳详情 */
export function AlphabetNav({ cities, className }: Props) {
  // 按首字母分组（mockup 阶段用 name 第一个字符）
  const byAlpha = React.useMemo(() => {
    const map: Record<string, City[]> = {};
    for (const c of cities) {
      const k = firstLetter(c.name);
      (map[k] = map[k] || []).push(c);
    }
    return map;
  }, [cities]);

  return (
    <div className={cn("flex flex-wrap gap-1 scrollbar-thin", className)}>
      {ALPHA.map((letter) => {
        const list = byAlpha[letter] || [];
        const has = list.length > 0;
        return (
          <Link
            key={letter}
            href={has ? `/city/${encodeURIComponent(list[0].code)}` : "#"}
            aria-disabled={!has}
            tabIndex={has ? 0 : -1}
            data-empty={has ? "false" : "true"}
            className={cn(
              "alpha-btn grid h-9 w-9 place-items-center rounded-md border text-sm font-medium transition",
              has
                ? "border-ink-100 bg-white text-ink-700 hover:border-primary hover:bg-primary-50 hover:text-primary"
                : "border-transparent bg-transparent text-ink-300"
            )}
            onClick={(e) => {
              if (!has) e.preventDefault();
            }}
            title={has ? `跳转到 ${list[0].name}` : `${letter} 无数据`}
          >
            {letter}
          </Link>
        );
      })}
    </div>
  );
}
