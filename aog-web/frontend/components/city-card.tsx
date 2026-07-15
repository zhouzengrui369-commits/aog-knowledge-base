import Link from "next/link";
import { ChevronRight } from "lucide-react";
import { cn, STATUS_LABEL, normalizeCityStatus } from "@/lib/utils";
import type { City } from "@/lib/types";

interface Props {
  city: City;
  className?: string;
}

/** 城市卡片（首页推荐 + 城市列表用） */
export function CityCard({ city, className }: Props) {
  const st = STATUS_LABEL[normalizeCityStatus(city.status)];
  const href = `/city/${encodeURIComponent(city.code)}`;
  return (
    <Link
      href={href}
      className={cn(
        "group block rounded-xl border border-ink-100 bg-white p-5 shadow-soft transition hover:border-primary hover:shadow-pop",
        className
      )}
    >
      <div className="flex items-start justify-between">
        <div>
          <div className="text-base font-semibold text-ink-900 group-hover:text-primary">
            {city.name}
          </div>
          <div className="mt-0.5 text-xs text-ink-500">
            {city.iata || "—"} · {city.region}
          </div>
        </div>
        <span
          className={cn(
            "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium",
            st.cls
          )}
        >
          <span className={cn("h-1.5 w-1.5 rounded-full", st.dot)} />
          {st.text}
        </span>
      </div>
      {city.summary && (
        <p className="mt-3 line-clamp-2 text-sm text-ink-500">{city.summary}</p>
      )}
      <div className="mt-4 flex items-center justify-between text-xs text-ink-500">
        <span>预案 / 联系人 / 备件 / 物流</span>
        <span className="inline-flex items-center gap-0.5 text-primary group-hover:underline">
          查看详情 <ChevronRight className="h-3 w-3" />
        </span>
      </div>
    </Link>
  );
}
