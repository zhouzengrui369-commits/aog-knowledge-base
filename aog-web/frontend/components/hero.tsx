"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Search, MapPin, FileText, BookOpen, Sparkles } from "lucide-react";
import { SearchBar } from "@/components/search-bar";

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
}

/** Hero — 首页头部（搜索 + 热门 + AI 快捷提问） */
export function Hero({ onAskAI }: Props) {
  const router = useRouter();
  return (
    <section className="hero-gradient">
      <div className="mx-auto max-w-7xl px-4 pb-10 pt-12 sm:px-6 sm:pt-16 lg:px-8 lg:pt-20">
        <div className="mx-auto max-w-3xl text-center">
          <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-primary-100 bg-primary-50 px-3 py-1 text-xs font-medium text-primary-700">
            <span className="h-1.5 w-1.5 rounded-full bg-success" />
            数据已更新 · 220 城市预案 + 18 实战经验 + 14 核心预案
          </div>
          <h1 className="text-3xl font-bold tracking-tight text-ink-900 sm:text-4xl lg:text-5xl">
            AOG 应急保障<span className="text-primary">知识库</span>
          </h1>
          <p className="mt-3 text-base text-ink-500 sm:text-lg">
            航材 AOG 智能伙伴 · 一站查询城市预案、保障经验、AI 对话
          </p>

          <SearchBar variant="hero" className="mx-auto mt-8 max-w-2xl" />

          <div className="mt-4 flex flex-wrap items-center justify-center gap-2 text-xs text-ink-500">
            <span>热门：</span>
            {HOT_TAGS.map((t) => (
              <Link
                key={t.href}
                href={t.href}
                className="rounded-full border border-ink-100 bg-white px-2.5 py-1 hover:border-primary hover:text-primary"
              >
                {t.label}
              </Link>
            ))}
          </div>

          <div className="mt-3 flex flex-wrap items-center justify-center gap-1.5 text-[11px] text-ink-500">
            <span>问 AI：</span>
            {QUICK_AI.map((q) => (
              <button
                key={q}
                type="button"
                onClick={() => onAskAI?.(q)}
                className="rounded-full bg-primary-50 px-2.5 py-1 text-primary-700 hover:bg-primary hover:text-white"
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
