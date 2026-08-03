// Coordinate fallback only. Access counts must always come from the live API.
import rawData from "./city-stats.json";

interface CityStatsData {
  coords: Record<string, [number, number]>;
}

const data = rawData as unknown as CityStatsData;

export function enrichCities<T extends { code: string; view_count?: number; lat?: number; lon?: number }>(cities: T[]): T[] {
  return cities.map((city) => {
    if ((city.lat == null || city.lon == null) && data.coords?.[city.code]) {
      const [lon, lat] = data.coords[city.code];
      city.lon = lon;
      city.lat = lat;
    }
    return city;
  });
}

export function topByViewCount<T extends { code: string; view_count?: number }>(cities: T[], count: number): T[] {
  return [...cities]
    .sort((left, right) => (right.view_count ?? 0) - (left.view_count ?? 0) || left.code.localeCompare(right.code))
    .slice(0, count);
}

export function citiesWithCoords<T extends { lat?: number; lon?: number }>(cities: T[]): T[] {
  return cities.filter((city) => city.lat != null && city.lon != null);
}
