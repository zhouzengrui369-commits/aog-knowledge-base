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
  ZoomableGroup as _ZoomableGroup,
} from "react-simple-maps";
// 世界国家边界 (TopoJSON, 108KB). 引用本地包避免 CDN 依赖.
// world-atlas 没自带 TS 类型 — 强类型断言.
import worldGeoData from "world-atlas/countries-110m.json";
import type { City } from "@/lib/types";
import { citiesWithCoords } from "@/lib/city-stats";
import { cn, firstLetter } from "@/lib/utils";
import { ZoomIn, ZoomOut, RotateCcw, MapPin } from "lucide-react";

const ComposableMap: any = _ComposableMap;
const Geographies: any = _Geographies;
const Geography: any = _Geography;
const Marker: any = _Marker;
const ZoomableGroup: any = _ZoomableGroup;

const WORLD_GEO: any = worldGeoData;

/* ============================================================
 *  V3 导航地图模式 — 渐进式 disclosure (3 tier zoom)
 *  ============================================================
 *  Tier 1 (zoom 1-2, 默认) — 国家级
 *    - 国家边界 1px 灰边 + 浅灰底色
 *    - 只显示 TOP 10 枢纽 (按 view_count)
 *    - Dot 大 (10px), 全部显示 IATA + name 标签
 *
 *  Tier 2 (zoom 3-4) — 区域级
 *    - 国家边界 0.5px 细边
 *    - 显示中心 ±30° 范围内所有城市
 *    - Dot 中 (7px), 仅 hover/selected 显示标签
 *
 *  Tier 3 (zoom 5-8) — 城市级
 *    - 国家边界 opacity 0.3 (淡出)
 *    - 显示全部 220 站点
 *    - Dot 小 (4.5px), 仅 hover/selected + 选中附近显示
 *    - 选中城市附近半径 0.5° (≈55km, 解释 NJX "5km 范围" 为城市级 metro 区)
 *
 *  附加:
 *    - 右下角缩略图 (200x100): 完整世界 + 红框显示当前可视范围
 *    - 右侧垂直 zoom slider + 保留 + / - / 重置按钮
 *    - 选中城市 / 程序化 zoom 时, 300ms easeInOut 平滑过渡 (rAF 自实现,
 *      因 react-simple-maps 3.0.0 未暴露 transitionDuration prop)
 * ============================================================ */

const ZOOM_MIN = 1;
const ZOOM_MAX = 8;
const ZOOM_DEFAULT = 1;
const ZOOM_SELECT = 6; // 选中城市时自动 zoom

function getTier(zoom: number): 1 | 2 | 3 {
  if (zoom < 3) return 1;
  if (zoom < 5) return 2;
  return 3;
}

const TIER_DOT_BASE: Record<1 | 2 | 3, number> = {
  1: 10,
  2: 7,
  3: 4.5,
};

const TIER_NEARBY_RADIUS_DEG: Record<1 | 2 | 3, number> = {
  1: 2.5, // ≈280km — 国家级仍用旧值
  2: 2.5, // ≈280km
  3: 0.5, // ≈55km — 城市级 metro (NJX "5km 范围" 解释为 5–50km 城市级 metro)
};

const TIER2_LATLON_RANGE = 30; // ±30° lat/lon
const TIER1_TOP_N = 10;
// tier 3 常显 top N (避免 200+ 标签重叠) — 始终是当前视图最重要 10 个
const TIER_LABEL_TOP_N = 10;

interface Props {
  cities: City[];
  className?: string;
  /** 父级 hover 的字母 — 地图上该字母城市 pulse */
  hoveredLetter?: string | null;
  /** 父级选中的城市 — 自动 pan/zoom + 高亮 + 显示附近 */
  selectedCity?: City | null;
  /** 通知父级城市被选中 */
  onSelectCity?: (city: City | null) => void;
}

/** Tier-aware dot 半径: tier 1 固定 10; tier 2/3 用 log 缩放 */
function dotRadius(c: City, tier: 1 | 2 | 3, maxView: number): number {
  const base = TIER_DOT_BASE[tier];
  if (tier === 1) return base;
  const v = c.view_count || 0;
  if (v <= 0) return Math.max(2.5, base * 0.55);
  // log2 缩放, 让 top 城市稍大, 其他稍小
  const logScale = Math.log2(Math.max(1, v)) * 0.5;
  // maxView 比例也微调: top 60% 的城市稍大
  const isTop = v >= maxView * 0.6;
  const ratio = isTop ? 1 : 0.7;
  return Math.max(base * 0.5, Math.min(base, base * 0.55 + logScale * ratio));
}

/** 全球 220 城市 (按 view_count 降序, view_count=0 排后面) */
function topByViewCount<T extends { view_count?: number }>(
  arr: T[],
  n: number
): T[] {
  return [...arr]
    .sort((a, b) => (b.view_count || 0) - (a.view_count || 0))
    .slice(0, n);
}

/* ============================================================
 *  主组件
 * ============================================================ */
export function WorldMapView({
  cities,
  className,
  hoveredLetter,
  selectedCity,
  onSelectCity,
}: Props) {
  const withCoords = React.useMemo(() => citiesWithCoords(cities), [cities]);
  const [hovered, setHovered] = React.useState<string | null>(null);
  const [zoom, setZoom] = React.useState<number>(ZOOM_DEFAULT);
  const [center, setCenter] = React.useState<[number, number]>([0, 20]);
  const lastSelectedCode = React.useRef<string | null>(null);

  // 平滑动画 ref — 避免 closure stale + 可被 onMoveEnd 取消
  const animFrameRef = React.useRef<number | null>(null);
  const zoomRef = React.useRef(zoom);
  const centerRef = React.useRef(center);
  React.useEffect(() => {
    zoomRef.current = zoom;
  }, [zoom]);
  React.useEffect(() => {
    centerRef.current = center;
  }, [center]);

  const tier: 1 | 2 | 3 = getTier(zoom);

  const maxView = React.useMemo(
    () => Math.max(1, ...withCoords.map((c) => c.view_count || 0)),
    [withCoords]
  );

  const topCities = React.useMemo(
    () => topByViewCount(withCoords, TIER1_TOP_N),
    [withCoords]
  );
  const topTierLabels = React.useMemo(() => {
    return new Set(topByViewCount(withCoords, TIER_LABEL_TOP_N).map((c) => c.code));
  }, [withCoords]);

  // 当前可见城市集 by tier
  const visibleCities = React.useMemo(() => {
    let base: City[];
    if (tier === 1) {
      base = topCities;
    } else if (tier === 2) {
      const [lon, lat] = center;
      base = withCoords.filter((c) => {
        if (c.lat == null || c.lon == null) return false;
        return (
          Math.abs(c.lat - lat) <= TIER2_LATLON_RANGE &&
          Math.abs(c.lon - lon) <= TIER2_LATLON_RANGE
        );
      });
    } else {
      base = withCoords;
    }
    // 选中城市始终包含
    if (selectedCity && !base.find((c) => c.code === selectedCity.code)) {
      return [selectedCity, ...base];
    }
    return base;
  }, [withCoords, tier, center, selectedCity, topCities]);

  // rAF-based 300ms easeInOutQuad 平滑过渡
  const animateTo = React.useCallback(
    (
      targetZoom: number,
      targetCenter: [number, number],
      duration: number = 300
    ) => {
      if (animFrameRef.current != null) {
        cancelAnimationFrame(animFrameRef.current);
        animFrameRef.current = null;
      }
      const startZoom = zoomRef.current;
      const startCenter: [number, number] = [...centerRef.current];
      const startTime = performance.now();
      const step = (now: number) => {
        const t = Math.min(1, (now - startTime) / duration);
        // easeInOutQuad
        const eased = t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;
        setZoom(startZoom + (targetZoom - startZoom) * eased);
        setCenter([
          startCenter[0] + (targetCenter[0] - startCenter[0]) * eased,
          startCenter[1] + (targetCenter[1] - startCenter[1]) * eased,
        ]);
        if (t < 1) {
          animFrameRef.current = requestAnimationFrame(step);
        } else {
          animFrameRef.current = null;
        }
      };
      animFrameRef.current = requestAnimationFrame(step);
    },
    []
  );

  // 暴露给 Playwright / dev: 程序化设置 view (测试用)
  React.useEffect(() => {
    if (typeof window === "undefined") return;
    (window as any).__aogMapView = {
      setView: (z: number, lon: number, lat: number, duration?: number) => {
        animateTo(z, [lon, lat], duration ?? 300);
      },
      getView: () => ({ zoom, center }),
      getTier: () => tier,
    };
    return () => {
      delete (window as any).__aogMapView;
    };
  }, [animateTo, zoom, center, tier]);

  // 选中城市: pan + zoom to 6
  React.useEffect(() => {
    if (!selectedCity) {
      lastSelectedCode.current = null;
      return;
    }
    if (
      selectedCity.lat == null ||
      selectedCity.lon == null ||
      lastSelectedCode.current === selectedCity.code
    ) {
      return;
    }
    lastSelectedCode.current = selectedCity.code;
    animateTo(ZOOM_SELECT, [selectedCity.lon, selectedCity.lat], 300);
  }, [
    selectedCity?.code,
    selectedCity?.lat,
    selectedCity?.lon,
    selectedCity,
    animateTo,
  ]);

  // 选中城市的附近城市 (tier 决定半径)
  const nearbyCodes = React.useMemo(() => {
    if (
      !selectedCity ||
      selectedCity.lat == null ||
      selectedCity.lon == null
    ) {
      return new Set<string>();
    }
    const radius = TIER_NEARBY_RADIUS_DEG[tier];
    const slat = selectedCity.lat;
    const slon = selectedCity.lon;
    const arr = withCoords
      .filter(
        (c) =>
          c.code !== selectedCity.code && c.lat != null && c.lon != null
      )
      .map((c) => {
        const dlat = (c.lat as number) - slat;
        const dlon = (c.lon as number) - slon;
        const d = dlat * dlat + dlon * dlon;
        return { code: c.code, d };
      })
      .filter((x) => Math.sqrt(x.d) <= radius)
      .sort((a, b) => a.d - b.d)
      .slice(0, 8)
      .map((x) => x.code);
    return new Set(arr);
  }, [selectedCity?.code, selectedCity?.lat, selectedCity?.lon, withCoords, tier]);

  // 国家边界样式 by tier
  const countryStyle = React.useMemo(() => {
    if (tier === 1) {
      return {
        fill: "#fafafa",
        stroke: "#d4d4d8",
        strokeWidth: 1,
        opacity: 1,
      };
    }
    if (tier === 2) {
      return {
        fill: "#fafafa",
        stroke: "#d4d4d8",
        strokeWidth: 0.5,
        opacity: 1,
      };
    }
    return {
      fill: "#fafafa",
      stroke: "#d4d4d8",
      strokeWidth: 0.5,
      opacity: 0.3,
    };
  }, [tier]);

  if (withCoords.length === 0) {
    return (
      <div className={cn("py-4 text-sm text-ink-500", className)}>
        暂无坐标数据
      </div>
    );
  }

  const tierBadgeColor = {
    1: "bg-blue-100 text-blue-700",
    2: "bg-amber-100 text-amber-700",
    3: "bg-red-100 text-red-700",
  }[tier];
  const tierLabel = {
    1: "国家级 · TOP 10 枢纽",
    2: "区域级 · ±30° 范围",
    3: "城市级 · 全部站点",
  }[tier];
  const tierBadge = {
    1: "T1",
    2: "T2",
    3: "T3",
  }[tier];

  return (
    <div
      className={cn(
        "relative h-full overflow-hidden rounded-lg border border-ink-100 bg-white",
        className
      )}
    >
      {/* 顶部状态条 */}
      <div className="flex items-center justify-between border-b border-ink-100 bg-ink-50/40 px-3 py-1.5 text-[11px] text-ink-500">
        <div className="flex items-center gap-3">
          <span className="inline-flex items-center gap-1">
            <MapPin className="h-3 w-3" />
            <span>
              <span className="font-medium text-ink-900">
                {withCoords.length}
              </span>{" "}
              个城市已上图
            </span>
          </span>
          <span className="hidden items-center gap-1.5 sm:inline-flex">
            <span
              className={cn(
                "rounded px-1.5 py-0.5 text-[10px] font-bold",
                tierBadgeColor
              )}
            >
              {tierBadge}
            </span>
            <span>{tierLabel}</span>
          </span>
        </div>
        <span className="tabular-nums">
          zoom {zoom.toFixed(1)}x · {visibleCities.length} 站
        </span>
      </div>

      {/* Map area */}
      <div className="relative">
        <div className="aspect-[2/1] w-full">
          <ComposableMap
            projection="geoEqualEarth"
            width={900}
            height={450}
            projectionConfig={{ scale: 140 }}
            style={{ width: "100%", height: "100%" }}
          >
            <ZoomableGroup
              zoom={zoom}
              center={center}
              onMoveEnd={(pos: any) => {
                // 用户拖动 / wheel 完成 — 取消任何进行中的程序化动画
                if (animFrameRef.current != null) {
                  cancelAnimationFrame(animFrameRef.current);
                  animFrameRef.current = null;
                }
                setZoom(pos.zoom);
                setCenter(pos.coordinates);
              }}
              minZoom={ZOOM_MIN}
              maxZoom={ZOOM_MAX}
            >
              {/* 国家边界 — tier 1/2/3 不同样式 (transition 平滑) */}
              <Geographies geography={WORLD_GEO}>
                {({ geographies }: { geographies: any[] }) =>
                  geographies.map((geo: any) => (
                    <Geography
                      key={geo.rsmKey}
                      geography={geo}
                      fill={countryStyle.fill}
                      stroke={countryStyle.stroke}
                      strokeWidth={countryStyle.strokeWidth}
                      style={{
                        default: {
                          outline: "none",
                          opacity: countryStyle.opacity,
                          transition:
                            "opacity 0.3s ease-in-out, stroke-width 0.3s ease-in-out",
                        },
                        hover: {
                          fill: "#e5e7eb",
                          outline: "none",
                          opacity: countryStyle.opacity,
                        },
                        pressed: { outline: "none" },
                      }}
                    />
                  ))
                }
              </Geographies>

              {/* 城市 dots */}
              {visibleCities.map((c) => {
                const r = dotRadius(c, tier, maxView);
                const v = c.view_count || 0;
                const isTop = v >= maxView * 0.6;
                const isHover = hovered === c.code;
                const isSelected = selectedCity?.code === c.code;
                const isNearby = nearbyCodes.has(c.code);
                const letter = firstLetter(c.code);
                const isLetterPulse =
                  hoveredLetter != null &&
                  letter === hoveredLetter &&
                  !isSelected;

                const fill = isSelected
                  ? "#dc2626"
                  : isHover
                  ? "#1e40af"
                  : isTop || tier === 1
                  ? "#1e40af"
                  : "#6b7280";
                const fillOpacity = isSelected
                  ? 1
                  : isHover
                  ? 1
                  : isNearby
                  ? 0.55
                  : tier === 1
                  ? 1
                  : isTop
                  ? 0.95
                  : 0.7;

                // label 规则:
                //   - selected / hovered / letter-pulse 始终显示
                //   - tier 1: 全部显示 (国家级 10 城市, 空间够)
                //   - tier 2: 仅 selected / hovered / letter-pulse (避免 ±30° 162 城全标重叠)
                //   - tier 3: selected / hovered / letter-pulse + top 10 (重要枢纽一直可见)
                //   - nearby 不显示 (保持地图干净)
                const showLabel =
                  isSelected ||
                  isHover ||
                  isLetterPulse ||
                  tier === 1 ||
                  (tier === 3 && topTierLabels.has(c.code) && !isNearby);

                const iataText =
                  c.iata && c.iata !== "—" ? c.iata : "";

                // SVG 文字随 zoom 缩放, 不同 tier 用不同 source size 让最终显示合理:
                //   tier 1 (zoom 1)   source 11px → display 11px
                //   tier 2 (zoom 3-4) source 4px  → display 12-16px
                //   tier 3 (zoom 5-8) source 2.5px → display 12-20px
                const labelFontSize = tier === 1 ? 11 : tier === 2 ? 4 : 2.5;
                const nameFontSize = isSelected
                  ? Math.max(3, labelFontSize + 0.5)
                  : labelFontSize;

                return (
                  <Marker
                    key={c.code}
                    coordinates={[c.lon!, c.lat!]}
                    onMouseEnter={() => setHovered(c.code)}
                    onMouseLeave={() => setHovered(null)}
                  >
                    <g
                      onClick={(e: any) => {
                        e.stopPropagation?.();
                        onSelectCity?.(isSelected ? null : c);
                      }}
                      style={{ cursor: "pointer" }}
                    >
                      {/* selected city — 大圈 + pulse ring */}
                      {isSelected && (
                        <>
                          <circle
                            r={r + 8}
                            fill="#dc2626"
                            fillOpacity={0.12}
                            stroke="none"
                          >
                            <animate
                              attributeName="r"
                              from={r + 4}
                              to={r + 14}
                              dur="1.5s"
                              repeatCount="indefinite"
                            />
                            <animate
                              attributeName="fillOpacity"
                              from="0.18"
                              to="0"
                              dur="1.5s"
                              repeatCount="indefinite"
                            />
                          </circle>
                          <circle
                            r={r + 3}
                            fill="none"
                            stroke="#dc2626"
                            strokeWidth={1.5}
                          />
                        </>
                      )}

                      {/* hovered letter — pulse 圈 */}
                      {isLetterPulse && (
                        <circle
                          r={r + 5}
                          fill="none"
                          stroke="#1e40af"
                          strokeWidth={1.2}
                          opacity={0.7}
                        >
                          <animate
                            attributeName="r"
                            from={r + 2}
                            to={r + 9}
                            dur="1.2s"
                            repeatCount="indefinite"
                          />
                          <animate
                            attributeName="opacity"
                            from="0.7"
                            to="0"
                            dur="1.2s"
                            repeatCount="indefinite"
                          />
                        </circle>
                      )}

                      {/* top / hover 外圈 */}
                      {(isTop || tier === 1) && !isSelected && (
                        <circle
                          r={r + 3}
                          fill="#1e40af"
                          fillOpacity={0.12}
                          stroke="none"
                        />
                      )}

                      {/* 主 dot */}
                      <circle
                        r={r}
                        fill={fill}
                        fillOpacity={fillOpacity}
                        stroke="#fff"
                        strokeWidth={0.8}
                        style={{ transition: "all 0.15s" }}
                      />

                      {/* IATA + name 标签 */}
                      {showLabel && (
                        <g pointerEvents="none">
                          {iataText && (
                            <text
                              textAnchor="middle"
                              y={-(r + 14)}
                              style={{
                                fontFamily:
                                  "-apple-system, BlinkMacSystemFont, sans-serif",
                                fontSize: labelFontSize,
                                fontWeight: 700,
                                fill: isSelected ? "#dc2626" : "#1e40af",
                                letterSpacing: 0.5,
                              }}
                            >
                              {iataText}
                            </text>
                          )}
                          <text
                            textAnchor="middle"
                            y={-(r + 4)}
                            style={{
                              fontFamily:
                                "-apple-system, BlinkMacSystemFont, sans-serif",
                              fontSize: nameFontSize,
                              fontWeight: isSelected || isHover ? 700 : 500,
                              fill: isSelected ? "#111827" : "#374151",
                            }}
                          >
                            {c.name}
                          </text>
                        </g>
                      )}
                    </g>
                  </Marker>
                );
              })}
            </ZoomableGroup>
          </ComposableMap>
        </div>

        {/* 右侧控制条: slider + 按钮 (V3) */}
        <div className="absolute right-3 top-1/2 flex -translate-y-1/2 flex-col items-center gap-1.5">
          <button
            type="button"
            onClick={() => {
              const next = Math.min(ZOOM_MAX, zoom * 1.4);
              animateTo(next, center, 200);
            }}
            className="grid h-7 w-7 place-items-center rounded-md border border-ink-100 bg-white text-ink-500 shadow-soft transition hover:bg-ink-50 hover:text-ink-900"
            aria-label="放大"
            title={`放大 (${zoom.toFixed(1)}x)`}
          >
            <ZoomIn className="h-3.5 w-3.5" />
          </button>

          <div className="my-0.5 rounded-md border border-ink-100 bg-white p-1 shadow-soft">
            <VerticalZoomSlider
              value={zoom}
              min={ZOOM_MIN}
              max={ZOOM_MAX}
              onChange={(v) => animateTo(v, center, 120)}
            />
          </div>

          <button
            type="button"
            onClick={() => {
              const next = Math.max(ZOOM_MIN, zoom / 1.4);
              animateTo(next, center, 200);
            }}
            className="grid h-7 w-7 place-items-center rounded-md border border-ink-100 bg-white text-ink-500 shadow-soft transition hover:bg-ink-50 hover:text-ink-900"
            aria-label="缩小"
            title={`缩小 (${zoom.toFixed(1)}x)`}
          >
            <ZoomOut className="h-3.5 w-3.5" />
          </button>

          <div className="my-0.5 h-px w-5 bg-ink-100" />

          <button
            type="button"
            onClick={() => {
              animateTo(ZOOM_DEFAULT, [0, 20], 250);
              onSelectCity?.(null);
            }}
            className="grid h-7 w-7 place-items-center rounded-md border border-ink-100 bg-white text-ink-500 shadow-soft transition hover:bg-ink-50 hover:text-ink-900"
            aria-label="重置"
            title="重置视图"
          >
            <RotateCcw className="h-3 w-3" />
          </button>
        </div>

        {/* 缩略图 (bottom-right) — 显示当前可视范围 */}
        <MiniMap zoom={zoom} center={center} />

        {/* 选中城市 footer (Vercel 风格 chip) */}
        {selectedCity && (
          <Link
            href={`/city/${encodeURIComponent(selectedCity.code)}`}
            className="absolute bottom-3 left-3 inline-flex max-w-[55%] items-center gap-2 rounded-md border border-red-200 bg-white/95 px-3 py-1.5 text-xs shadow-soft backdrop-blur transition hover:border-red-300 hover:bg-white"
          >
            <span className="inline-block h-2 w-2 rounded-full bg-red-500" />
            <span className="font-semibold text-ink-900">
              {selectedCity.name}
            </span>
            {selectedCity.iata && selectedCity.iata !== "—" && (
              <span className="rounded bg-red-50 px-1.5 py-0.5 text-[10px] font-medium tabular-nums text-red-700">
                {selectedCity.iata}
              </span>
            )}
            <span className="text-ink-500">
              · 周边 {nearbyCodes.size} 站 ({TIER_NEARBY_RADIUS_DEG[tier]}°)
            </span>
            <span className="ml-1 text-primary">→</span>
          </Link>
        )}

        {/* Footer caption (右下角 mini-map 旁边避让) */}
        <div className="pointer-events-none absolute left-3 top-3 hidden flex-col gap-0.5 text-[10px] text-ink-400 sm:flex">
          <span>滚轮缩放 · 拖动平移</span>
          <span>点城市查看周边</span>
        </div>
      </div>
    </div>
  );
}

/* ============================================================
 *  VerticalZoomSlider — 自定义垂直滑块
 *  - 鼠标拖动 / 点击 track 都触发 onChange
 *  - 当前 zoom 数值显示在 thumb 位置
 * ============================================================ */
function VerticalZoomSlider({
  value,
  min,
  max,
  onChange,
}: {
  value: number;
  min: number;
  max: number;
  onChange: (v: number) => void;
}) {
  const trackRef = React.useRef<HTMLDivElement>(null);
  const draggingRef = React.useRef(false);

  const updateFromY = React.useCallback(
    (clientY: number) => {
      const el = trackRef.current;
      if (!el) return;
      const rect = el.getBoundingClientRect();
      // top = max, bottom = min
      const t = 1 - (clientY - rect.top) / rect.height;
      const clamped = Math.max(0, Math.min(1, t));
      onChange(min + clamped * (max - min));
    },
    [min, max, onChange]
  );

  React.useEffect(() => {
    const onMove = (e: MouseEvent) => {
      if (draggingRef.current) updateFromY(e.clientY);
    };
    const onUp = () => {
      draggingRef.current = false;
    };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    return () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
  }, [updateFromY]);

  const pct = ((value - min) / (max - min)) * 100;

  return (
    <div
      className="relative flex h-32 w-6 flex-col items-center"
      title={`缩放 ${value.toFixed(1)}x`}
    >
      {/* 刻度数字 (top = max, bottom = min) */}
      <div className="mb-0.5 text-[8px] font-medium tabular-nums text-ink-400">
        {max}
      </div>

      {/* track */}
      <div
        ref={trackRef}
        onMouseDown={(e) => {
          draggingRef.current = true;
          updateFromY(e.clientY);
          e.preventDefault();
        }}
        className="relative h-24 w-1.5 cursor-pointer rounded-full bg-ink-100"
      >
        {/* filled portion (从 thumb 到底部) */}
        <div
          className="absolute bottom-0 left-0 right-0 rounded-full bg-primary/40 transition-[height] duration-150"
          style={{ height: `${pct}%` }}
        />
        {/* thumb */}
        <div
          className="absolute left-1/2 h-2.5 w-2.5 -translate-x-1/2 rounded-full border-2 border-primary bg-white shadow-sm transition-[bottom] duration-150"
          style={{ bottom: `calc(${pct}% - 5px)` }}
        />
      </div>

      {/* 刻度数字 (bottom = min) */}
      <div className="mt-0.5 text-[8px] font-medium tabular-nums text-ink-400">
        {min}
      </div>
    </div>
  );
}

/* ============================================================
 *  MiniMap — 200x100 缩略图 + 红框
 *  - 独立 ComposableMap (固定 zoom 1, 简化版 d3 projection)
 *  - 红框: 中心 = main center, 尺寸 = full_size / zoom
 *  - 极简等距矩形近似 (非精准 d3) — 足够示意当前可视范围
 * ============================================================ */
function MiniMap({
  zoom,
  center,
}: {
  zoom: number;
  center: [number, number];
}) {
  const W = 200;
  const H = 100;
  // equirectangular 近似: lon → x 线性, lat → y 线性
  const centerX = ((center[0] + 180) / 360) * W;
  const centerY = ((90 - center[1]) / 180) * H;
  // 红框大小: 主图 zoom Z 时, 1/Z 的世界在视口内
  const rectW = Math.max(8, Math.min(W, W / zoom));
  const rectH = Math.max(4, Math.min(H, H / zoom));
  const rectX = Math.max(0, Math.min(W - 4, centerX - rectW / 2));
  const rectY = Math.max(0, Math.min(H - 4, centerY - rectH / 2));

  return (
    <div className="pointer-events-none absolute bottom-3 right-16 overflow-hidden rounded-md border border-ink-200 bg-white shadow-soft">
      <div className="relative" style={{ width: W, height: H }}>
        <ComposableMap
          projection="geoEqualEarth"
          width={W}
          height={H}
          projectionConfig={{ scale: 31 }}
          style={{ width: "100%", height: "100%" }}
        >
          <Geographies geography={WORLD_GEO}>
            {({ geographies }: { geographies: any[] }) =>
              geographies.map((geo: any) => (
                <Geography
                  key={geo.rsmKey}
                  geography={geo}
                  fill="#f5f5f4"
                  stroke="#d4d4d8"
                  strokeWidth={0.2}
                  style={{
                    default: { outline: "none" },
                    hover: { outline: "none" },
                    pressed: { outline: "none" },
                  }}
                />
              ))
            }
          </Geographies>
        </ComposableMap>
        {/* viewport red rect + center dot */}
        <svg
          width={W}
          height={H}
          viewBox={`0 0 ${W} ${H}`}
          className="absolute inset-0"
        >
          <rect
            x={rectX}
            y={rectY}
            width={Math.min(rectW, W - rectX)}
            height={Math.min(rectH, H - rectY)}
            fill="rgba(220, 38, 38, 0.12)"
            stroke="#dc2626"
            strokeWidth={1.5}
            rx={2}
          />
          <circle cx={centerX} cy={centerY} r={2} fill="#dc2626" />
        </svg>
      </div>
      <div className="border-t border-ink-100 bg-white px-1.5 py-0.5 text-center text-[9px] tabular-nums text-ink-400">
        缩略图 · {zoom.toFixed(1)}x
      </div>
    </div>
  );
}
