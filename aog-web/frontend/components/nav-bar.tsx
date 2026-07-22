import Link from "next/link";
import { Plane } from "lucide-react";
import { SearchBar } from "@/components/search-bar";

/** 顶部导航 — 全局共享 */
export function NavBar({ active }: { active?: "home" | "experiences" | "airlines" }) {
  return (
    <header className="sticky top-0 z-30 border-b border-ink-100 bg-white/80 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
        <Link href="/" className="flex items-center gap-2">
          <span className="grid h-9 w-9 place-items-center rounded-lg bg-primary text-white shadow-soft">
            <Plane className="h-5 w-5" />
          </span>
          <div className="leading-tight">
            <div className="text-base font-semibold text-ink-900">AOG 知识库</div>
            <div className="text-[11px] text-ink-500">航材 AOG 智能伙伴</div>
          </div>
        </Link>
        <nav className="hidden gap-1 md:flex">
          <Link
            href="/"
            className={
              "rounded-md px-3 py-1.5 text-sm font-medium " +
              (active === "home"
                ? "bg-primary-50 text-primary"
                : "text-ink-700 hover:bg-ink-50")
            }
          >
            首页
          </Link>
          <Link
            href="/airlines"
            className={
              "rounded-md px-3 py-1.5 text-sm font-medium " +
              (active === "airlines"
                ? "bg-primary-50 text-primary"
                : "text-ink-700 hover:bg-ink-50")
            }
          >
            航司互援
          </Link>
          <Link
            href="/experiences"
            className={
              "rounded-md px-3 py-1.5 text-sm font-medium " +
              (active === "experiences"
                ? "bg-primary-50 text-primary"
                : "text-ink-700 hover:bg-ink-50")
            }
          >
            保障经验
          </Link>
          <span className="cursor-not-allowed rounded-md px-3 py-1.5 text-sm font-medium text-ink-300">
            课件
            <span className="ml-1 rounded bg-ink-100 px-1.5 py-0.5 text-[10px] text-ink-500">v2</span>
          </span>
        </nav>
        <div className="flex items-center gap-2">
          <div className="hidden sm:block">
            <SearchBar variant="compact" />
          </div>
        </div>
      </div>
    </header>
  );
}
