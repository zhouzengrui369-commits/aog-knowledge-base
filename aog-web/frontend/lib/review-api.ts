import type { ReviewCity, ReviewCitySummary, ReviewStatus } from "@/lib/types";

const BASE = (process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000").replace(/\/api\/?$/, "");

async function reviewFetch<T>(path: string): Promise<T | null> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 8_000);
  try {
    const response = await fetch(`${BASE}${path}`, {
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      signal: controller.signal,
    });
    if (!response.ok) return null;
    return (await response.json()) as T;
  } catch {
    return null;
  } finally {
    window.clearTimeout(timeout);
  }
}

export async function getReviewCities(options?: {
  reviewStatus?: ReviewStatus;
  includeVerified?: boolean;
}): Promise<ReviewCitySummary[] | null> {
  const query = new URLSearchParams();
  if (options?.reviewStatus) query.set("review_status", options.reviewStatus);
  if (options?.includeVerified) query.set("include_verified", "true");
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return reviewFetch<ReviewCitySummary[]>(`/api/review/cities${suffix}`);
}

export async function getReviewCity(code: string): Promise<ReviewCity | null> {
  return reviewFetch<ReviewCity>(`/api/review/city/${encodeURIComponent(code)}`);
}
