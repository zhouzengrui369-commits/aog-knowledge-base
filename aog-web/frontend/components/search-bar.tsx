"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { Search } from "lucide-react";
import { cn } from "@/lib/utils";

interface Props {
  variant?: "compact" | "hero";
  className?: string;
  initialQuery?: string;
  placeholder?: string;
}

/** 全局搜索框 — 客户端组件 */
export function SearchBar({ variant = "compact", className, initialQuery = "", placeholder }: Props) {
  const router = useRouter();
  const [q, setQ] = React.useState(initialQuery);

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    const v = q.trim();
    if (!v) return;
    // 简化：跳到经验搜索（更通用），城市/经验页会再做精确匹配
    router.push(`/experiences?q=${encodeURIComponent(v)}`);
  };

  if (variant === "hero") {
    return (
      <form onSubmit={submit} className={cn("relative", className)} autoComplete="off">
        <span className="pointer-events-none absolute inset-y-0 left-4 flex items-center text-ink-500">
          <Search className="h-5 w-5" />
        </span>
        <input
          type="search"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder={placeholder ?? "搜索航站、城市或经验，如「北京大兴」「B787 风挡」"}
          className="block w-full rounded-xl border border-ink-100 bg-white py-4 pl-12 pr-32 text-base shadow-soft placeholder:text-ink-500 focus:border-primary focus:outline-none focus:ring-4 focus:ring-primary/15"
        />
        <button
          type="submit"
          className="absolute right-2 top-2 bottom-2 inline-flex items-center gap-1 rounded-lg bg-primary px-5 text-sm font-medium text-white shadow-soft hover:bg-primary-700"
        >
          搜索
        </button>
      </form>
    );
  }

  return (
    <form onSubmit={submit} className={cn("relative", className)}>
      <span className="pointer-events-none absolute inset-y-0 left-3 flex items-center text-ink-500">
        <Search className="h-4 w-4" />
      </span>
      <input
        type="search"
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder={placeholder ?? "搜航站 / 城市 / 经验…"}
        className="w-64 rounded-md border border-ink-100 bg-ink-50 py-1.5 pl-9 pr-3 text-sm placeholder:text-ink-500 focus:border-primary focus:bg-white focus:outline-none focus:ring-2 focus:ring-primary/20"
      />
    </form>
  );
}
