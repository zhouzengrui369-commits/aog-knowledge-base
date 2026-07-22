"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { NavBar } from "@/components/nav-bar";
import { Plane, Home, Search } from "lucide-react";
import { getCities } from "@/lib/api";

export default function NotFound() {
  const [smartRedirect, setSmartRedirect] = useState<string | null>(null);

  useEffect(() => {
    // V12.2: 智能 404 — 检测 /city/{code} 路径, 按 name/code 模糊匹配后自动跳转
    if (typeof window === "undefined") return;
    const m = window.location.pathname.match(/^\/city\/([^/]+)$/);
    if (!m) return;
    const raw = decodeURIComponent(m[1]); // 'c-重庆江北' or 'C-重庆江北'
    let cancelled = false;
    (async () => {
      try {
        const all = await getCities();
        if (cancelled) return;
        // 1) exact code match (case-insensitive)
        const normLower = raw.toLowerCase();
        let hit = all.find((c) => c.code.toLowerCase() === normLower);
        // 2) 按 name 模糊 (lowercase url: 'c-重庆江北' → name '重庆江北')
        if (!hit) {
          const nameCandidate = raw.includes("-") ? raw.slice(raw.indexOf("-") + 1) : raw;
          hit = all.find((c) => c.name === nameCandidate);
        }
        // 3) 按 pinyin / iata / view
        if (!hit) {
          hit = all.find(
            (c) =>
              c.iata?.toUpperCase() === raw.toUpperCase() ||
              c.pinyin === raw.toLowerCase()
          );
        }
        if (hit) setSmartRedirect(`/city/${hit.code}`);  // V13: 不 encode, <Link> 会自己处理
      } catch {
        // 静默 — fallback 404 内容
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <>
      <NavBar />
      <main className="mx-auto flex min-h-[70vh] max-w-3xl flex-col items-center justify-center px-4 py-12 text-center sm:px-6 lg:px-8">
        <div className="relative">
          <div className="text-[120px] font-extrabold leading-none text-primary-50 sm:text-[160px]">404</div>
          <div className="absolute inset-0 flex items-center justify-center">
            <Plane className="h-12 w-12 text-primary opacity-50" />
          </div>
        </div>
        <h1 className="-mt-6 text-2xl font-bold text-ink-900 sm:text-3xl">这架航班没有找到目的地</h1>
        <p className="mt-2 max-w-md text-sm text-ink-500">
          {smartRedirect
            ? "已找到匹配城市, 正在跳转..."
            : "抱歉，你访问的页面不存在。可能链接已过期，或城市 / 经验已迁移。"}
        </p>

        <div className="mt-6 flex w-full max-w-md flex-col gap-2 sm:flex-row">
          <input
            type="search"
            placeholder="试试搜「北京大兴」「B787 风挡」"
            className="flex-1 rounded-md border border-ink-100 bg-white px-3 py-2 text-sm placeholder:text-ink-500 focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
          />
          <Link
            href="/"
            className="inline-flex items-center justify-center gap-1 rounded-md bg-primary px-4 py-2 text-sm font-medium text-white shadow-soft hover:bg-primary-700"
          >
            <Home className="h-4 w-4" /> 返回首页
          </Link>
        </div>

        {smartRedirect ? (
          <div className="mt-6">
            <Link
              href={smartRedirect}
              className="inline-flex items-center justify-center gap-1 rounded-md bg-primary px-5 py-2.5 text-sm font-medium text-white shadow-soft hover:bg-primary-700"
            >
              点这里直接打开 {decodeURIComponent(smartRedirect.split("/").pop() || "")} →
            </Link>
          </div>
        ) : null}

        <div className="mt-8 grid w-full max-w-2xl grid-cols-1 gap-3 sm:grid-cols-3">
          <Link
            href="/city/B-北京大兴"
            className="rounded-xl border border-ink-100 bg-white p-4 text-left shadow-soft hover:border-primary"
          >
            <div className="text-xs font-medium text-primary">热门城市</div>
            <div className="mt-1 text-sm font-semibold text-ink-900">北京大兴</div>
            <div className="mt-0.5 text-xs text-ink-500">PKX · 华北 · 现行</div>
          </Link>
          <Link
            href="/city/S-上海浦东"
            className="rounded-xl border border-ink-100 bg-white p-4 text-left shadow-soft hover:border-primary"
          >
            <div className="text-xs font-medium text-primary">热门城市</div>
            <div className="mt-1 text-sm font-semibold text-ink-900">上海浦东</div>
            <div className="mt-0.5 text-xs text-ink-500">PKX · 华东 · 现行</div>
          </Link>
          <Link
            href="/experiences"
            className="rounded-xl border border-ink-100 bg-white p-4 text-left shadow-soft hover:border-primary"
          >
            <div className="text-xs font-medium text-primary">全部经验</div>
            <div className="mt-1 text-sm font-semibold text-ink-900">保障经验库</div>
            <div className="mt-0.5 text-xs text-ink-500">18 个实战经验</div>
          </Link>
        </div>
      </main>
    </>
  );
}
