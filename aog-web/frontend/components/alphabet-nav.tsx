"use client";

import * as React from "react";
import Link from "next/link";
import { ChevronDown, X } from "lucide-react";
import { cn, firstLetter } from "@/lib/utils";
import type { City } from "@/lib/types";

const ALPHA = "ABCDEFGHIJKLMNOPQRSTUVWXYZ".split("");

interface Props {
  cities: City[];
  className?: string;
  /**
   * horizontal (默认): 26 字母横向单行, in-page 展开
   * sidebar: 4 列紧凑 grid, 用作地图侧栏缩略
   */
  mode?: "horizontal" | "sidebar";
  /** 父级控制的 hover 状态 — 用于和地图同步高亮 */
  hoveredLetter?: string | null;
  onLetterHover?: (letter: string | null) => void;
}

/**
 * 字母导航（Vercel / Linear 风格）
 *  - horizontal: 26 字母横向单行 + in-page 展开城市列表
 *  - sidebar:    4 列紧凑 grid + 下方滚动展开（适配 unified 视图侧栏）
 *  - hover 字母: 通过 onLetterHover 通知父级（用于地图同步 pulse）
 */
export function AlphabetNav({
  cities,
  className,
  mode = "horizontal",
  hoveredLetter,
  onLetterHover,
}: Props) {
  const [expanded, setExpanded] = React.useState<string | null>(null);

  const byAlpha = React.useMemo(() => {
    const map: Record<string, City[]> = {};
    for (const c of cities) {
      const k = firstLetter(c.code);
      (map[k] = map[k] || []).push(c);
    }
    for (const k of Object.keys(map)) {
      map[k].sort((a, b) => a.name.localeCompare(b.name, "zh-CN"));
    }
    return map;
  }, [cities]);

  const totalWith = ALPHA.filter((l) => (byAlpha[l] || []).length > 0).length;
  const activeLetter = expanded && byAlpha[expanded] ? expanded : null;
  const isExternalHover = (l: string) =>
    hoveredLetter != null && l === hoveredLetter;

  // sidebar 模式下点开字母时, 自动滚动展开区域到可见
  const panelRef = React.useRef<HTMLDivElement | null>(null);
  React.useEffect(() => {
    if (mode === "sidebar" && expanded && panelRef.current) {
      panelRef.current.scrollIntoView({
        behavior: "smooth",
        block: "nearest",
      });
    }
  }, [expanded, mode]);

  // 点击外部关闭 (horizontal 模式, sidebar 模式让父级布局管)
  React.useEffect(() => {
    if (mode !== "horizontal" || !expanded) return;
    const handler = (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      if (!target.closest("[data-alpha-panel]") && !target.closest("[data-alpha-btn]")) {
        setExpanded(null);
      }
    };
    document.addEventListener("click", handler);
    return () => document.removeEventListener("click", handler);
  }, [expanded, mode]);

  // ---------- Sidebar 模式 ----------
  if (mode === "sidebar") {
    return (
      <div className={cn("flex h-full flex-col", className)}>
        {/* header */}
        <div className="mb-3 flex items-baseline justify-between">
          <span className="text-xs font-medium uppercase tracking-wider text-ink-500">
            按首字母
          </span>
          <span className="text-[11px] tabular-nums text-ink-400">
            {totalWith}/26
          </span>
        </div>

        {/* 字母 grid: 4 列 x 7 行 */}
        <div className="grid grid-cols-4 gap-1.5">
          {ALPHA.map((letter) => {
            const list = byAlpha[letter] || [];
            const has = list.length > 0;
            const isOpen = expanded === letter;
            const isHover = isExternalHover(letter);
            return (
              <button
                key={letter}
                type="button"
                data-alpha-btn
                disabled={!has}
                onClick={() => has && setExpanded(isOpen ? null : letter)}
                onMouseEnter={() => has && onLetterHover?.(letter)}
                onMouseLeave={() => onLetterHover?.(null)}
                onFocus={() => has && onLetterHover?.(letter)}
                onBlur={() => onLetterHover?.(null)}
                aria-expanded={isOpen}
                className={cn(
                  "group relative flex h-9 items-center justify-center rounded-md text-sm font-semibold tabular-nums transition",
                  has
                    ? isOpen
                      ? "bg-primary text-white shadow-sm"
                      : isHover
                      ? "bg-primary-50 text-primary ring-1 ring-primary/30"
                      : "bg-ink-50 text-ink-900 hover:bg-primary-50 hover:text-primary"
                    : "cursor-not-allowed bg-ink-50/40 text-ink-300"
                )}
                title={has ? `${letter} · ${list.length} 个城市` : `${letter} 无数据`}
              >
                {letter}
                {has && (
                  <span
                    className={cn(
                      "absolute -right-0.5 -top-0.5 grid h-3.5 min-w-[14px] place-items-center rounded-full px-0.5 text-[9px] font-medium tabular-nums",
                      isOpen || isHover
                        ? "bg-primary text-white"
                        : "bg-ink-200 text-ink-600"
                    )}
                  >
                    {list.length}
                  </span>
                )}
              </button>
            );
          })}
        </div>

        {/* 展开城市 panel — sidebar 模式 max-h 滚动, 不撑破地图列 */}
        {expanded && byAlpha[expanded] && (
          <div
            ref={panelRef}
            data-alpha-panel
            className="mt-3 flex min-h-0 flex-1 flex-col overflow-hidden rounded-lg border border-ink-100 bg-white"
          >
            <div className="flex items-center justify-between border-b border-ink-100 bg-ink-50/60 px-3 py-2">
              <div className="flex items-baseline gap-1.5">
                <span className="text-base font-semibold tracking-tight text-primary">
                  {expanded}
                </span>
                <span className="text-[11px] text-ink-500">
                  {byAlpha[expanded].length} 个城市
                </span>
              </div>
              <button
                type="button"
                onClick={() => setExpanded(null)}
                className="inline-flex items-center gap-0.5 rounded px-1.5 py-0.5 text-[11px] text-ink-500 transition hover:bg-white hover:text-ink-900"
                aria-label="收起"
              >
                <X className="h-3 w-3" />
              </button>
            </div>
            <ul className="flex-1 overflow-y-auto py-1">
              {byAlpha[expanded].map((c) => (
                <li key={c.code}>
                  <Link
                    href={`/city/${encodeURIComponent(c.code)}`}
                    className="flex items-center justify-between gap-2 px-3 py-1.5 text-sm transition hover:bg-primary-50"
                  >
                    <span className="min-w-0 truncate text-ink-900 group-hover:text-primary">
                      {c.name}
                    </span>
                    <span className="shrink-0 text-[10px] tabular-nums text-ink-400">
                      {c.iata && c.iata !== "—" ? c.iata : ""}
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* footer meta (sidebar 模式下置底) */}
        <div className="mt-2 text-[10px] text-ink-400">
          共 {cities.length} 城市 · hover 同步高亮地图
        </div>
      </div>
    );
  }

  // ---------- Horizontal 模式 (v1 行为) ----------
  return (
    <div className={cn("space-y-4", className)}>
      <div className="flex flex-wrap items-center gap-x-1 gap-y-2">
        {ALPHA.map((letter) => {
          const list = byAlpha[letter] || [];
          const has = list.length > 0;
          const isOpen = expanded === letter;
          const isHover = isExternalHover(letter);
          return (
            <button
              key={letter}
              type="button"
              data-alpha-btn
              disabled={!has}
              onClick={() => has && setExpanded(isOpen ? null : letter)}
              onMouseEnter={() => has && onLetterHover?.(letter)}
              onMouseLeave={() => onLetterHover?.(null)}
              aria-expanded={isOpen}
              className={cn(
                "alpha-btn group inline-flex h-7 min-w-[28px] items-center justify-center rounded px-1.5 text-[13px] font-medium tabular-nums transition",
                has
                  ? isOpen
                    ? "bg-primary text-white"
                    : isHover
                    ? "bg-primary-50 text-primary"
                    : "text-ink-900 hover:bg-ink-50 hover:text-primary"
                  : "cursor-not-allowed text-ink-200"
              )}
              title={has ? `${letter} · ${list.length} 个城市` : `${letter} 无数据`}
            >
              {letter}
            </button>
          );
        })}
      </div>

      <div className="flex items-center gap-3 text-xs text-ink-500">
        <span>
          {totalWith} / 26 字母有数据 · 共 {cities.length} 城市
        </span>
        {activeLetter && (
          <span className="inline-flex items-center gap-1 text-primary">
            <span className="h-1.5 w-1.5 rounded-full bg-primary" />
            正在显示 {activeLetter} · {byAlpha[activeLetter].length} 个
          </span>
        )}
      </div>

      {expanded && byAlpha[expanded] && (
        <div
          data-alpha-panel
          className="overflow-hidden rounded-lg border border-ink-100 bg-ink-50/50"
        >
          <div className="flex items-center justify-between border-b border-ink-100 bg-white px-5 py-3">
            <div className="flex items-baseline gap-2">
              <span className="text-2xl font-semibold tracking-tight text-primary">
                {expanded}
              </span>
              <span className="text-sm text-ink-500">
                {byAlpha[expanded].length} 个城市
              </span>
            </div>
            <button
              type="button"
              onClick={() => setExpanded(null)}
              className="inline-flex items-center gap-1 rounded px-2 py-1 text-xs text-ink-500 transition hover:bg-ink-50 hover:text-ink-900"
            >
              <X className="h-3.5 w-3.5" />
              收起
            </button>
          </div>
          <div className="grid grid-cols-2 gap-px bg-ink-100 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5">
            {byAlpha[expanded].map((c) => (
              <Link
                key={c.code}
                href={`/city/${encodeURIComponent(c.code)}`}
                className="group flex items-center justify-between gap-2 bg-white px-4 py-3 transition hover:bg-primary-50"
              >
                <div className="min-w-0">
                  <div className="truncate text-sm font-medium text-ink-900 group-hover:text-primary">
                    {c.name}
                  </div>
                  <div className="truncate text-xs text-ink-500 tabular-nums">
                    {c.iata && c.iata !== "—" ? c.iata : "—"} · {c.region}
                  </div>
                </div>
                <ChevronDown className="h-3.5 w-3.5 -rotate-90 text-ink-300 transition group-hover:translate-x-0.5 group-hover:text-primary" />
              </Link>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
