import { keepPreviousData, useQuery } from "@tanstack/react-query";

import { api } from "../api/client";
import type { Filters } from "./params";
import type { Viewport } from "./SearchMap";

export const PAGE_SIZE = 20;
/** Больше API не отдаёт за один запрос (`limit` ≤ 100, иначе 422). */
export const MAX_LIMIT = 100;

export function useTrackSearch(filters: Filters, viewport: Viewport | null, limit: number) {
  const q = filters.q.trim();
  return useQuery({
    queryKey: ["search", filters, q ? null : viewport?.bbox, viewport?.zoom, limit],
    enabled: viewport !== null || q !== "",
    placeholderData: keepPreviousData,
    queryFn: async () => {
      const { data, error } = await api.GET("/tracks/search", {
        params: {
          query: {
            // Текстовый поиск идёт по всем трекам, без области карты.
            bbox: viewport && !q ? viewport.bbox.map((v) => v.toFixed(5)).join(",") : undefined,
            zoom: viewport?.zoom ?? 12,
            category: filters.cat ?? undefined,
            dist_min_km: filters.dmin ?? undefined,
            dist_max_km: filters.dmax ?? undefined,
            time_min_s: filters.tmin !== null ? filters.tmin * 60 : undefined,
            time_max_s: filters.tmax !== null ? filters.tmax * 60 : undefined,
            pace_min_s: filters.pmin ?? undefined,
            pace_max_s: filters.pmax ?? undefined,
            date_from: filters.from ?? undefined,
            date_to: filters.to ?? undefined,
            has_attempts: filters.att ?? undefined,
            is_new: filters.fresh ?? undefined,
            q: q || undefined,
            sort: filters.sort,
            limit,
          },
        },
      });
      if (error || !data) throw new Error("search failed");
      return data;
    },
  });
}
