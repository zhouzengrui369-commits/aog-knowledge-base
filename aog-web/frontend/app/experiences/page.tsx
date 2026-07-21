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
      <Suspense
        fallback={
          <div className="mx-auto max-w-7xl px-4 py-8 text-sm text-ink-500 sm:px-6 lg:px-8">
            加载中…
          </div>
        }
      >
        <ExperiencesListClient />
      </Suspense>
    </>
  );
}
