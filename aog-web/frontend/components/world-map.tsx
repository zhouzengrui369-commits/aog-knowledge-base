"use client";

import * as React from "react";
import Link from "next/link";
// react-simple-maps 3.0.0 的类型用 React 18 FunctionComponent (returns ReactNode | Promise<ReactNode>)
// 与 React 19 RC 严格类型不兼容 — 用 any cast 绕过
import {
  ComposableMap as _ComposableMap,
  Geographies as _Geographies,
  Geography as _Geography,
  Marker as _Marker,
} from "react-simple-maps";
import type { City } from "@/lib/types";
import { citiesWithCoords } from "@/lib/city-stats";
import { cn } from "@/lib/utils";

const ComposableMap: any = _ComposableMap;
const Geographies: any = _Geographies;
const Geography: any = _Geography;
const Marker: any = _Marker;

/** 免费 topojson — jsDelivr CDN（react-simple-maps 官方推荐） */
const GEO_URL =
  "https://cdn.jsdelivr.net/npm/world-atlas@2/countries-110m.json";

interface Props {
  cities: City[];
  className?: string;
}

/** 世界地图视图 — 城市点按 lat/lon 标注，点击跳详情 */
export function WorldMapView({ cities, className }: Props) {
  const withCoords = React.useMemo(() => citiesWithCoords(cities), [cities]);

  if (withCoords.length === 0) {
    return (
      <div className={cn("text-sm text-ink-500 py-4", className)}>
        暂无坐标数据
      </div>
    );
  }

  return (
    <div className={cn("rounded-md border border-ink-100 bg-white p-4", className)}>
      <div className="mb-2 flex items-center justify-between">
        <div className="text-sm text-ink-500">
          全球保障网络 ·{" "}
          <span className="font-medium text-ink-900">{withCoords.length}</span>{" "}
          个有坐标城市
        </div>
        <div className="text-xs text-ink-500">
          <span className="inline-block h-2 w-2 rounded-full bg-primary align-middle" />{" "}
          城市
        </div>
      </div>
      <div className="overflow-hidden rounded">
        <ComposableMap
          projection="geoEqualEarth"
          width={900}
          height={420}
          projectionConfig={{ scale: 130 }}
          style={{ width: "100%", height: "auto" }}
        >
          <Geographies geography={GEO_URL}>
            {({ geographies }: { geographies: any[] }) =>
              geographies.map((geo: any) => (
                <Geography
                  key={geo.rsmKey}
                  geography={geo}
                  fill="#EAEAEC"
                  stroke="#D6D6DA"
                  strokeWidth={0.5}
                  style={{
                    default: { outline: "none" },
                    hover: { fill: "#F5F5F7", outline: "none" },
                    pressed: { outline: "none" },
                  }}
                />
              ))
            }
          </Geographies>
          {withCoords.map((c) => (
            <Marker key={c.code} coordinates={[c.lon!, c.lat!]}>
              <Link href={`/city/${encodeURIComponent(c.code)}`}>
                <circle
                  r={3.5}
                  fill="#0969da"
                  stroke="#fff"
                  strokeWidth={0.8}
                  className="cursor-pointer transition hover:fill-primary"
                  style={{ transition: "all 0.15s" }}
                />
                <title>{c.name} ({c.code})</title>
              </Link>
            </Marker>
          ))}
        </ComposableMap>
      </div>
    </div>
  );
}
