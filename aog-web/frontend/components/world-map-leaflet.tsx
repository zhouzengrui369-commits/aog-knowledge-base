"use client";

import * as React from "react";
import {
  MapContainer,
  TileLayer,
  CircleMarker,
  Tooltip,
  ZoomControl,
  useMap,
  useMapEvents,
  Marker,
} from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import Link from "next/link";
import { MapPin, RotateCcw, ZoomIn, ZoomOut, X } from "lucide-react";
import type { City } from "@/lib/types";
import { citiesWithCoords } from "@/lib/city-stats";
import { cn, firstLetter } from "@/lib/utils";
import type { Airline, Airport } from "@/lib/types";
import { getAirports } from "@/lib/api";
import Supercluster from "supercluster";

/* ============================================================
 *  V16 — react-leaflet 嵌入主图
 *  保留 V8-V14 视觉特性 (NJX 拍过的):
 *  - hub label (top 6 永远 + 其他 zoom>=5) — V9
 *  - 普通城市 T3 (zoom>=3) — V11
 *  - label 在 dot 右侧 (Tooltip direction="right" offset=[8,0]) — V7
 *  - hub label 中文名（无 IATA）— V10
 *  - 字号 constant 实际像素（leaflet Tooltip 直接 CSS 字号, 不需要 N/zoom 公式）
 *  - 选中态 pulse ring (CircleMarker 加大半径) — V7
 *  - 选中 chip bottom-left (V5)
 *  - click → /city/{code} uppercase (V14)
 *  - 智能 404 兼容 (V12.2 client useEffect, 不需 file path)
 *  - 中文 file path (V13, 不需 router.push)
 *
 *  V16 新增 (react-leaflet):
 *  - MapContainer + TileLayer (OSM: 真实 tile, 不是轮廓线)
 *  - CircleMarker (radius constant 像素, 不受 zoom 影响)
 *  - Tooltip permanent (label 永远显示, 跟 V8 N/zoom constant 像素效果一致)
 *  - smooth flyTo (leaflet 原生, 替代 V8 自写 rAF)
 *  - zoom 控件、attribution
 *
 *  V17 新增:
 *  - airlines prop: 航司数据 (Sprint C, 公网 backend 25 家 / dev fallback MOCK)
 *  - airlineHubsByCity: Map<city_code, Airline[]>  (聚合各 city 的航司 hub)
 *  - city CircleMarker 外层加紫色环 (#7c3aed, radius + 6) 标识有航司 hub
 *  - tooltip 显示航司 IATA + 简称/中文名 (国航 CA / 东航 MU / 南航 CZ 等)
 *
 *  V20 新增 (NJX 拍 C — 两层叠加 + 颜色区分):
 *  - airports prop (可选): 全局机场列表 (OpenFlights 6072 站)
 *  - 如未传 → useEffect 懒加载 /data/global-airports.json (public 静态资源)
 *  - AOG 城市保持现有红/蓝/灰颜色 (cities 渲染逻辑不变)
 *  - 非 AOG 机场: 灰色小点 (#9ca3af, radius 1.5, fillOpacity 0.55, no event)
 *  - zoom < 4: supercluster 聚合灰点 (避免 6072 DOM node 同时渲染)
 *  - zoom >= 4: 散开所有灰点 (视口内 ~600-1000 节点, 可接受)
 *  - 缩略图: 地图 bottom-left 浮窗, 显示 top 12 国家机场数 (V20 面板)
 *
 *  V21 新增 (NJX 拍 C — 页面太拥挤简化):
 *  - AirlineHubDot tooltip: 限 top 5 航司 + "还有 N 家" 折叠 (北京 9 航司堆叠)
 *  - 缩略图面板: 12 → top 6 国家, 2 列 → 单列, max-w-280px → w-48 (紧凑)
 *  - aogCodesByCountry map: 一次扫描, 面板里直接 O(1) 查 AOG 数字
 *  - 数据/底层逻辑 (218 城市 + 6072 全球机场 + AOG 紫环 + 灰点) 全部保留
 *
 *  V22 新增 (NJX 拍 B — 数字徽章 + flyTo 放大 + 右侧 panel):
 *  - 推翻 V21 "tooltip 限 5" 方案 (NJX 反馈堆叠还是堆叠)
 *  - AirlineHubDot → AirlineHubBadge: 紫环装饰保留 + 中心数字徽章 divIcon
 *  - 数字 = N 家航司 (大圆 28x28 + 白字 14px)
 *  - 选中态: ring-2 amber + scale 1.1
 *  - click badge → map.flyTo(city, zoom 5) + 右侧滑出 AirlineHubPanel
 *  - AirlineHubPanel: 320px 宽, 顶部 close (X) + ESC 关闭, 列 N 航司 (IATA + 中文名 + 联盟 badge + 基地)
 *  - 零堆叠, 零永久 tooltip, 北京 9 航司显示为 "9"
 *
 *  React 19 strict mode 防御: mounted 状态 gate (避免 "Map container is already initialized")
 * ============================================================ */

const HUB_TOP_N = 15; // 国家级 hub 数量
const HUB_LABEL_TOP_N = 6; // V9: 区域级 (T2) 只显示 top 6 hub label
const ZOOM_MIN = 1;
const ZOOM_MAX = 8;
const ZOOM_SELECT = 6;
const ZOOM_DEFAULT = 4;
const TIER2_LATLON_RANGE = 20;
const TIER_NEARBY_RADIUS_DEG: Record<1 | 2 | 3, number> = {
  1: 2.5,
  2: 2.5,
  3: 0.5,
};

function getTier(zoom: number): 1 | 2 | 3 {
  if (zoom < 3) return 1;
  if (zoom < 5) return 2;
  return 3;
}

function computeHubs(cities: City[]): {
  hubSet: Set<string>;
  labelSet: Set<string>;
} {
  const sorted = [...cities]
    .filter((c) => (c.view_count || 0) > 0)
    .sort((a, b) => (b.view_count || 0) - (a.view_count || 0));
  const topN = sorted.slice(0, HUB_TOP_N);
  const labelTopN = sorted.slice(0, HUB_LABEL_TOP_N);
  return {
    hubSet: new Set(topN.map((c) => c.code)),
    labelSet: new Set(labelTopN.map((c) => c.code)),
  };
}

interface Props {
  cities: City[];
  /** V17: 航司列表 (Sprint C) — city 上叠加航司 hub 紫色环 + tooltip */
  airlines?: Airline[];
  /** V20: 全球机场 (OpenFlights 6072) — 灰点 layer. 如不传则组件内 fetch 静态 JSON */
  airports?: Airport[];
  className?: string;
  /** 父级 hover 的字母 — 地图上该字母城市 pulse */
  hoveredLetter?: string | null;
  /** 父级选中的城市 — 自动 pan/zoom + 高亮 + 显示附近 */
  selectedCity?: City | null;
  /** 通知父级城市被选中 */
  onSelectCity?: (city: City | null) => void;
}

/* ============================================================
 *  MapController — 跑在 MapContainer 内部, 暴露 map ref + 处理事件
 * ============================================================ */
function MapController({
  onZoomEnd,
  onCenterEnd,
  onMapReady,
  selectedCity,
  lastSelectedCodeRef,
  hovered,
  setHovered,
  setMouseAnchor,
}: {
  onZoomEnd: (zoom: number) => void;
  onCenterEnd: (center: [number, number]) => void;
  onMapReady: (map: L.Map) => void;
  selectedCity: City | null;
  lastSelectedCodeRef: React.MutableRefObject<string | null>;
  hovered: string | null;
  setHovered: (code: string | null) => void;
  setMouseAnchor: (a: { x: number; y: number } | null) => void;
}) {
  const map = useMap();

  React.useEffect(() => {
    onMapReady(map);
    return () => {
      // do not call map.remove() — React Leaflet handles cleanup
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [map]);

  useMapEvents({
    zoomend: () => {
      onZoomEnd(map.getZoom());
      const c = map.getCenter();
      onCenterEnd([c.lat, c.lng]);
    },
    moveend: () => {
      const c = map.getCenter();
      onCenterEnd([c.lat, c.lng]);
    },
    mousemove: (e) => {
      if (e.containerPoint) {
        setMouseAnchor({ x: e.containerPoint.x, y: e.containerPoint.y });
      }
    },
    mouseout: () => {
      setHovered(null);
      setMouseAnchor(null);
    },
  });

  // 选中城市: flyTo (代替 V14 自写 rAF)
  React.useEffect(() => {
    if (!selectedCity) {
      lastSelectedCodeRef.current = null;
      return;
    }
    if (
      selectedCity.lat == null ||
      selectedCity.lon == null ||
      lastSelectedCodeRef.current === selectedCity.code
    ) {
      return;
    }
    lastSelectedCodeRef.current = selectedCity.code;
    map.flyTo([selectedCity.lat, selectedCity.lon], ZOOM_SELECT, {
      duration: 0.6,
    });
  }, [selectedCity?.code, selectedCity?.lat, selectedCity?.lon, map]);

  // 暴露给 Playwright / dev (跟 V14 一致)
  React.useEffect(() => {
    (window as any).__aogMapView = {
      setView: (z: number, lon: number, lat: number, duration?: number) => {
        map.flyTo([lat, lon], z, { duration: (duration ?? 300) / 1000 });
      },
      getView: () => ({
        zoom: map.getZoom(),
        center: (() => {
          const c = map.getCenter();
          return [c.lng, c.lat];
        })(),
      }),
    };
    return () => {
      delete (window as any).__aogMapView;
    };
  }, [map]);

  return null;
}

/* ============================================================
 *  CityDot — 单城市 marker (CircleMarker + optional permanent Tooltip)
 * ============================================================ */
function CityDot({
  city,
  isHub,
  isLabel,
  isSelected,
  isHovered,
  isLetterPulse,
  isNearby,
  showLabel,
  onSelect,
  setHovered,
}: {
  city: City;
  isHub: boolean;
  isLabel: boolean;
  isSelected: boolean;
  isHovered: boolean;
  isLetterPulse: boolean;
  isNearby: boolean;
  showLabel: boolean;
  onSelect?: (city: City | null) => void;
  setHovered: (code: string | null) => void;
}) {
  // V8: dot 半径 constant 像素 (CircleMarker 半径就是像素, leaflet 不会随 zoom 改)
  const r = isHub ? 5 : 3;
  // 选中态外圈 (pulse ring 用一个外层 transparent circle)
  const fill = isSelected
    ? "#dc2626"
    : isHub
    ? "#2563eb"
    : isHovered
    ? "#1e40af"
    : "#9ca3af";
  const fillOpacity = isSelected
    ? 1
    : isHovered
    ? 1
    : isNearby
    ? 0.7
    : isHub
    ? 0.95
    : 0.65;

  return (
    <>
      {/* V7: 选中态 pulse ring — 外层 transparent circle 加大半径 + CSS animation */}
      {isSelected && (
        <CircleMarker
          center={[city.lat!, city.lon!]}
          radius={r + 7}
          pathOptions={{
            color: "#dc2626",
            weight: 1.5,
            fillColor: "#dc2626",
            fillOpacity: 0.15,
            className: "selected-pulse-ring",
          }}
          interactive={false}
        />
      )}
      {/* letter pulse (V6 行为) */}
      {isLetterPulse && (
        <CircleMarker
          center={[city.lat!, city.lon!]}
          radius={r + 4}
          pathOptions={{
            color: "#1e40af",
            weight: 1,
            fillOpacity: 0,
            className: "letter-pulse-ring",
          }}
          interactive={false}
        />
      )}
      <CircleMarker
        center={[city.lat!, city.lon!]}
        radius={r}
        pathOptions={{
          color: isHub || isSelected ? "#ffffff" : "none",
          weight: isHub || isSelected ? 2 : 0,
          fillColor: fill,
          fillOpacity: fillOpacity,
        }}
        eventHandlers={{
          click: () => {
            onSelect?.(isSelected ? null : city);
            // V14: 同步触发 chip 内 Link 跳转 (但用 onSelectCity 控选中态, 不直接 navigate)
            // 用户再点 chip 才真跳
          },
          mouseover: () => setHovered(city.code),
          mouseout: () => setHovered(null),
        }}
      >
        {showLabel && (
          <Tooltip
            permanent
            direction="right"
            offset={[8, 0]}
            opacity={1}
            className="city-label-tooltip"
          >
            <span
              className={cn(
                "inline-block whitespace-nowrap rounded px-1.5 py-0.5 text-[12px] font-semibold",
                isHub ? "hub-label" : "city-label",
                isSelected && "selected-label"
              )}
              style={{
                fontFamily:
                  "-apple-system, BlinkMacSystemFont, 'PingFang SC', 'Microsoft YaHei', sans-serif",
              }}
            >
              {city.name}
            </span>
          </Tooltip>
        )}
      </CircleMarker>
    </>
  );
}

/* ============================================================
 *  V17→V22 — AirlineHubBadge
 *  V17: 紫环 + permanent tooltip 显示航司 (堆叠严重)
 *  V21: 紫环 + tooltip 限 5 (NJX 反馈堆叠还是堆叠, 治标)
 *  V22 (NJX 拍 B): 紫环 + 中心数字徽章 (大圆 + 白字 N) + click → flyTo + 右侧 panel
 *  - 紫环: 装饰层, 永远显示 (hub city 半径 11, 普通 9)
 *  - 数字徽章: 紫底白字, 28x28 圆, z-index 提到 city dot 之上
 *  - 选中态: ring-2 ring-amber-400 + scale 1.1
 *  - click: 调用 onHubClick → map.flyTo + setAirlinePanel
 *  - interactive: true (徽章可点; 紫环背景仍 false 不挡 city)
 * ============================================================ */

function AirlineHubBadge({
  city,
  airlines,
  active,
  onHubClick,
}: {
  city: City;
  airlines: Airline[];
  active: boolean;
  onHubClick?: (city: City, airlines: Airline[]) => void;
}) {
  if (city.lat == null || city.lon == null) return null;
  const isHub = (city.view_count || 0) > 0;
  const r = isHub ? 5 : 3;
  const count = airlines.length;
  if (count === 0) return null; // 没航司不渲染 (防御)
  return (
    <>
      {/* 紫环装饰 — 背景, 不可点 */}
      <CircleMarker
        center={[city.lat, city.lon]}
        radius={r + 6}
        pathOptions={{
          color: "#7c3aed",
          weight: 2,
          fillColor: "#7c3aed",
          fillOpacity: 0.08,
        }}
        interactive={false}
      />
      {/* 数字徽章 — 中心 divIcon Marker, 可点 */}
      <Marker
        position={[city.lat, city.lon]}
        icon={L.divIcon({
          className: "airline-hub-badge-wrapper",
          html: `<div class="airline-hub-badge ${
            active ? "airline-hub-badge-active" : ""
          }">${count}</div>`,
          iconSize: [28, 28],
          iconAnchor: [14, 14],
        })}
        eventHandlers={{
          click: () => onHubClick?.(city, airlines),
        }}
        keyboard={true}
        title={`${city.name} · ${count} 家航司 hub`}
        zIndexOffset={500}
      />
    </>
  );
}

/* ============================================================
 *  V22 — AirlineHubPanel (右侧浮层, 列出选中城市的所有航司)
 *  - 320px 宽, absolute right-3 top-3 (跟地图右上角浮)
 *  - 顶部 close (X) + ESC 关闭
 *  - 列 N 航司: IATA 大紫字 + 中文名 + 联盟 badge + 基地 (iata 列表)
 *  - 每条航司 整行 hover 高亮, 点击 → 跳 /airlines/<iata>
 *  - 头部: 城市名 + "N 家航司 hub" + view_count
 * ============================================================ */

function AirlineHubPanel({
  city,
  airlines,
  onClose,
}: {
  city: City;
  airlines: Airline[];
  onClose: () => void;
}) {
  // ESC 关闭
  React.useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div
      className="absolute right-3 top-3 z-[600] flex max-h-[440px] w-[320px] flex-col overflow-hidden rounded-lg border border-ink-200 bg-white shadow-soft"
      data-testid="airline-hub-panel"
      style={{
        fontFamily:
          "-apple-system, BlinkMacSystemFont, 'PingFang SC', 'Microsoft YaHei', sans-serif",
      }}
    >
      {/* 头部 */}
      <div className="flex items-start justify-between gap-2 border-b border-ink-100 bg-gradient-to-br from-violet-50 to-white px-3 py-2">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1.5">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-violet-700">
              Airlines Hub
            </span>
            {city.view_count ? (
              <span className="rounded bg-ink-100 px-1 text-[10px] tabular-nums text-ink-600">
                访问 {city.view_count}
              </span>
            ) : null}
          </div>
          <div className="mt-0.5 truncate text-[15px] font-semibold text-ink-900">
            {city.name}
          </div>
          <div className="text-[11px] text-ink-500">
            {city.iata} · {airlines.length} 家航司 hub
          </div>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="grid h-6 w-6 shrink-0 place-items-center rounded text-ink-400 transition hover:bg-ink-100 hover:text-ink-900"
          aria-label="关闭"
          title="关闭 (ESC)"
        >
          <X className="h-3.5 w-3.5" />
        </button>
      </div>

      {/* 航司列表 */}
      <div className="flex-1 overflow-y-auto">
        {airlines.map((a) => {
          const hubHere = (a.hubs || []).find(
            (h) => h.city_code === city.code
          );
          return (
            <Link
              key={a.iata}
              href={`/airlines/${a.iata}`}
              className="group flex items-center gap-2.5 border-b border-ink-50 px-3 py-2 transition hover:bg-violet-50/50"
            >
              <span
                className="grid h-9 w-9 shrink-0 place-items-center rounded-md text-[12px] font-bold tabular-nums text-white"
                style={{ background: "#7c3aed" }}
                title={a.iata}
              >
                {a.iata}
              </span>
              <div className="min-w-0 flex-1">
                <div className="truncate text-[13px] font-medium text-ink-900 group-hover:text-violet-700">
                  {a.name_short || a.name_cn}
                </div>
                <div className="mt-0.5 flex items-center gap-1.5 text-[10px] text-ink-500">
                  {a.alliance && a.alliance !== "无" && (
                    <span className="rounded bg-ink-100 px-1 text-ink-700">
                      {a.alliance}
                    </span>
                  )}
                  {a.fleet_size > 0 && (
                    <span className="tabular-nums">
                      机队 {a.fleet_size}
                    </span>
                  )}
                  {hubHere?.type && (
                    <span
                      className="rounded px-1"
                      style={{
                        background:
                          hubHere.type === "hub" ? "#fef3c7" : "#dbeafe",
                        color:
                          hubHere.type === "hub" ? "#92400e" : "#1e40af",
                      }}
                    >
                      {hubHere.type === "hub" ? "主基地" : "重点"}
                    </span>
                  )}
                </div>
              </div>
            </Link>
          );
        })}
      </div>

      {/* 底部 — flyTo 提示 + 总数 */}
      <div className="flex items-center justify-between border-t border-ink-100 bg-ink-50/40 px-3 py-1.5 text-[10px] text-ink-500">
        <span>点航司行跳详情</span>
        <span className="tabular-nums">{airlines.length} 家</span>
      </div>
    </div>
  );
}

/* ============================================================
 *  ClusterBubble — 聚合点 (T1 zoom ≤ 4 用 supercluster 聚合 hubs)
 *  用 L.divIcon 渲染带数字的气泡
 * ============================================================ */
function clusterIconFactory(count: number, r: number): L.DivIcon {
  const label = count >= 1000 ? `${(count / 1000).toFixed(1)}k` : count;
  return L.divIcon({
    className: "cluster-bubble-wrapper",
    html: `<div class="cluster-bubble" style="width:${r * 2}px;height:${r * 2}px;line-height:${r * 2}px;">${label}</div>`,
    iconSize: [r * 2, r * 2],
    iconAnchor: [r, r],
  });
}

function ClusterMarker({
  count,
  clusterId,
  lat,
  lon,
  cluster,
  zoom,
  mapRef,
}: {
  count: number;
  clusterId: number;
  lat: number;
  lon: number;
  cluster: Supercluster;
  zoom: number;
  mapRef: React.MutableRefObject<L.Map | null>;
}) {
  const r = Math.min(14, 5 + Math.sqrt(count) * 1.5);
  return (
    <Marker
      position={[lat, lon]}
      icon={clusterIconFactory(count, r)}
      eventHandlers={{
        click: () => {
          const expansionZoom =
            cluster.getClusterExpansionZoom(clusterId) ??
            Math.min(ZOOM_MAX, zoom + 1);
          mapRef.current?.flyTo([lat, lon], Math.max(zoom + 0.5, expansionZoom), {
            duration: 0.4,
          });
        },
      }}
    />
  );
}

/* ============================================================
 *  主组件
 * ============================================================ */
export function WorldMapLeaflet({
  cities,
  airlines,
  airports: airportsProp,
  className,
  hoveredLetter,
  selectedCity,
  onSelectCity,
}: Props) {
  // React 19 strict mode 防御 — 第一次 render discard, 不渲染 MapContainer
  const [mounted, setMounted] = React.useState(false);
  React.useEffect(() => {
    setMounted(true);
  }, []);

  const withCoords = React.useMemo(() => citiesWithCoords(cities), [cities]);
  const [zoom, setZoom] = React.useState<number>(ZOOM_DEFAULT);
  const [center, setCenter] = React.useState<[number, number]>([35, 105]);
  const [hovered, setHovered] = React.useState<string | null>(null);
  const [mouseAnchor, setMouseAnchor] = React.useState<{
    x: number;
    y: number;
  } | null>(null);
  const mapRef = React.useRef<L.Map | null>(null);
  const lastSelectedCodeRef = React.useRef<string | null>(null);

  // V22: 航司 hub panel state (NJX 拍 B — flyTo + 右侧 panel)
  // city 选中 → flyTo zoom 5 + 滑出右侧 panel 列 N 航司
  const [airlinePanel, setAirlinePanel] = React.useState<{
    cityCode: string;
    airlines: Airline[];
  } | null>(null);

  // V22: hub badge click handler — flyTo city + 打开 panel
  const handleHubClick = React.useCallback(
    (city: City, airlines: Airline[]) => {
      // toggle: 同一 city 再点关闭
      setAirlinePanel((prev) => {
        if (prev?.cityCode === city.code) return null;
        return { cityCode: city.code, airlines };
      });
      // flyTo 到该 city, zoom 5 (够近看到附近, 不太近避免太小)
      if (mapRef.current && city.lat != null && city.lon != null) {
        mapRef.current.flyTo([city.lat, city.lon], 5, { duration: 0.6 });
      }
    },
    []
  );

  const closeHubPanel = React.useCallback(() => {
    setAirlinePanel(null);
  }, []);

  const tier: 1 | 2 | 3 = getTier(zoom);

  const { hubSet, labelSet } = React.useMemo(
    () => computeHubs(withCoords),
    [withCoords]
  );
  const hubs = React.useMemo(
    () => withCoords.filter((c) => hubSet.has(c.code)),
    [withCoords, hubSet]
  );

  // V17: 航司 hub 聚合 by city_code — Map<city_code, Airline[]>
  // 公网 backend 返 25 航司, dev fallback MOCK 3 航司 (CA/MU/CZ)
  // city_code 缺失 (e.g. MU PVG) → 不入 map (前端只显示有 city_code 的 hub)
  const airlineHubsByCity = React.useMemo(() => {
    const map = new Map<string, Airline[]>();
    if (!airlines || airlines.length === 0) return map;
    for (const a of airlines) {
      if (!a.hubs) continue;
      for (const hub of a.hubs) {
        if (!hub.city_code) continue;
        const list = map.get(hub.city_code) || [];
        list.push(a);
        map.set(hub.city_code, list);
      }
    }
    return map;
  }, [airlines]);

  // V20: 全球机场 (OpenFlights 6072). 如未传 prop → 懒加载 /data/global-airports.json
  const [globalAirports, setGlobalAirports] = React.useState<Airport[]>(
    () => airportsProp || []
  );
  React.useEffect(() => {
    if (airportsProp && airportsProp.length > 0) {
      setGlobalAirports(airportsProp);
      return;
    }
    let cancelled = false;
    getAirports().then((list) => {
      if (!cancelled && list && list.length > 0) setGlobalAirports(list);
    });
    return () => {
      cancelled = true;
    };
  }, [airportsProp]);

  // V20: AOG 城市 IATA 集合 (用于灰点去重 — 已上图的不重复渲染灰点)
  const aogIatas = React.useMemo(() => {
    const s = new Set<string>();
    for (const c of cities) {
      if (c.iata && c.iata !== "—") s.add(c.iata.toUpperCase());
    }
    return s;
  }, [cities]);

  // V20: 非 AOG 机场 (灰点 layer 数据源)
  const nonAogAirports = React.useMemo(() => {
    if (globalAirports.length === 0) return [];
    return globalAirports.filter((a) => !aogIatas.has(a.iata.toUpperCase()));
  }, [globalAirports, aogIatas]);

  // V20: 全局机场 supercluster (zoom < 4 用, 灰点聚合)
  const globalCluster = React.useMemo(() => {
    if (nonAogAirports.length === 0) return null;
    const idx = new Supercluster<
      { iata: string; country: string },
      { country: string }
    >({ radius: 60, maxZoom: 4, minPoints: 4 });
    idx.load(
      nonAogAirports.map((a) => ({
        type: "Feature" as const,
        properties: { iata: a.iata, country: a.country },
        geometry: { type: "Point" as const, coordinates: [a.lon, a.lat] },
      }))
    );
    return idx;
  }, [nonAogAirports]);

  // V20: 当前 viewport 内的灰点 cluster features (zoom < 4)
  const globalClusterFeatures = React.useMemo(() => {
    if (!globalCluster || zoom >= 4) return null;
    return globalCluster.getClusters([-180, -85, 180, 85], Math.floor(zoom));
  }, [globalCluster, zoom]);

  // V20: top 国家机场数 (面板显示用)
  // V21 (NJX 拍 C): top 12 → top 6 (单列更紧凑, 不再 2 列 x 6 行拥挤)
  const topCountries = React.useMemo(() => {
    const counts = new Map<string, number>();
    for (const a of globalAirports) {
      counts.set(a.country, (counts.get(a.country) || 0) + 1);
    }
    return Array.from(counts.entries())
      .sort((a, b) => b[1] - a[1])
      .slice(0, 6);
  }, [globalAirports]);

  // V21: AOG 预案城市 by country map (面板显示每国 AOG 站点数)
  const aogCodesByCountry = React.useMemo(() => {
    const m = new Map<string, number>();
    for (const c of cities) {
      if (!c.iata) continue;
      const iata = c.iata.toUpperCase();
      const airport = globalAirports.find(
        (a) => a.iata.toUpperCase() === iata
      );
      if (!airport) continue;
      m.set(airport.country, (m.get(airport.country) || 0) + 1);
    }
    return m;
  }, [cities, globalAirports]);

  // supercluster — T1 聚合 hubs
  const cluster = React.useMemo(() => {
    if (hubs.length === 0) return null;
    const idx = new Supercluster<
      { code: string; name: string; iata: string },
      any
    >({ radius: 80, maxZoom: 4, minPoints: 2 });
    idx.load(
      hubs
        .filter((c) => c.lat != null && c.lon != null)
        .map((c) => ({
          type: "Feature" as const,
          properties: { code: c.code, name: c.name, iata: c.iata || "" },
          geometry: {
            type: "Point" as const,
            coordinates: [c.lon as number, c.lat as number],
          },
        }))
    );
    return idx;
  }, [hubs]);

  const clusterFeatures = React.useMemo(() => {
    if (!cluster || zoom > 4) return null;
    return cluster.getClusters([-180, -85, 180, 85], Math.floor(zoom));
  }, [cluster, zoom]);

  // 可见城市集 by tier (V14 逻辑保留)
  const visibleCities = React.useMemo(() => {
    let base: City[];
    if (tier === 1) {
      base = hubs;
    } else if (tier === 2) {
      const [lat, lon] = center;
      const inRange = withCoords.filter((c) => {
        if (c.lat == null || c.lon == null) return false;
        return (
          Math.abs(c.lat - lat) <= TIER2_LATLON_RANGE &&
          Math.abs(c.lon - lon) <= TIER2_LATLON_RANGE
        );
      });
      const hubCodes = new Set(hubs.map((c) => c.code));
      const nonHubInRange = inRange.filter(
        (c) => !hubCodes.has(c.code) && (c.view_count || 0) > 0
      );
      base = Array.from(
        new Map([...hubs, ...nonHubInRange].map((c) => [c.code, c])).values()
      );
      base.sort((a, b) => {
        const aH = hubCodes.has(a.code) ? 1 : 0;
        const bH = hubCodes.has(b.code) ? 1 : 0;
        if (aH !== bH) return bH - aH;
        return (b.view_count || 0) - (a.view_count || 0);
      });
    } else {
      base = withCoords;
    }
    if (selectedCity && !base.find((c) => c.code === selectedCity.code)) {
      return [selectedCity, ...base];
    }
    return base;
  }, [withCoords, tier, center, selectedCity, hubs]);

  // 选中城市的附近城市
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
    return new Set(
      withCoords
        .filter(
          (c) => c.code !== selectedCity.code && c.lat != null && c.lon != null
        )
        .map((c) => {
          const dlat = (c.lat as number) - slat;
          const dlon = (c.lon as number) - slon;
          return { code: c.code, d: dlat * dlat + dlon * dlon };
        })
        .filter((x) => Math.sqrt(x.d) <= radius)
        .sort((a, b) => a.d - b.d)
        .slice(0, 8)
        .map((x) => x.code)
    );
  }, [
    selectedCity?.code,
    selectedCity?.lat,
    selectedCity?.lon,
    withCoords,
    tier,
  ]);

  // 距离 km
  const nearbyDistances = React.useMemo(() => {
    if (
      !selectedCity ||
      selectedCity.lat == null ||
      selectedCity.lon == null
    ) {
      return new Map<string, number>();
    }
    const m = new Map<string, number>();
    nearbyCodes.forEach((code) => {
      const c = withCoords.find((x) => x.code === code);
      if (!c || c.lat == null || c.lon == null) return;
      const dlat = (c.lat - selectedCity.lat!) * 111;
      const dlon =
        (c.lon - selectedCity.lon!) *
        111 *
        Math.cos((selectedCity.lat! * Math.PI) / 180);
      m.set(code, Math.round(Math.sqrt(dlat * dlat + dlon * dlon)));
    });
    return m;
  }, [selectedCity, nearbyCodes, withCoords]);

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
    1: "国家级 · 15 大枢纽 + 真实 OSM tile",
    2: "区域级 · 中心 ±20° 范围",
    3: "城市级 · 全部 218 站点",
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
      data-testid="world-map-root"
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
              个城市 ·{" "}
              <span className="font-medium text-primary">{hubSet.size}</span>{" "}
              枢纽
              {airlineHubsByCity.size > 0 && (
                <>
                  {" · "}
                  <span
                    className="font-bold"
                    style={{ color: "#7c3aed" }}
                    data-testid="airline-hub-count"
                  >
                    {airlineHubsByCity.size}
                  </span>{" "}
                  <span style={{ color: "#7c3aed" }}>航司 hub</span>
                </>
              )}
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

      {/* Map area — 高度固定 480px (V14 用 aspect-[2/1], V16 改固定高度让 leaflet 正确布局) */}
      <div
        className="relative"
        style={{ height: "480px", width: "100%" }}
      >
        {!mounted ? (
          <div className="flex h-full w-full items-center justify-center bg-ink-50 text-ink-500">
            地图加载中…
          </div>
        ) : (
          <MapContainer
            center={[35, 105]}
            zoom={ZOOM_DEFAULT}
            minZoom={ZOOM_MIN}
            maxZoom={ZOOM_MAX}
            scrollWheelZoom={true}
            style={{ height: "100%", width: "100%" }}
            zoomControl={false}
            worldCopyJump={true}
          >
            <TileLayer
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            />
            <ZoomControl position="bottomright" />
            <MapController
              onZoomEnd={setZoom}
              onCenterEnd={(c) => setCenter(c)}
              onMapReady={(m) => {
                mapRef.current = m;
              }}
              selectedCity={selectedCity ?? null}
              lastSelectedCodeRef={lastSelectedCodeRef}
              hovered={hovered}
              setHovered={setHovered}
              setMouseAnchor={setMouseAnchor}
            />

            {/* T1 cluster 模式 (zoom ≤ 4): supercluster 聚合 hubs */}
            {clusterFeatures?.map((feat) => {
              const [lon, lat] = feat.geometry.coordinates;
              const props: any = feat.properties;
              if (props.cluster) {
                return (
                  <ClusterMarker
                    key={`cluster-${props.cluster_id}`}
                    count={props.point_count as number}
                    clusterId={props.cluster_id as number}
                    lat={lat}
                    lon={lon}
                    cluster={cluster!}
                    zoom={zoom}
                    mapRef={mapRef}
                  />
                );
              } else {
                // single hub (cluster 不形成, 偏远地区单 hub)
                const city = hubs.find((h) => h.code === props.code);
                if (!city) return null;
                const isHub = true;
                const inLabelSet = labelSet.has(props.code);
                const showLabel =
                  inLabelSet ||
                  zoom >= 5 ||
                  selectedCity?.code === props.code ||
                  hovered === props.code ||
                  (hoveredLetter != null &&
                    firstLetter(props.code) === hoveredLetter);
                return (
                  <CityDot
                    key={`hub-${props.code}`}
                    city={city}
                    isHub={isHub}
                    isLabel={inLabelSet}
                    isSelected={selectedCity?.code === props.code}
                    isHovered={hovered === props.code}
                    isLetterPulse={
                      hoveredLetter != null &&
                      firstLetter(props.code) === hoveredLetter &&
                      selectedCity?.code !== props.code
                    }
                    isNearby={nearbyCodes.has(props.code)}
                    showLabel={showLabel}
                    onSelect={onSelectCity}
                    setHovered={setHovered}
                  />
                );
              }
            })}

            {/* 非 cluster 模式: 普通 CircleMarker */}
            {visibleCities
              .filter((c) => {
                if (clusterFeatures && hubSet.has(c.code)) return false;
                return true;
              })
              .map((c) => {
                const isHub = hubSet.has(c.code);
                const r = isHub ? 5 : 3;
                if (r <= 0) return null; // T1 已过滤
                const isHover = hovered === c.code;
                const isSelected = selectedCity?.code === c.code;
                const isNearby = nearbyCodes.has(c.code);
                const isLetterPulse =
                  hoveredLetter != null &&
                  firstLetter(c.code) === hoveredLetter &&
                  !isSelected;
                const inLabelSet = labelSet.has(c.code);
                const showLabel =
                  inLabelSet ||
                  (isHub && zoom >= 5) ||
                  isSelected ||
                  isHover ||
                  isLetterPulse;
                return (
                  <CityDot
                    key={c.code}
                    city={c}
                    isHub={isHub}
                    isLabel={inLabelSet}
                    isSelected={isSelected}
                    isHovered={isHover}
                    isLetterPulse={isLetterPulse}
                    isNearby={isNearby}
                    showLabel={showLabel}
                    onSelect={onSelectCity}
                    setHovered={setHovered}
                  />
                );
              })}

            {/* V17→V22: 航司 hub 数字徽章 layer
                V17: 紫环 + permanent tooltip (堆叠)
                V22 (NJX 拍 B): 紫环保留 + 中心数字徽章 (click → flyTo + 右侧 panel) */}
            {airlineHubsByCity.size > 0 &&
              Array.from(airlineHubsByCity.entries()).map(
                ([cityCode, airlinesHere]) => {
                  const city = withCoords.find((c) => c.code === cityCode);
                  if (!city) return null;
                  return (
                    <AirlineHubBadge
                      key={`airline-hub-${cityCode}`}
                      city={city}
                      airlines={airlinesHere}
                      active={airlinePanel?.cityCode === cityCode}
                      onHubClick={handleHubClick}
                    />
                  );
                }
              )}

            {/* V20: 全球机场灰点 layer
                - zoom < 4: 用 globalCluster 聚合 (避免 6072 DOM node 同时渲染)
                - zoom >= 4: 散开所有非 AOG 机场 (视口内 ~600-1000 节点)
                - 颜色: #9ca3af (ink-400) — 区别于 AOG 红/蓝 hub
                - 半径: 1.5 (更小, 不抢 AOG 城市视觉)
                - interactive: false (灰点不响应 click/hover)
                - 渲染顺序: 在 city + airline hub 之后 (但灰点 radius 1.5, 不会盖住 AOG) */}
            {zoom < 4 && globalClusterFeatures
              ? globalClusterFeatures.map((feat) => {
                  const [lon, lat] = feat.geometry.coordinates;
                  const props: any = feat.properties;
                  if (props.cluster) {
                    // 聚合气泡: 浅灰半透明, 数字显示机场数
                    return (
                      <Marker
                        key={`gcluster-${props.cluster_id}`}
                        position={[lat, lon]}
                        icon={L.divIcon({
                          className: "global-cluster-wrapper",
                          html: `<div class="global-cluster-bubble">${
                            props.point_count >= 1000
                              ? `${(props.point_count / 1000).toFixed(1)}k`
                              : props.point_count
                          }</div>`,
                          iconSize: [22, 22],
                          iconAnchor: [11, 11],
                        })}
                        interactive={false}
                      />
                    );
                  } else {
                    // 单机场 (cluster 未能聚合到的偏远单点) — 灰点
                    return (
                      <CircleMarker
                        key={`gairport-${props.iata}`}
                        center={[lat, lon]}
                        radius={1.5}
                        pathOptions={{
                          color: "transparent",
                          fillColor: "#9ca3af",
                          fillOpacity: 0.55,
                        }}
                        interactive={false}
                      />
                    );
                  }
                })
              : null}
            {zoom >= 4 &&
              nonAogAirports.map((a) => (
                <CircleMarker
                  key={`gairport-${a.iata}`}
                  center={[a.lat, a.lon]}
                  radius={1.5}
                  pathOptions={{
                    color: "transparent",
                    fillColor: "#9ca3af",
                    fillOpacity: 0.55,
                  }}
                  interactive={false}
                />
              ))}
          </MapContainer>
        )}

        {/* 右侧控制条 (跟 V14 视觉一致) */}
        <div className="absolute right-3 top-1/2 z-[400] flex -translate-y-1/2 flex-col items-center gap-1.5">
          <button
            type="button"
            onClick={() => {
              const next = Math.min(ZOOM_MAX, zoom + 1);
              mapRef.current?.flyTo(center, next, { duration: 0.3 });
            }}
            className="grid h-7 w-7 place-items-center rounded-md border border-ink-100 bg-white text-ink-500 shadow-soft transition hover:bg-ink-50 hover:text-ink-900"
            aria-label="放大"
            title={`放大 (${zoom.toFixed(1)}x)`}
          >
            <ZoomIn className="h-3.5 w-3.5" />
          </button>

          <button
            type="button"
            onClick={() => {
              const next = Math.max(ZOOM_MIN, zoom - 1);
              mapRef.current?.flyTo(center, next, { duration: 0.3 });
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
              mapRef.current?.flyTo([35, 105], ZOOM_DEFAULT, { duration: 0.4 });
              onSelectCity?.(null);
            }}
            className="grid h-7 w-7 place-items-center rounded-md border border-ink-100 bg-white text-ink-500 shadow-soft transition hover:bg-ink-50 hover:text-ink-900"
            aria-label="重置"
            title="重置视图"
          >
            <RotateCcw className="h-3 w-3" />
          </button>
        </div>

        {/* 选中城市 chip — bottom-left (V5 行为保留) */}
        {selectedCity && (
          <div
            className="absolute bottom-3 left-3 z-[400] inline-flex max-w-[60%] flex-col gap-1 rounded-lg border border-red-200 bg-white/95 px-3 py-2 text-xs shadow-soft backdrop-blur"
            data-testid="selected-chip"
          >
            <Link
              href={`/city/${encodeURIComponent(selectedCity.code)}`}
              className="inline-flex items-center gap-2 transition hover:opacity-80"
            >
              <span className="inline-block h-2.5 w-2.5 rounded-full bg-red-500 shadow-[0_0_0_3px_rgba(220,38,38,0.2)]" />
              <span className="font-semibold text-ink-900">
                {selectedCity.name}
              </span>
              {selectedCity.iata && selectedCity.iata !== "—" && (
                <span className="rounded bg-red-50 px-1.5 py-0.5 text-[10px] font-bold tabular-nums text-red-700">
                  {selectedCity.iata}
                </span>
              )}
              {(selectedCity.view_count ?? 0) > 0 && (
                <span className="rounded bg-ink-50 px-1.5 py-0.5 text-[10px] font-medium tabular-nums text-ink-500">
                  {(selectedCity.view_count ?? 0).toLocaleString()} 浏览
                </span>
              )}
              <span className="ml-1 text-primary">→</span>
            </Link>
            <div className="flex items-center gap-2 text-[10px] text-ink-500">
              <span>
                周边 {nearbyCodes.size} 站 · 半径 {TIER_NEARBY_RADIUS_DEG[tier]}°
              </span>
              {nearbyCodes.size > 0 && (
                <span className="text-ink-400">
                  · 最近{" "}
                  {(() => {
                    const arr = Array.from(nearbyDistances.values()).sort(
                      (a, b) => a - b
                    );
                    return arr.length > 0 ? `${arr[0]} km` : "—";
                  })()}
                </span>
              )}
            </div>
          </div>
        )}

        {/* hover 浮动 tooltip (V5 行为保留) */}
        {hovered &&
          hovered !== selectedCity?.code &&
          mouseAnchor &&
          (() => {
            const city = withCoords.find((c) => c.code === hovered);
            if (!city) return null;
            const isHub = hubSet.has(hovered);
            const distance = nearbyDistances.get(hovered);
            return (
              <div
                className={cn(
                  "pointer-events-none absolute z-[401] -translate-x-1/2",
                  "rounded-md border bg-white/95 px-2.5 py-1.5 text-[11px] shadow-soft backdrop-blur",
                  isHub ? "border-primary/40" : "border-ink-200"
                )}
                style={{
                  left: mouseAnchor.x,
                  top: Math.max(8, mouseAnchor.y - 28),
                }}
                data-testid="hover-tooltip"
              >
                <div className="flex items-center gap-1.5">
                  {isHub && (
                    <span className="rounded bg-primary/10 px-1 text-[9px] font-bold text-primary">
                      HUB
                    </span>
                  )}
                  <span className="font-semibold text-ink-900">
                    {city.name}
                  </span>
                  {city.iata && city.iata !== "—" && (
                    <span className="rounded bg-ink-50 px-1 text-[9px] font-bold tabular-nums text-ink-700">
                      {city.iata}
                    </span>
                  )}
                  {(city.view_count ?? 0) > 0 && (
                    <span className="text-[9px] text-ink-500 tabular-nums">
                      {(city.view_count ?? 0).toLocaleString()}
                    </span>
                  )}
                </div>
                {distance != null && (
                  <div className="mt-0.5 text-[9px] text-ink-500">
                    距 {distance} km
                  </div>
                )}
              </div>
            );
          })()}

        {/* Footer caption */}
        <div className="pointer-events-none absolute left-3 top-3 z-[400] hidden flex-col gap-0.5 text-[10px] sm:flex">
          <span className="rounded bg-black/60 px-1.5 py-0.5 text-white">
            滚轮缩放 · 拖动平移
          </span>
          <span className="rounded bg-black/60 px-1.5 py-0.5 text-white">
            点城市查看周边 · 红圈 = 选中
          </span>
        </div>

        {/* V21: 区域数字面板 (bottom-left, 选中 chip 上方)
            NJX 拍 C: top 6 国家 (单列 6 行) + AOG 数字标红 区分
            - 12 → 6 行, 紧凑 (w-48 = 192px)
            - 单列而非 2 列, 名字不被截
            - 每行: 国名 | AOG (红) / 总数 (灰) */}
        {globalAirports.length > 0 && (
          <div
            className={cn(
              "absolute z-[400] w-48 rounded-lg border border-ink-200 bg-white/95 px-3 py-2 text-[11px] shadow-soft backdrop-blur",
              selectedCity ? "bottom-[68px] left-3" : "bottom-3 left-3"
            )}
            data-testid="global-airports-panel"
          >
            <div className="mb-1.5 flex items-baseline justify-between gap-2">
              <span className="font-semibold text-ink-900">全球机场</span>
              <span className="tabular-nums text-ink-500">
                <span className="font-bold text-ink-700">
                  {globalAirports.length.toLocaleString()}
                </span>{" "}
                站
              </span>
            </div>
            <div className="flex flex-col">
              {topCountries.map(([country, count], i) => {
                const aogInCountry = aogCodesByCountry.get(country) || 0;
                return (
                  <div
                    key={country}
                    className="flex items-center justify-between gap-2 py-0.5 text-ink-600"
                  >
                    <span className="truncate">
                      {i + 1}. {country}
                    </span>
                    <span className="shrink-0 tabular-nums text-ink-500">
                      {aogInCountry > 0 && (
                        <span style={{ color: "#dc2626", fontWeight: 700 }}>
                          {aogInCountry}
                        </span>
                      )}
                      {aogInCountry > 0 && <span className="mx-0.5">/</span>}
                      <span className="font-medium text-ink-700">
                        {count.toLocaleString()}
                      </span>
                    </span>
                  </div>
                );
              })}
            </div>
            <div className="mt-1.5 flex items-center justify-between gap-2 border-t border-ink-100 pt-1.5 text-[10px] text-ink-400">
              <span className="inline-flex items-center gap-1">
                <span className="inline-block h-1.5 w-1.5 rounded-full bg-[#9ca3af]" />
                灰 = 暂无预案
              </span>
              <span className="inline-flex items-center gap-1">
                <span style={{ color: "#dc2626", fontWeight: 700 }}>红</span>
                = AOG
              </span>
            </div>
          </div>
        )}

        {/* V22: 航司 hub 详情 panel (NJX 拍 B)
            浮在地图右上, 列选中城市的所有航司
            数字徽章 click → flyTo + setState 触发 */}
        {airlinePanel &&
          (() => {
            const panelCity = withCoords.find(
              (c) => c.code === airlinePanel.cityCode
            );
            if (!panelCity) return null;
            return (
              <AirlineHubPanel
                city={panelCity}
                airlines={airlinePanel.airlines}
                onClose={closeHubPanel}
              />
            );
          })()}
      </div>
    </div>
  );
}
