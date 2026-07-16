import { Suspense } from "react";
import { NavBar } from "@/components/nav-bar";
import { ExperiencesListClient } from "./list-client";

export const metadata = {
  title: "保障经验 · AOG 知识库",
  description: "18 个实战经验库 · 流程/规范/案例/培训/技术/管理",
};

export default function ExperiencesPage() {
  return (
    <>
      <NavBar active="experiences" />
      <section className="border-b border-ink-100 bg-gradient-to-b from-ink-50 to-white">
        <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
          <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
            <div>
              <h1 className="text-2xl font-bold text-ink-900 sm:text-3xl">保障经验</h1>
              <p className="mt-1 text-sm text-ink-600">
                18 个实战经验库 · 流程 / 规范 / 案例 / 培训 / 技术 / 管理
              </p>
            </div>
          </div>
        </div>
      </section>
      <Suspense fallback={<div className="mx-auto max-w-7xl px-4 py-8 text-ink-500 text-sm">加载中…</div>}>
        <ExperiencesListClient />
      </Suspense>
    </>
  );
}
