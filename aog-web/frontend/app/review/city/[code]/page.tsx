import type { Metadata } from "next";
import { ReviewCityDetailClient } from "@/components/review-city-detail-client";
import cityCodes from "../../../city/codes.json";

interface PageProps {
  params: Promise<{ code: string }>;
}

export async function generateStaticParams() {
  return cityCodes.map((code) => ({ code }));
}

export async function generateMetadata(): Promise<Metadata> {
  return { title: "知识审核详情 · AOG 知识库" };
}

export default async function ReviewCityPage({ params }: PageProps) {
  const { code } = await params;
  return <ReviewCityDetailClient code={code} />;
}
