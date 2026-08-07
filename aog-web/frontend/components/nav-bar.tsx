import Link from "next/link";
import { Plane } from "lucide-react";
import { SearchBar } from "@/components/search-bar";

export function NavBar({ active }: { active?: "home" | "experiences" | "airlines" | "review" }) {
  const links = [
    { href: "/", key: "home", label: "首页" },
    { href: "/airlines", key: "airlines", label: "航司互援" },
    { href: "/experiences", key: "experiences", label: "保障经验" },
    { href: "/review", key: "review", label: "知识审核" },
  ] as const;

  return (
    <header className="sticky top-0 z-30 border-b border-ink-100 bg-white/90 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
        <Link href="/" className="flex items-center gap-2">
          <span className="grid h-9 w-9 place-items-center rounded-lg bg-primary text-white shadow-soft"><Plane className="h-5 w-5" /></span>
          <div className="leading-tight"><div className="text-base font-semibold text-ink-900">AOG 知识库</div><div className="text-[11px] text-ink-500">航材 AOG 智能伙伴</div></div>
        </Link>
        <nav className="hidden gap-1 md:flex" aria-label="主导航">
          {links.map((link) => (
            <Link key={link.key} href={link.href} className={`rounded-md px-3 py-1.5 text-sm font-medium ${active === link.key ? "bg-primary-50 text-primary" : "text-ink-700 hover:bg-ink-50"}`}>{link.label}</Link>
          ))}
        </nav>
        <div className="hidden sm:block"><SearchBar variant="compact" /></div>
      </div>
    </header>
  );
}
