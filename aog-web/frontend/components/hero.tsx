"use client";

import * as React from "react";
import Link from "next/link";
import { Search, Sparkles } from "lucide-react";
import { SearchBar } from "@/components/search-bar";
import { cn } from "@/lib/utils";
import { getCities } from "@/lib/api";

const QUICK_AI = [
  "B787 风挡 AOG 怎么处理？",
  "浦东 AOG 联系人？",
  "BMS9-3 玻璃纤维布哪里备？",
];

const HOT_TAGS = [
  { label: "北京大兴", href: "/city/B-北京大兴" },
  { label: "上海浦东", href: "/city/S-上海浦东" },
  { label: "B787 风挡", href: "/experiences?q=B787" },
  { label: "BMS9-3 玻璃纤维布", href: "/experiences?q=BMS9-3" },
];

interface Props {
  onAskAI?: (q: string) => void;
  className?: string;
}

/**
 * Hero — 首页头部（Linear / Vercel 风格）
 *  - 左对齐（非居中），max-w-3xl
 *  - 强 typography：48–60px 标题
 *  - 搜索框 + 热门 / 问 AI chips inline
 *  - subtle gradient bg（已在 globals.css .hero-gradient 定义）
 */
export function Hero({ onAskAI, className }: Props) {
  // V8: 动态城市数 (替代硬编码 220) — 与 home-data 同步
  const [cityCount, setCityCount] = React.useState<number | null>(null);
  React.useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const cities = await getCities();
        if (!cancelled) setCityCount(cities.length);
      } catch {
        if (!cancelled) setCityCount(220); // fallback 硬编码
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <section className={cn("hero-gradient border-b border-ink-100", className)}>
      <div className="mx-auto max-w-7xl px-4 pb-14 pt-16 sm:px-6 sm:pt-20 lg:px-8 lg:pt-24">
        <div className="max-w-3xl">
          {/* Eyebrow */}
          <div className="mb-5 inline-flex items-center gap-2 text-xs font-medium text-ink-500">
            <span className="inline-block h-px w-6 bg-ink-300" />
            <span className="uppercase tracking-wider">AOG 应急保障知识库</span>
          </div>

          {/* Headline */}
          <h1 className="text-[40px] font-semibold leading-[1.1] tracking-tight text-ink-900 sm:text-[52px] lg:text-[60px]">
            让每一次 AOG 都有
            <br />
            <span className="text-primary">确定性的答案</span>
            <span className="text-ink-900">。</span>
          </h1>

          <p className="mt-5 max-w-xl text-base leading-relaxed text-ink-500 sm:text-lg">
            {cityCount ?? 220} 个城市预案 · 18 份实战经验 · 8686 条知识片段。
            <br className="hidden sm:block" />
            搜索、按首字母浏览、或直接问 AI。
          </p>

          {/* Search */}
          <div className="mt-8 max-w-2xl">
            <SearchBar variant="hero" />
          </div>

          {/* Hot tags + AI prompts — inline, one line on desktop */}
          <div className="mt-5 flex flex-wrap items-center gap-x-1.5 gap-y-2 text-sm">
            <span className="text-ink-500">热门</span>
            {HOT_TAGS.map((t, i) => (
              <React.Fragment key={t.href}>
                {i > 0 && <span className="text-ink-300">·</span>}
                <Link
                  href={t.href}
                  className="text-ink-700 transition hover:text-primary"
                >
                  {t.label}
                </Link>
              </React.Fragment>
            ))}
            <span className="ml-3 inline-block h-4 w-px bg-ink-100" />
            <span className="inline-flex items-center gap-1 text-ink-500">
              <Sparkles className="h-3.5 w-3.5" />
              问 AI
            </span>
            {QUICK_AI.map((q) => (
              <button
                key={q}
                type="button"
                onClick={() => onAskAI?.(q)}
                className="rounded-full border border-ink-100 bg-white px-2.5 py-1 text-xs text-ink-700 transition hover:border-primary hover:text-primary"
              >
                {q}
              </button>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
