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
// V5 新增: react-simple-maps 的 Annotation,自动处理 SVG/zoom 缩放,用于国家标签
import { Annotation as _Annotation } from "react-simple-maps";
// 世界国家边界 (TopoJSON, 108KB). 引用本地包避免 CDN 依赖.
// world-atlas 没自带 TS 类型 — 强类型断言.
import worldGeoData from "world-atlas/countries-110m.json";
import type { City } from "@/lib/types";
import { citiesWithCoords } from "@/lib/city-stats";
import { cn, firstLetter } from "@/lib/utils";
import { ZoomIn, ZoomOut, RotateCcw, MapPin } from "lucide-react";
// V5 新增: d3-geo + topojson-client (transitive dep) 算 38 国 centroid,模块加载一次性算好
// d3-geo v3 没有 default export, 用 namespace import
// topojson-client 没自带 @types, 本地声明
import * as d3 from "d3-geo";
// topojson-client 自带 @types (V5 装), 无需 @ts-expect-error
import * as topojsonClient from "topojson-client";
// V6 新增: supercluster — hub 聚合 (zoom ≤ 4)
// radius=80px (中等聚合力度), maxZoom=4 (T1+T2 聚合, T3+ 不聚合)
import Supercluster from "supercluster";

const ComposableMap: any = _ComposableMap;
const Geographies: any = _Geographies;
const Geography: any = _Geography;
const Marker: any = _Marker;
const ZoomableGroup: any = _ZoomableGroup;
const Annotation: any = _Annotation;

const WORLD_GEO: any = worldGeoData;

/* ============================================================
 *  V7 导航地图 — 终极收口 (在 V6 基础上, NJX 截图硬诊断后重做 label 位置)
 *  ============================================================
 *  V5 已知问题 (NJX 截图):
 *  1. 15 hub dot 8px 太密 — 上海/南京/杭州/苏州/无锡 8px+8px 互相覆盖
 *  2. pulse ring 12-22px 太大 — 北京 PKX 选中态覆盖"北京"文字
 *  3. 38 国标签 + 15 hub dot 同时显示 — 信息密度太高
 *
 *  V6 已知问题 (NJX 截图 hard 诊断):
 *  1. 4px hub dot 实际渲染 24-30px — feDropShadow stdDeviation=2 + 1.5px stroke + 1.5px 蓝背景
 *     → 即使在 zoom 6, dot 视觉占满 24px 屏幕像素, 完全遮 label
 *  2. Label 位置错 — IATA 在 dot 上方 (y=-r-5) + CN 名在下方 (y=r+4)
 *     → close pack 区域 (上海/南京/杭州 200km 内) label 互相 + 与 dot 中心交叠
 *  3. 同区域 hub 200km 互遮 — V6 改偏移但实际渲染位置还在 dot 中心附近
 *
 *  V8 改造 (NJX 拍 8x 看清):
 *  1. 字号 + dot 全部 N/zoom 公式 (constant 实际像素):
 *     - hub IATA 14px constant
 *     - hub CN 16px constant
 *     - 国家名 16px constant
 *     - 普通 IATA 8px / CN 10px constant
 *     - hub dot 4px constant (V7 1.5px 太小, V8 增大)
 *     - TIER_REGULAR_DOT 3px constant (V7 0.5 几乎隐形)
 *     - HUB_HALO 6px, STROKE 0.5px constant
 *     - SELECTED_PULSE 8/4px, RING 1.5px constant
 *  2. V7 保留:
 *     - textAnchor="start" 永远在 dot 右侧
 *     - 白底 rect 防 dot 遮文字
 *
 *  2. Label **永远在 dot 右侧** (V6 错改, V7 硬性约束):
 *     - textAnchor="start" (不再 middle)
 *     - x = cx + r + 3 (永远 dot 中心右侧 3px+)
 *     - IATA 在 y = cy - 2 (中心偏上 2px)
 *     - CN 名在 y = cy + 9 (中心偏下 9px, 在 IATA 下方)
 *     - 加白底 rect 防 dot 遮文字 (fillOpacity 0.85, rx 2)
 *     - rect 宽 = 估算 textWidth (IATA ~18px, CN ~30px)
 *
 *  3. IATA + CN 名 **永远显示** (V6 T1 隐藏非 hub, V7 任何 zoom 都显示 hub IATA):
 *     - hub 永远显示 IATA + CN 名
 *     - cluster dot 数字 仍居中显示 (大点内部, 视觉集中)
 *     - single-hub cluster (偏远) 与独立 hub 一致
 *
 *  V6 保留:
 *  - 38 国标签 + tier 1/2/3 + cluster 聚合 + 字母 sidebar 联动
 *  - Link 跳转 + chip 浮动 + 距离 km + minimap + 选中红圈
 * ============================================================ */

const ZOOM_MIN = 1;
const ZOOM_MAX = 8;
const ZOOM_DEFAULT = 1;
const ZOOM_SELECT = 6;

const HUB_TOP_N = 15; // 国家级 hub 数量
const HUB_LABEL_TOP_N = 6; // V9: 区域级 (T2) 只显示 top 6 hub label, 避免重叠 (NJX 拍)

function getTier(zoom: number): 1 | 2 | 3 {
  if (zoom < 3) return 1;
  if (zoom < 5) return 2;
  return 3;
}

// V8: dot 尺寸定义在 component 内部 (line 273+, 因为依赖 zoom state)
//   公式 N/zoom → 实际像素 = N (constant, 抵消 react-simple-maps transform scale(zoom))

// V8: label 字号 — 保持 V7 公式 N/zoom (产生 constant 像素 N, 抵消 react-simple-maps transform scale(zoom))
//   react-simple-maps ZoomableGroup 实际: <g transform="translate(x,y) scale(k)"> 包裹 children
//   Marker 内部: <g transform="translate(mx,my)"> → 实际 transform = scale(k) + translate
//   所以 fontSize = N/zoom 时, 实际像素 = (N/zoom) * zoom = N (constant across all zoom)
//   V7 的 bug 是 N 太小 (7/8.5) → 实际像素 7-8.5px (看不清, NJX 拍)
//   V8 N 调到 V3 量级 14-16 → 实际像素 14-16px (能看清)

const TIER_NEARBY_RADIUS_DEG: Record<1 | 2 | 3, number> = {
  1: 2.5,
  2: 2.5,
  3: 0.5,
};

const TIER2_LATLON_RANGE = 20;

/* ============================================================
 *  V5 改造 2: 国家标签 — 38 国 centroid (模块加载一次性算好)
 * ============================================================ */

// 模块级常量 — 38 个国家 (亚洲 16 + 欧洲 10 + 美洲 6 + 大洋洲 1 + 非洲 5)
const COUNTRY_LABELS: Array<{
  en: string;
  zh: string;
  region: "asia" | "europe" | "america" | "oceania" | "africa";
  lon: number;
  lat: number;
}> = (() => {
  // 仅在浏览器侧用 topojson-client + d3-geo 算 centroid
  // 提前算好, runtime cost = 0
  const WIK = (() => {
    try {
      const fc = topojsonClient.feature(
        WORLD_GEO,
        WORLD_GEO.objects.countries
      );
      return fc as any;
    } catch {
      return null;
    }
  })();
  const defs: Array<{
    en: string;
    zh: string;
    region: "asia" | "europe" | "america" | "oceania" | "africa";
  }> = [
    // 亚洲 (16) — 重点,中国航空业相关
    { en: "China", zh: "中国", region: "asia" },
    { en: "Russia", zh: "俄罗斯", region: "asia" },
    { en: "Mongolia", zh: "蒙古", region: "asia" },
    { en: "Kazakhstan", zh: "哈萨克斯坦", region: "asia" },
    { en: "India", zh: "印度", region: "asia" },
    { en: "Japan", zh: "日本", region: "asia" },
    { en: "South Korea", zh: "韩国", region: "asia" },
    { en: "North Korea", zh: "朝鲜", region: "asia" },
    { en: "Vietnam", zh: "越南", region: "asia" },
    { en: "Laos", zh: "老挝", region: "asia" },
    { en: "Myanmar", zh: "缅甸", region: "asia" },
    { en: "Philippines", zh: "菲律宾", region: "asia" },
    { en: "Malaysia", zh: "马来西亚", region: "asia" },
    { en: "Indonesia", zh: "印度尼西亚", region: "asia" },
    { en: "Thailand", zh: "泰国", region: "asia" },
    { en: "Cambodia", zh: "柬埔寨", region: "asia" },
    // 欧洲 (10) — 国际枢纽
    { en: "Germany", zh: "德国", region: "europe" },
    { en: "France", zh: "法国", region: "europe" },
    { en: "United Kingdom", zh: "英国", region: "europe" },
    { en: "Italy", zh: "意大利", region: "europe" },
    { en: "Spain", zh: "西班牙", region: "europe" },
    { en: "Netherlands", zh: "荷兰", region: "europe" },
    { en: "Belgium", zh: "比利时", region: "europe" },
    { en: "Switzerland", zh: "瑞士", region: "europe" },
    { en: "Austria", zh: "奥地利", region: "europe" },
    { en: "Turkey", zh: "土耳其", region: "europe" },
    // 美洲 (6)
    { en: "United States of America", zh: "美国", region: "america" },
    { en: "Canada", zh: "加拿大", region: "america" },
    { en: "Mexico", zh: "墨西哥", region: "america" },
    { en: "Brazil", zh: "巴西", region: "america" },
    { en: "Argentina", zh: "阿根廷", region: "america" },
    { en: "Chile", zh: "智利", region: "america" },
    // 大洋洲 (1)
    { en: "Australia", zh: "澳大利亚", region: "oceania" },
    // 非洲 (5)
    { en: "Egypt", zh: "埃及", region: "africa" },
    { en: "South Africa", zh: "南非", region: "africa" },
    { en: "Nigeria", zh: "尼日利亚", region: "africa" },
    { en: "Kenya", zh: "肯尼亚", region: "africa" },
    { en: "Morocco", zh: "摩洛哥", region: "africa" },
  ];
  return defs.map((d) => {
    if (!WIK) return { ...d, lon: 0, lat: 0 };
    const f = WIK.features.find(
      (g: any) => g.properties && g.properties.name === d.en
    );
    if (!f) return { ...d, lon: 0, lat: 0 };
    const c = d3.geoCentroid(f);
    return { ...d, lon: c[0], lat: c[1] };
  });
})();

/* ============================================================
 *  V5 改造 1: Hub 集合计算
 *  - 取 view_count > 0 的城市排序,前 HUB_TOP_N
 *  - 极少见: 若 HUB_TOP_N 个都是中国/亚洲,T2/T3 也能 cover 大部分区域
 *  - 用 Set cache 提升 O(1) lookup
 * ============================================================ */
function computeHubs(cities: City[]): { hubSet: Set<string>; labelSet: Set<string> } {
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
  className?: string;
  /** 父级 hover 的字母 — 地图上该字母城市 pulse */
  hoveredLetter?: string | null;
  /** 父级选中的城市 — 自动 pan/zoom + 高亮 + 显示附近 */
  selectedCity?: City | null;
  /** 通知父级城市被选中 */
  onSelectCity?: (city: City | null) => void;
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
  const [hoverAnchor, setHoverAnchor] = React.useState<{
    x: number;
    y: number;
  } | null>(null);
  const [zoom, setZoom] = React.useState<number>(ZOOM_DEFAULT);
  const [center, setCenter] = React.useState<[number, number]>([0, 20]);
  const lastSelectedCode = React.useRef<string | null>(null);

  const animFrameRef = React.useRef<number | null>(null);
  const zoomRef = React.useRef(zoom);

  // V8: dot/halo/stroke 尺寸 (N/zoom 公式 → constant 实际像素)
  const HUB_DOT_V8 = 4 / zoom;
  const HUB_STROKE_W_V8 = 0.5 / zoom;
  const HUB_HALO_R_V8 = 6 / zoom;
  const HUB_LABEL_GAP_V8 = 5 / zoom;
  const TIER_REGULAR_DOT_V8: Record<1 | 2 | 3, number> = {
    1: 0,
    2: 3 / zoom,
    3: 3 / zoom,
  };
  const SELECTED_PULSE_OUTER_V8 = 8 / zoom;
  const SELECTED_PULSE_INNER_V8 = 4 / zoom;
  const SELECTED_RING_W_V8 = 1.5 / zoom;
  const HOVERED_PULSE_OUTER_V8 = 4 / zoom;
  const HOVERED_PULSE_INNER_V8 = 1 / zoom;
  const centerRef = React.useRef(center);
  React.useEffect(() => {
    zoomRef.current = zoom;
  }, [zoom]);
  React.useEffect(() => {
    centerRef.current = center;
  }, [center]);

  const tier: 1 | 2 | 3 = getTier(zoom);

  // V5: hub set
  const { hubSet, labelSet } = React.useMemo(() => computeHubs(withCoords), [withCoords]);
  const hubs = React.useMemo(
    () => withCoords.filter((c) => hubSet.has(c.code)),
    [withCoords, hubSet]
  );

  // V6: supercluster 索引 — 基于 hubs (15 个) 聚合
  // radius=80px (中等力度), maxZoom=4 (T1+T2 聚合, T3+ 不聚合)
  // 输入: hubs 数组, 转换为 GeoJSON Point features
  const cluster = React.useMemo(() => {
    if (hubs.length === 0) return null;
    const idx = new Supercluster<{ code: string; name: string; iata: string }, any>({
      radius: 80,
      maxZoom: 4,
      minPoints: 2, // 至少 2 个点才聚合
    });
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

  // V6: 当前 zoom 的 cluster 输出
  // 条件: zoom ≤ 4 (T1 + T2), 否则回退到 hubs 直接显示
  // bbox 用世界范围 [-180, -85, 180, 85] (确保所有 hub 都参与)
  const clusterFeatures = React.useMemo(() => {
    if (!cluster || zoom > 4) return null;
    return cluster.getClusters([-180, -85, 180, 85], Math.floor(zoom));
  }, [cluster, zoom]);

  // 当前可见城市集 by tier
  const visibleCities = React.useMemo(() => {
    let base: City[];
    if (tier === 1) {
      // 国家级: 只显示 hub
      base = hubs;
    } else if (tier === 2) {
      // 区域级: hub 始终 + 中心 ±20° 范围内 view_count > 0 城市
      // (V5 spec: "view_count > 100" — 但实际数据 0/24,放宽到 > 0 才有非 hub 显示)
      const [lon, lat] = center;
      const inRange = withCoords.filter((c) => {
        if (c.lat == null || c.lon == null) return false;
        return (
          Math.abs(c.lat - lat) <= TIER2_LATLON_RANGE &&
          Math.abs(c.lon - lon) <= TIER2_LATLON_RANGE
        );
      });
      const hubCodes = new Set(hubs.map((c) => c.code));
      // hub 始终 + 范围内 view_count > 0 的非 hub
      const nonHubInRange = inRange.filter(
        (c) => !hubCodes.has(c.code) && (c.view_count || 0) > 0
      );
      base = Array.from(
        new Map(
          [...hubs, ...nonHubInRange].map((c) => [c.code, c])
        ).values()
      );
      // hub 排前面, 其他按 view_count 降序
      base.sort((a, b) => {
        const aHub = hubCodes.has(a.code) ? 1 : 0;
        const bHub = hubCodes.has(b.code) ? 1 : 0;
        if (aHub !== bHub) return bHub - aHub;
        return (b.view_count || 0) - (a.view_count || 0);
      });
    } else {
      // 城市级: 全部
      base = withCoords;
    }
    // 选中城市始终包含
    if (selectedCity && !base.find((c) => c.code === selectedCity.code)) {
      return [selectedCity, ...base];
    }
    return base;
  }, [withCoords, tier, center, selectedCity, hubs]);

  // V5: 区域级 (T2) 可见的国家 — 中心 ±25° 范围内
  const visibleCountryLabels = React.useMemo(() => {
    if (tier === 3) return []; // 城市级隐藏
    if (tier === 1) return COUNTRY_LABELS; // 国家级全显示
    // T2: 中心 ±25° 范围
    const [lon, lat] = center;
    const RANGE = 25;
    return COUNTRY_LABELS.filter(
      (c) =>
        Math.abs(c.lat - lat) <= RANGE && Math.abs(c.lon - lon) <= RANGE
    );
  }, [tier, center]);

  // rAF-based 平滑动画 (V3 保留)
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

  // 暴露给 Playwright / dev
  React.useEffect(() => {
    if (typeof window === "undefined") return;
    (window as any).__aogMapView = {
      setView: (z: number, lon: number, lat: number, duration?: number) => {
        animateTo(z, [lon, lat], duration ?? 300);
      },
      getView: () => ({ zoom, center }),
      getTier: () => tier,
      getHubSet: () => Array.from(hubSet),
    };
    return () => {
      delete (window as any).__aogMapView;
    };
  }, [animateTo, zoom, center, tier, hubSet]);

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

  // 选中城市的附近城市 (V3 保留)
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

  // V5: 附近城市距离 (km, 1° ≈ 111km) — 给 chip 用
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
      opacity: 0.4,
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
    1: "国家级 · 15 大枢纽 + 38 国标签",
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
            <defs>
              {/* V7: hub 蓝发光 drop-shadow filter (V6 2 → V7 0.5, 阴影极轻) */}
              <filter
                id="hub-glow"
                x="-50%"
                y="-50%"
                width="200%"
                height="200%"
              >
                <feDropShadow
                  dx="0"
                  dy="0.5"
                  stdDeviation="0.5"
                  floodColor="#2563eb"
                  floodOpacity="0.3"
                />
              </filter>
              {/* 选中红光 (V7 同步缩) */}
              <filter
                id="selected-glow"
                x="-50%"
                y="-50%"
                width="200%"
                height="200%"
              >
                <feDropShadow
                  dx="0"
                  dy="1"
                  stdDeviation="1"
                  floodColor="#dc2626"
                  floodOpacity="0.45"
                />
              </filter>
            </defs>
            <ZoomableGroup
              zoom={zoom}
              center={center}
              onMoveEnd={(pos: any) => {
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
              {/* 国家边界 */}
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

              {/* V5 改造 2: 国家标签 (38 国 centroid, 11px 600 weight) */}
              {visibleCountryLabels.map((c) => {
                if (c.lon === 0 && c.lat === 0) return null;
                // V8: N=16 → 实际 16px constant (国家名)
                const fontSize = 16 / zoom;
                return (
                  <Annotation
                    key={c.en}
                    subject={[c.lon, c.lat]}
                    dx={0}
                    dy={0}
                    connectorProps={{ stroke: "none" }}
                  >
                    <text
                      x={0}
                      y={0}
                      textAnchor="middle"
                      dominantBaseline="central"
                      style={{
                        fontFamily:
                          "-apple-system, BlinkMacSystemFont, 'PingFang SC', 'Microsoft YaHei', sans-serif",
                        fontSize,
                        fontWeight: 600,
                        fill: "#6b7280",
                        fillOpacity: 0.7,
                        paintOrder: "stroke",
                        stroke: "#ffffff",
                        strokeWidth: 4 / zoom,
                        strokeLinejoin: "round",
                        pointerEvents: "none",
                      }}
                    >
                      {c.zh}
                    </text>
                  </Annotation>
                );
              })}

              {/* V6: 城市 dots (cluster 模式下不渲染 hubs, 由 cluster 接管) */}
              {visibleCities
                .filter((c) => {
                  // V6: zoom ≤ 4 且该城市是 hub → 已被 cluster 接管, 跳过
                  if (clusterFeatures && hubSet.has(c.code)) return false;
                  return true;
                })
                .map((c) => {
                const isHub = hubSet.has(c.code);
                // V6: hub 永远 4px (V5 8px → V6 4px), 普通按 tier
                const r = isHub
                  ? HUB_DOT_V8
                  : TIER_REGULAR_DOT_V8[tier] > 0
                  ? TIER_REGULAR_DOT_V8[tier]
                  : 0;
                if (r <= 0) return null; // T1 隐藏非 hub
                const v = c.view_count || 0;
                const isHover = hovered === c.code;
                const isSelected = selectedCity?.code === c.code;
                const isNearby = nearbyCodes.has(c.code);
                const letter = firstLetter(c.code);
                const isLetterPulse =
                  hoveredLetter != null &&
                  letter === hoveredLetter &&
                  !isSelected;

                // V5 保留: 颜色按 hub / 普通分
                const fill = isSelected
                  ? "#dc2626"
                  : isHub
                  ? "#2563eb"
                  : isHover
                  ? "#1e40af"
                  : "#9ca3af";

                const fillOpacity = isSelected
                  ? 1
                  : isHover
                  ? 1
                  : isNearby
                  ? 0.7
                  : isHub
                  ? 0.95
                  : 0.65;

                // V11: CN label density (NJX 拍"中文名, 不要 IATA, 不要太密")
                //   - top 6 hub (labelSet): 任何 zoom 都显示 CN (突出)
                //   - 其他 hub: zoom >= 5 显示
                //   - selected/hovered/letterPulse/nearby 永远显示
                //   - 普通城市: 不显示 label (NJX 拍"区域级不要 label 全部显示", 218 城市重叠)
                //   - 普通城市保持 dot (3px) 让用户知道"这个区域有航站", 但不互相覆盖
                const inLabelSet = labelSet.has(c.code);
                const showCnName =
                  inLabelSet ||
                  (isHub && zoom >= 5) ||
                  isSelected ||
                  isHover ||
                  isLetterPulse ||
                  (nearbyCodes.has(c.code) && c.name);

                // V11: CN 字号 (constant 像素)
                //   - hub: 16px
                //   - 普通城市 (nearby/selected): 12px
                const cnNameFontSize = isHub
                  ? 16 / zoom
                  : 12 / zoom;

                return (
                  <Marker
                    key={c.code}
                    coordinates={[c.lon!, c.lat!]}
                    onMouseEnter={(e: any) => {
                      setHovered(c.code);
                      // V5: 记录鼠标屏幕位置, tooltip 浮动跟随
                      if (e && e.clientX != null) {
                        const mapEl = (
                          document.querySelector(
                            "[data-testid='world-map-root']"
                          ) as HTMLElement
                        )?.getBoundingClientRect();
                        if (mapEl) {
                          setHoverAnchor({
                            x: e.clientX - mapEl.left,
                            y: e.clientY - mapEl.top,
                          });
                        } else {
                          setHoverAnchor({ x: e.clientX, y: e.clientY });
                        }
                      }
                    }}
                    onMouseLeave={() => setHovered(null)}
                  >
                    <a
                      href={`/city/${encodeURIComponent(c.code).toLowerCase()}`}
                      onClick={(e: any) => {
                        // V5: 用 onSelectCity 控制选中态, preventDefault 阻止 navigate
                        // (navigate 改由 chip 内的 Link 触发 — 用户先看 chip, 决定是否跳)
                        e.preventDefault();
                        e.stopPropagation?.();
                        onSelectCity?.(isSelected ? null : c);
                      }}
                      style={{ cursor: "pointer", textDecoration: "none" }}
                      data-testid={`city-${encodeURIComponent(c.code).toLowerCase()}`}
                    >
                      <g style={{ cursor: "pointer" }}>
                        {/* V7: 选中态强化 — pulse ring 缩小到适配 1.5px hub dot */}
                        {isSelected && (
                          <>
                            {/* 外层 pulse ring (4px → 7px, 缩) */}
                            <circle
                              r={r + SELECTED_PULSE_OUTER_V8}
                              fill="#dc2626"
                              fillOpacity={0.1}
                              stroke="none"
                            >
                              <animate
                                attributeName="r"
                                from={r + 1.5}
                                to={r + 7}
                                dur="1.8s"
                                repeatCount="indefinite"
                              />
                              <animate
                                attributeName="fillOpacity"
                                from="0.2"
                                to="0"
                                dur="1.8s"
                                repeatCount="indefinite"
                              />
                            </circle>
                            {/* 中层 pulse ring (2.5px → 5px) */}
                            <circle
                              r={r + SELECTED_PULSE_INNER_V8}
                              fill="none"
                              stroke="#dc2626"
                              strokeWidth={0.8}
                              opacity={0.6}
                            >
                              <animate
                                attributeName="r"
                                from={r + 0.5}
                                to={r + 5}
                                dur="1.8s"
                                repeatCount="indefinite"
                              />
                              <animate
                                attributeName="opacity"
                                from="0.7"
                                to="0"
                                dur="1.8s"
                                repeatCount="indefinite"
                              />
                            </circle>
                            {/* 选中实心 ring (r + 1.5 紧贴 hub halo) */}
                            <circle
                              r={HUB_HALO_R_V8}
                              fill="none"
                              stroke="#dc2626"
                              strokeWidth={SELECTED_RING_W_V8}
                            />
                          </>
                        )}

                        {/* hovered letter — pulse 圈 (V6 缩小到 1→3) */}
                        {isLetterPulse && (
                          <circle
                            r={r + HOVERED_PULSE_INNER_V8}
                            fill="none"
                            stroke="#1e40af"
                            strokeWidth={1}
                            opacity={0.7}
                          >
                            <animate
                              attributeName="r"
                              from={r + 0.5}
                              to={r + HOVERED_PULSE_OUTER_V8}
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

                        {/* V7: hub 蓝发光背景圈 (subtle, 蓝 halo, r=HUB_HALO_R_V8) */}
                        {isHub && !isSelected && (
                          <circle
                            r={HUB_HALO_R_V8}
                            fill="#2563eb"
                            fillOpacity={0.18}
                            stroke="none"
                          />
                        )}

                        {/* 主 dot */}
                        <circle
                          r={r}
                          fill={fill}
                          fillOpacity={fillOpacity}
                          stroke={isHub || isSelected ? "#ffffff" : "none"}
                          strokeWidth={isHub ? HUB_STROKE_W_V8 : isSelected ? 1 : 0}
                          filter={isSelected ? "url(#selected-glow)" : isHub ? "url(#hub-glow)" : undefined}
                          style={{ transition: "all 0.15s" }}
                        />

                        {/* V10: 删 IATA label (NJX 拍"应该显示中文名"), 只留 CN */}
                        {/* V10: CN 名 label 永远在 dot 右侧 + 白底框防遮 */}
                        {showCnName && (
                          <g style={{ pointerEvents: "none" }}>
                            <rect
                              x={r + 1.5}
                              y={2 / zoom}
                              width={Math.max(
                                24,
                                (c.name || "").length * 7
                              ) / zoom}
                              height={10 / zoom}
                              fill="#ffffff"
                              fillOpacity={0.85}
                              rx={1.5 / zoom}
                              stroke="#e5e7eb"
                              strokeWidth={0.3 / zoom}
                            />
                            <text
                              x={r + HUB_LABEL_GAP_V8}
                              y={9}
                              textAnchor="start"
                              style={{
                                fontFamily:
                                  "-apple-system, BlinkMacSystemFont, 'PingFang SC', 'Microsoft YaHei', sans-serif",
                                fontSize: cnNameFontSize,
                                fontWeight: isHub ? 600 : 500,
                                fill: isSelected
                                  ? "#dc2626"
                                  : isHub
                                  ? "#1e40af"
                                  : "#6b7280",
                                letterSpacing: 0.2,
                              }}
                            >
                              {c.name}
                            </text>
                          </g>
                        )}
                      </g>
                    </a>
                  </Marker>
                );
              })}

              {/* V6 改造 2: Cluster dots (zoom ≤ 4 时, supercluster 聚合 hubs) */}
              {clusterFeatures &&
                clusterFeatures.map((feat) => {
                  const [lon, lat] = feat.geometry.coordinates;
                  const props: any = feat.properties;
                  // cluster 节点 vs 单点
                  if (props.cluster) {
                    const count = props.point_count as number;
                    // V6: cluster dot 大小按 count 缩放 (6px → 14px)
                    // 公式: r = 5 + sqrt(count) * 1.5, 3 站 ≈ 7.6, 10 站 ≈ 9.7
                    const r = Math.min(14, 5 + Math.sqrt(count) * 1.5);
                    return (
                      <Marker
                        key={`cluster-${props.cluster_id}`}
                        coordinates={[lon, lat]}
                        onMouseEnter={() => {
                          setHovered(`cluster-${props.cluster_id}`);
                          setHoverAnchor({ x: 0, y: 0 });
                        }}
                        onMouseLeave={() => setHovered(null)}
                      >
                        <g
                          style={{ cursor: "pointer" }}
                          data-testid={`cluster-${props.cluster_id}`}
                          onClick={() => {
                            // V6: click cluster → zoom in 1 级 + 居中
                            // 1 级太少, 用 cluster.getClusterExpansionZoom 拿精确级
                            const expansionZoom =
                              cluster?.getClusterExpansionZoom(
                                props.cluster_id
                              ) ?? Math.min(ZOOM_MAX, zoom + 1);
                            animateTo(
                              Math.max(zoom + 0.5, expansionZoom),
                              [lon, lat],
                              400
                            );
                          }}
                        >
                          {/* 外层白边 (光晕) */}
                          <circle
                            r={r + 2}
                            fill="#ffffff"
                            fillOpacity={0.85}
                            stroke="none"
                          />
                          {/* 蓝填充 */}
                          <circle
                            r={r}
                            fill="#2563eb"
                            fillOpacity={0.95}
                            stroke="#ffffff"
                            strokeWidth={1.5}
                            filter="url(#hub-glow)"
                          />
                          {/* 数字 label (白色 9px bold) */}
                          <text
                            textAnchor="middle"
                            dominantBaseline="central"
                            y={0}
                            pointerEvents="none"
                            style={{
                              fontFamily:
                                "-apple-system, BlinkMacSystemFont, 'PingFang SC', 'Microsoft YaHei', sans-serif",
                              fontSize: 12 / zoom,
                              fontWeight: 800,
                              fill: "#ffffff",
                              letterSpacing: 0.3,
                              paintOrder: "stroke",
                              stroke: "#1e40af",
                              strokeWidth: 4 / zoom,
                            }}
                          >
                            {count >= 1000
                              ? `${(count / 1000).toFixed(1)}k`
                              : count}
                          </text>
                        </g>
                      </Marker>
                    );
                  } else {
                    // 单点 (cluster 不形成, zoom 低偏远地区单 hub) — 显示 hub dot
                    return (
                      <Marker
                        key={`hub-${props.code}`}
                        coordinates={[lon, lat]}
                        onMouseEnter={(e: any) => {
                          setHovered(props.code);
                          if (e && e.clientX != null) {
                            const mapEl = (
                              document.querySelector(
                                "[data-testid='world-map-root']"
                              ) as HTMLElement
                            )?.getBoundingClientRect();
                            if (mapEl) {
                              setHoverAnchor({
                                x: e.clientX - mapEl.left,
                                y: e.clientY - mapEl.top,
                              });
                            } else {
                              setHoverAnchor({ x: e.clientX, y: e.clientY });
                            }
                          }
                        }}
                        onMouseLeave={() => setHovered(null)}
                      >
                        <a
                          href={`/city/${encodeURIComponent(props.code).toLowerCase()}`}
                          onClick={(e: any) => {
                            e.preventDefault();
                            e.stopPropagation?.();
                            // 找原始 city 对象
                            const c = hubs.find((x) => x.code === props.code);
                            if (c) onSelectCity?.(c);
                          }}
                          style={{ cursor: "pointer", textDecoration: "none" }}
                        >
                          <g style={{ cursor: "pointer" }}>
                            {/* V7: hub 蓝发光背景圈 (HUB_HALO_R_V8) */}
                            <circle
                              r={HUB_HALO_R_V8}
                              fill="#2563eb"
                              fillOpacity={0.18}
                              stroke="none"
                            />
                            {/* 主 dot */}
                            <circle
                              r={HUB_DOT_V8}
                              fill="#2563eb"
                              fillOpacity={0.95}
                              stroke="#ffffff"
                              strokeWidth={HUB_STROKE_W_V8}
                              filter="url(#hub-glow)"
                            />
                            {/* V10: 删 IATA label (NJX 拍"应该显示中文名"), 只留 CN */}
                            {/* V8: CN 名 label 永远在 dot 右侧 + 白底框 */}
                            <g style={{ pointerEvents: "none" }}>
                              <rect
                                x={HUB_DOT_V8 + 1.5}
                                y={2 / zoom}
                                width={Math.max(
                                  24,
                                  (props.name || "").length * 7
                                ) / zoom}
                                height={10 / zoom}
                                fill="#ffffff"
                                fillOpacity={0.85}
                                rx={1.5 / zoom}
                                stroke="#e5e7eb"
                                strokeWidth={0.3 / zoom}
                              />
                              <text
                                x={HUB_DOT_V8 + HUB_LABEL_GAP_V8}
                                y={9}
                                textAnchor="start"
                                style={{
                                  fontFamily:
                                    "-apple-system, BlinkMacSystemFont, 'PingFang SC', 'Microsoft YaHei', sans-serif",
                                  fontSize: 16 / zoom,
                                  fontWeight: 600,
                                  fill: "#1e40af",
                                  letterSpacing: 0.2,
                                }}
                              >
                                {props.name}
                              </text>
                            </g>
                          </g>
                        </a>
                      </Marker>
                    );
                  }
                })}
            </ZoomableGroup>
          </ComposableMap>
        </div>

        {/* 右侧控制条 */}
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

        {/* 缩略图 (V5: dot 差异化 — hub 3px 红 + 普通 1px 灰) */}
        <MiniMap
          zoom={zoom}
          center={center}
          cities={withCoords}
          hubSet={hubSet}
        />

        {/* V5 改造 4: 选中城市 chip — bottom-left 浮动, 显示城市名 + IATA + view_count + 周边 */}
        {selectedCity && (
          <div
            className="absolute bottom-3 left-3 z-20 inline-flex max-w-[60%] flex-col gap-1 rounded-lg border border-red-200 bg-white/95 px-3 py-2 text-xs shadow-soft backdrop-blur"
            data-testid="selected-chip"
          >
            <Link
              href={`/city/${encodeURIComponent(selectedCity.code).toLowerCase()}`}
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

        {/* V5: hover 浮动 tooltip (浮动在 dot 屏幕位置上方 24px) */}
        {hovered && hovered !== selectedCity?.code && (
          <HoverTooltip
            city={withCoords.find((c) => c.code === hovered)!}
            isHub={hubSet.has(hovered)}
            distance={nearbyDistances.get(hovered)}
            anchor={hoverAnchor}
          />
        )}

        {/* Footer caption */}
        <div className="pointer-events-none absolute left-3 top-3 hidden flex-col gap-0.5 text-[10px] text-ink-400 sm:flex">
          <span>滚轮缩放 · 拖动平移</span>
          <span>点城市查看周边 · 红圈 = 选中</span>
        </div>
      </div>
    </div>
  );
}

/* ============================================================
 *  VerticalZoomSlider — 垂直滑块 (V3 保留)
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
      <div className="mb-0.5 text-[8px] font-medium tabular-nums text-ink-400">
        {max}
      </div>
      <div
        ref={trackRef}
        onMouseDown={(e) => {
          draggingRef.current = true;
          updateFromY(e.clientY);
          e.preventDefault();
        }}
        className="relative h-24 w-1.5 cursor-pointer rounded-full bg-ink-100"
      >
        <div
          className="absolute bottom-0 left-0 right-0 rounded-full bg-primary/40 transition-[height] duration-150"
          style={{ height: `${pct}%` }}
        />
        <div
          className="absolute left-1/2 h-2.5 w-2.5 -translate-x-1/2 rounded-full border-2 border-primary bg-white shadow-sm transition-[bottom] duration-150"
          style={{ bottom: `calc(${pct}% - 5px)` }}
        />
      </div>
      <div className="mt-0.5 text-[8px] font-medium tabular-nums text-ink-400">
        {min}
      </div>
    </div>
  );
}

/* ============================================================
 *  V5: HoverTooltip — 浮动 tooltip (跟随 dot 屏幕位置)
 *  anchor: { x, y } — 鼠标在地图区域内的坐标 (相对 data-testid='world-map-root')
 *  位置: dot 上方 24px, 水平居中
 * ============================================================ */
function HoverTooltip({
  city,
  isHub,
  distance,
  anchor,
}: {
  city: City;
  isHub: boolean;
  distance?: number;
  anchor: { x: number; y: number } | null;
}) {
  if (!city || !anchor) return null;
  return (
    <div
      className={cn(
        "pointer-events-none absolute z-30 -translate-x-1/2",
        "rounded-md border bg-white/95 px-2.5 py-1.5 text-[11px] shadow-soft backdrop-blur",
        isHub ? "border-primary/40" : "border-ink-200"
      )}
      style={{
        left: anchor.x,
        top: Math.max(8, anchor.y - 28), // dot 上方 28px, 不超出顶部
      }}
      data-testid="hover-tooltip"
    >
      <div className="flex items-center gap-1.5">
        {isHub && (
          <span className="rounded bg-primary/10 px-1 text-[9px] font-bold text-primary">
            HUB
          </span>
        )}
        <span className="font-semibold text-ink-900">{city.name}</span>
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
        <div className="mt-0.5 text-[9px] text-ink-500">距 {distance} km</div>
      )}
    </div>
  );
}

/* ============================================================
 *  MiniMap — 200x100 缩略图 (V5 优化: 完整 218 城, hub 3px 红 + 普通 1px 灰)
 * ============================================================ */
function MiniMap({
  zoom,
  center,
  cities,
  hubSet,
}: {
  zoom: number;
  center: [number, number];
  cities: City[];
  hubSet: Set<string>;
}) {
  const W = 200;
  const H = 100;
  const centerX = ((center[0] + 180) / 360) * W;
  const centerY = ((90 - center[1]) / 180) * H;
  const rectW = Math.max(8, Math.min(W, W / zoom));
  const rectH = Math.max(4, Math.min(H, H / zoom));
  const rectX = Math.max(0, Math.min(W - 4, centerX - rectW / 2));
  const rectY = Math.max(0, Math.min(H - 4, centerY - rectH / 2));

  return (
    <div
      className="pointer-events-none absolute bottom-3 right-16 overflow-hidden rounded-md border border-ink-200 bg-white shadow-soft"
      data-testid="minimap"
    >
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
        {/* 城市 dot 叠加层 (V5 优化) */}
        <svg
          width={W}
          height={H}
          viewBox={`0 0 ${W} ${H}`}
          className="absolute inset-0"
        >
          {cities.map((c) => {
            if (c.lat == null || c.lon == null) return null;
            const x = ((c.lon + 180) / 360) * W;
            const y = ((90 - c.lat) / 180) * H;
            const isHub = hubSet.has(c.code);
            return (
              <circle
                key={c.code}
                cx={x}
                cy={y}
                r={isHub ? 2 : 0.7}
                fill={isHub ? "#dc2626" : "#9ca3af"}
                fillOpacity={isHub ? 0.85 : 0.5}
              />
            );
          })}
        </svg>
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
