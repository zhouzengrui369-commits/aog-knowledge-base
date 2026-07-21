import Link from "next/link";
import { ArrowUpRight } from "lucide-react";
import { cn, STATUS_LABEL, normalizeCityStatus } from "@/lib/utils";
import type { City } from "@/lib/types";

interface Props {
  cities: City[]; // already sorted desc by view_count, take first 4
  className?: string;
}

/**
 * 推荐城市（Linear / Plane 风格）
 *  - 1 大 + 3 小 asymmetric grid
 *  - 大卡: iata + 城市名 + view_count 大数字 + 1 metric
 *  - 小卡: 缩写 + 1 行 summary
 *  - 1px border, hover lift 微动
 */
export function FeaturedCities({ cities, className }: Props) {
  if (cities.length === 0) return null;
  const [main, ...rest] = cities;
  const small = rest.slice(0, 3);
  const mainStatus = STATUS_LABEL[normalizeCityStatus(main.status)];

  return (
    <div className={cn("grid grid-cols-1 gap-4 lg:grid-cols-3", className)}>
      {/* Main featured city — 2/3 width on lg */}
      <Link
        href={`/city/${encodeURIComponent(main.code)}`}
        className="group relative col-span-1 flex flex-col justify-between overflow-hidden rounded-xl border border-ink-100 bg-white p-7 transition hover:border-ink-300 lg:col-span-2 lg:p-8"
      >
        <div className="absolute right-5 top-5 inline-flex h-9 w-9 items-center justify-center rounded-full border border-ink-100 text-ink-300 transition group-hover:border-primary group-hover:text-primary">
          <ArrowUpRight className="h-4 w-4" />
        </div>

        <div>
          <div className="mb-2 flex items-center gap-2 text-xs text-ink-500">
            <span className="font-mono">{main.iata || "—"}</span>
            <span className="text-ink-300">·</span>
            <span>{main.region}</span>
            {mainStatus && (
              <>
                <span className="text-ink-300">·</span>
                <span className="inline-flex items-center gap-1 text-ink-700">
                  <span className={cn("h-1.5 w-1.5 rounded-full", mainStatus.dot)} />
                  {mainStatus.text}
                </span>
              </>
            )}
          </div>
          <h3 className="text-3xl font-semibold tracking-tight text-ink-900 transition group-hover:text-primary sm:text-4xl">
            {main.name}
          </h3>
          {main.summary && (
            <p className="mt-3 max-w-md text-sm text-ink-500">{main.summary}</p>
          )}
        </div>

        <div className="mt-8 flex items-end gap-8 border-t border-ink-100 pt-5">
          <div>
            <div className="text-3xl font-semibold tabular-nums tracking-tight text-ink-900">
              {(main.view_count || 0).toLocaleString()}
            </div>
            <div className="mt-0.5 text-xs text-ink-500">累计访问</div>
          </div>
          <div>
            <div className="text-3xl font-semibold tabular-nums tracking-tight text-ink-900">
              {main.fleet?.length ?? "—"}
            </div>
            <div className="mt-0.5 text-xs text-ink-500">执飞机型</div>
          </div>
          <div>
            <div className="text-3xl font-semibold tabular-nums tracking-tight text-ink-900">
              {main.parts?.length ?? main.parts_mockup?.length ?? "—"}
            </div>
            <div className="mt-0.5 text-xs text-ink-500">备件项</div>
          </div>
        </div>
      </Link>

      {/* Small cities — stacked, 1/3 width on lg */}
      <div className="flex flex-col gap-4">
        {small.map((c) => (
          <Link
            key={c.code}
            href={`/city/${encodeURIComponent(c.code)}`}
            className="group flex flex-1 flex-col justify-between rounded-xl border border-ink-100 bg-white p-5 transition hover:border-ink-300"
          >
            <div>
              <div className="flex items-center justify-between text-xs text-ink-500">
                <span className="font-mono">{c.iata || "—"}</span>
                <span>{(c.view_count || 0).toLocaleString()}</span>
              </div>
              <h4 className="mt-2 text-lg font-semibold text-ink-900 transition group-hover:text-primary">
                {c.name}
              </h4>
              {c.summary && (
                <p className="mt-1.5 line-clamp-2 text-xs text-ink-500">{c.summary}</p>
              )}
            </div>
            <div className="mt-3 flex items-center justify-between text-[11px]">
              <span className="text-ink-500">{c.region}</span>
              <ArrowUpRight className="h-3 w-3 text-ink-300 transition group-hover:translate-x-0.5 group-hover:-translate-y-0.5 group-hover:text-primary" />
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
