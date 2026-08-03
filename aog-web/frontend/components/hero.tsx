"use client";

import * as React from "react";
import Link from "next/link";
import { Sparkles } from "lucide-react";
import { SearchBar } from "@/components/search-bar";
import { cn } from "@/lib/utils";
import { getProductionStats, type ProductionStats } from "@/lib/production-api";

const HOT_TAGS = [
  { label: "北京大兴", href: "/city/B-北京大兴" },
  { label: "上海浦东", href: "/city/S-上海浦东" },
  { label: "B787 风挡", href: "/experiences?q=B787" },
  { label: "BMS9-3", href: "/experiences?q=BMS9-3" },
];

export function Hero({ className }: { className?: string }) {
  const [stats, setStats] = React.useState<ProductionStats | null>(null);

  React.useEffect(() => {
    let cancelled = false;
    getProductionStats().then((value) => { if (!cancelled) setStats(value); });
    return () => { cancelled = true; };
  }, []);

  function openAssistant() {
    window.dispatchEvent(new CustomEvent("aog:ask", { detail: { q: "请根据已核验资料协助我处理当前 AOG。" } }));
  }

  return (
    <section className={cn("hero-gradient border-b border-ink-100", className)}>
      <div className="mx-auto max-w-7xl px-4 pb-14 pt-16 sm:px-6 sm:pt-20 lg:px-8 lg:pt-24">
        <div className="max-w-3xl">
          <div className="mb-5 inline-flex items-center gap-2 text-xs font-medium text-ink-500">
            <span className="inline-block h-px w-6 bg-ink-300" />
            <span className="uppercase tracking-wider">AOG 应急保障知识库</span>
          </div>
          <h1 className="text-[40px] font-semibold leading-[1.1] tracking-tight text-ink-900 sm:text-[52px] lg:text-[60px]">
            让每一次 AOG 都有<br /><span className="text-primary">可追溯的处置依据</span><span>。</span>
          </h1>
          <p className="mt-5 max-w-2xl text-base leading-relaxed text-ink-500 sm:text-lg">
            {stats ? `${stats.cities} 个城市预案 · ${stats.experiences} 条可发布经验 · ${stats.knowledge_chunks} 条知识片段` : "正在读取生产数据…"}
            <br className="hidden sm:block" />
            所有数字来自当前 SQLite 与索引状态，不使用前端 mock 估算。
          </p>
          <div className="mt-8 max-w-2xl"><SearchBar variant="hero" /></div>
          <div className="mt-5 flex flex-wrap items-center gap-x-2 gap-y-2 text-sm">
            <span className="text-ink-500">热门</span>
            {HOT_TAGS.map((tag) => <Link key={tag.href} href={tag.href} className="text-ink-700 transition hover:text-primary">{tag.label}</Link>)}
            <button type="button" onClick={openAssistant} className="ml-2 inline-flex items-center gap-1 rounded-full border border-primary/30 bg-primary-50 px-3 py-1 text-xs font-medium text-primary hover:border-primary">
              <Sparkles className="h-3.5 w-3.5" />问 AI
            </button>
          </div>
        </div>
      </div>
    </section>
  );
}
