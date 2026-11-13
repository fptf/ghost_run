/** Состояние главной карты в адресе страницы: им можно поделиться, «Назад» работает. */

export const VLADIVOSTOK = { lat: 43.1155, lon: 131.8855, z: 12 };

export const CATEGORIES = ["1", "5", "10", "21", "21+"] as const;
export type Category = (typeof CATEGORIES)[number];
export const SORTS = ["popular", "distance", "pace", "date", "attempts"] as const;
export type Sort = (typeof SORTS)[number];

export interface Filters {
  cat: Category | null;
  dmin: number | null; // км
  dmax: number | null;
  tmin: number | null; // минуты
  tmax: number | null;
  pmin: number | null; // секунды на км
  pmax: number | null;
  from: string | null; // YYYY-MM-DD
  to: string | null;
  att: boolean | null;
  fresh: boolean | null; // «Новые»
  q: string;
  sort: Sort;
}

export interface View {
  lat: number;
  lon: number;
  z: number;
}

export const EMPTY_FILTERS: Filters = {
  cat: null,
  dmin: null,
  dmax: null,
  tmin: null,
  tmax: null,
  pmin: null,
  pmax: null,
  from: null,
  to: null,
  att: null,
  fresh: null,
  q: "",
  sort: "popular",
};

function num(p: URLSearchParams, key: string): number | null {
  const raw = p.get(key);
  if (raw === null || raw === "") return null;
  const n = Number(raw);
  return Number.isFinite(n) ? n : null;
}

export function readFilters(p: URLSearchParams): Filters {
  const cat = p.get("cat");
  const sort = p.get("sort");
  const att = p.get("att");
  return {
    cat: (CATEGORIES as readonly string[]).includes(cat ?? "") ? (cat as Category) : null,
    dmin: num(p, "dmin"),
    dmax: num(p, "dmax"),
    tmin: num(p, "tmin"),
    tmax: num(p, "tmax"),
    pmin: num(p, "pmin"),
    pmax: num(p, "pmax"),
    from: p.get("from") || null,
    to: p.get("to") || null,
    att: att === "1" ? true : att === "0" ? false : null,
    fresh: p.get("fresh") === "1" ? true : null,
    q: p.get("q") ?? "",
    sort: (SORTS as readonly string[]).includes(sort ?? "") ? (sort as Sort) : "popular",
  };
}

export function readView(p: URLSearchParams): View {
  const lat = num(p, "lat");
  const lon = num(p, "lon");
  const z = num(p, "z");
  return lat !== null && lon !== null && z !== null ? { lat, lon, z } : VLADIVOSTOK;
}

/** Пишет фильтры и вид в параметры, сохраняя прочие (например, выбранный трек). */
export function writeParams(
  base: URLSearchParams,
  patch: Partial<Filters> & Partial<View>,
): URLSearchParams {
  const next = new URLSearchParams(base);
  for (const [key, value] of Object.entries(patch)) {
    if (
      value === null ||
      value === undefined ||
      value === "" ||
      (key === "sort" && value === "popular")
    ) {
      next.delete(key);
    } else if (typeof value === "boolean") {
      next.set(key, value ? "1" : "0");
    } else if (key === "lat" || key === "lon") {
      next.set(key, (value as number).toFixed(5));
    } else if (key === "z") {
      next.set(key, (value as number).toFixed(2));
    } else {
      next.set(key, String(value));
    }
  }
  return next;
}

/** Фильтры, спрятанные под «Все фильтры». */
export function activeExtraFilters(f: Filters): number {
  return [f.tmin, f.tmax, f.pmin, f.pmax, f.from, f.to].filter((v) => v !== null).length;
}

/** Есть ли что сбрасывать в фильтрах и поиске. */
export function hasActiveFilters(f: Filters): boolean {
  return (
    activeExtraFilters(f) > 0 ||
    f.cat !== null ||
    f.dmin !== null ||
    f.dmax !== null ||
    f.att !== null ||
    f.fresh !== null ||
    f.q.trim() !== "" ||
    f.sort !== "popular"
  );
}

export function sameView(a: View, b: View): boolean {
  return (
    Math.abs(a.lat - b.lat) < 1e-3 && Math.abs(a.lon - b.lon) < 1e-3 && Math.abs(a.z - b.z) < 0.05
  );
}

export function hasViewInUrl(p: URLSearchParams): boolean {
  return p.has("lat") && p.has("lon") && p.has("z");
}
