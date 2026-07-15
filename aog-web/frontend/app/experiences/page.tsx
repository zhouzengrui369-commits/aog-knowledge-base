import { Suspense } from "react";
import Link from "next/link";
import { NavBar } from "@/components/nav-bar";
import { getExperiences } from "@/lib/api";
import { ExperienceFilter } from "./filter";

export const dynamic = "force-dynamic";

export const metadata = {
  title: "保障经验 · AOG 知识库",
  description: "18 个实战经验库 · 流程/规范/案例/培训/技术/管理",
};

interface PageProps {
  searchParams: Promise<{ q?: string; category?: string; status?: string }>;
}

export default async function ExperiencesPage({ searchParams }: PageProps) {
  const sp = await searchParams;
  const all = await getExperiences();

  return (
    <>
      <NavBar active="experiences" />
      <section className="border-b border-ink-100 bg-gradient-to-b from-ink-50 to-white">
        <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
          <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
            <div>
              <h1 className="text-2xl font-bold text-ink-900 sm:text-3xl">保障经验</h1>
              <p className="mt-1 text-sm text-ink-500">
                {all.length} 个实战经验库 · 流程 / 规范 / 案例 / 培训 / 技术 / 管理
              </p>
              <p className="mt-2 text-xs text-ink-500">
                精选案例：
                <Link href="/experience/b787-windshield-aog" className="text-primary hover:underline">
                  B787 风挡 AOG 处理流程
                </Link>
                {" · "}
                <Link href="/experience/bms9-3-fiberglass" className="text-primary hover:underline">
                  BMS9-3 系列玻璃纤维布
                </Link>
                {" · "}
                <Link href="/experience/milan-pickup" className="text-primary hover:underline">
                  米兰取件经验
                </Link>
                {" · "}
                <Link href="/experience/aog-workflow-r1" className="text-primary hover:underline">
                  AOG 保障工作流 R1
                </Link>
              </p>
            </div>
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        <Suspense fallback={<div className="text-ink-500">加载中…</div>}>
          <ExperienceFilter
            all={all}
            initialCategory={sp.category || "all"}
            initialStatus={sp.status || "all"}
            initialQuery={sp.q || ""}
          />
        </Suspense>
      </section>

      <footer className="border-t border-ink-100 bg-ink-50">
        <div className="mx-auto flex max-w-7xl flex-col gap-2 px-4 py-6 text-xs text-ink-500 sm:flex-row sm:items-center sm:justify-between sm:px-6 lg:px-8">
          <div>© 2026 AOG 知识库 · v0.1.0-frontend</div>
          <div>
            <Link href="/" className="hover:text-ink-900">
              ← 返回首页
            </Link>
          </div>
        </div>
      </footer>
    </>
  );
}
