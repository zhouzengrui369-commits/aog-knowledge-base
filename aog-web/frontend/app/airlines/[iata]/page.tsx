import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { NavBar } from "@/components/nav-bar";
import { AirlineDetailClient } from "./detail-client";

interface PageProps {
  params: Promise<{ iata: string }>;
}

/** 静态生成 - 用全部 IATA 列表 (来自 data/airlines.json 静态导入) */
export async function generateStaticParams() {
  try {
    // 静态导入 airlines.json — Next.js 会自动 inline 进 build
    const { AIRLINES_STATIC } = await import("@/lib/airlines-static");
    return AIRLINES_STATIC.map((a) => ({ iata: a.iata.toUpperCase() }));
  } catch {
    return [];
  }
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { iata } = await params;
  return {
    title: `${iata.toUpperCase()} 航司详情`,
    description: `中国 ${iata.toUpperCase()} 航司基地 + 机队 + AOG 联系方式`,
  };
}

export default async function AirlinePage({ params }: PageProps) {
  const { iata } = await params;
  if (!iata || iata.length !== 2 || !/^[A-Za-z0-9]+$/.test(iata)) {
    notFound();
  }
  return (
    <>
      <NavBar active="airlines" />
      <AirlineDetailClient iata={iata.toUpperCase()} />
    </>
  );
}
