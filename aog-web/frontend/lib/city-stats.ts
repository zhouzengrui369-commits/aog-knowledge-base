// 城市静态数据 - view_count 排序 + lat/lon 世界地图
// 数据来源: aog-web/backend/data/aog.db (本任务一次性导出)
// 设计: 优先用 API 返回的字段（如有），否则 fallback 到静态数据
//       这样 SCF 即使不重部署（当前未返回这些字段），前端也能用

import rawData from "./city-stats.json";

interface CityStats {
  view_count: Record<string, number>;
  coords: Record<string, [number, number]>; // [lon, lat]
}

const data = rawData as unknown as CityStats;

/** 给城市数组补 view_count + lat/lon（保留 API 字段优先） */
export function enrichCities<T extends { code: string; view_count?: number; lat?: number; lon?: number }>(
  cities: T[]
): T[] {
  return cities.map((c) => {
    if (c.view_count == null && data.view_count[c.code] != null) {
      c.view_count = data.view_count[c.code];
    }
    if ((c.lat == null || c.lon == null) && data.coords[c.code]) {
      const [lon, lat] = data.coords[c.code];
      c.lon = lon;
      c.lat = lat;
    }
    return c;
  });
}

/** 按 view_count 降序取前 N（view_count 默认 0，无数据排后面） */
export function topByViewCount<T extends { code: string; view_count?: number }>(
  cities: T[],
  n: number
): T[] {
  return [...cities]
    .sort((a, b) => (b.view_count ?? 0) - (a.view_count ?? 0))
    .slice(0, n);
}

/** 有 lat/lon 的城市（世界地图用） */
export function citiesWithCoords<T extends { lat?: number; lon?: number }>(cities: T[]): T[] {
  return cities.filter((c) => c.lat != null && c.lon != null);
}
