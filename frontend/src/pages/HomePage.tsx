import { useCallback, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useSearchParams } from "react-router";

import { DistanceFilter } from "../search/DistanceFilter";
import { MoreFilters } from "../search/MoreFilters";
import { activeExtraFilters, readFilters, readView, SORTS, writeParams } from "../search/params";
import type { Filters, Sort } from "../search/params";
import { ResultList } from "../search/ResultList";
import { SearchMap } from "../search/SearchMap";
import type { Viewport } from "../search/SearchMap";
import { TrackCardPanel } from "../search/TrackCardPanel";
import { PAGE_SIZE, useTrackSearch } from "../search/useSearch";
import { useTrack } from "../tracks/api";

export function HomePage() {
  const { t } = useTranslation();
  const [params, setParams] = useSearchParams();
  const filters = useMemo(() => readFilters(params), [params]);
  const [initialView] = useState(() => readView(params));
  const selectedId = params.get("track");
  const [viewport, setViewport] = useState<Viewport | null>(null);
  const [moreOpen, setMoreOpen] = useState(activeExtraFilters(filters) > 0);
  const [sheetOpen, setSheetOpen] = useState(false);
  const [limit, setLimit] = useState(PAGE_SIZE);
  const [query, setQuery] = useState(filters.q);
  // «Показать на карте»: при открытии с ?track= карта подгоняется под трек один раз.
  const [fitKey] = useState(() => (params.get("track") && params.get("fit") ? 1 : 0));

  const search = useTrackSearch(filters, viewport, limit);
  const selected = useTrack(selectedId ?? "", { enabled: Boolean(selectedId) });

  const update = useCallback(
    (patch: Partial<Filters>) => {
      setLimit(PAGE_SIZE);
      setParams((p) => writeParams(p, patch), { replace: true });
    },
    [setParams],
  );

  const onViewChange = useCallback(
    (v: Viewport) => {
      setViewport(v);
      setParams((p) => writeParams(p, { lat: v.center.lat, lon: v.center.lon, z: v.zoom }), {
        replace: true,
      });
    },
    [setParams],
  );

  const select = useCallback(
    (id: string | null) => {
      setParams((p) => {
        const next = new URLSearchParams(p);
        next.delete("fit");
        if (id) next.set("track", id);
        else next.delete("track");
        return next;
      });
      if (id) setSheetOpen(true);
    },
    [setParams],
  );

  const data = search.data;
  const extra = activeExtraFilters(filters);
  const card = selectedId && selected.data ? selected.data : null;

  return (
    <main className="map-page">
      <h1 className="visually-hidden">{t("search.title")}</h1>
      <aside className={`map-panel${sheetOpen ? " map-panel--open" : ""}`}>
        <div className="map-panel__filters">
          <form
            className="search-box"
            role="search"
            onSubmit={(e) => {
              e.preventDefault();
              update({ q: query });
            }}
          >
            <input
              className="input input--sm"
              type="search"
              placeholder={t("search.placeholder")}
              aria-label={t("search.placeholder")}
              value={query}
              onChange={(e) => {
                setQuery(e.target.value);
                if (e.target.value === "") update({ q: "" });
              }}
            />
          </form>
          <DistanceFilter filters={filters} onChange={update} />
          <button
            type="button"
            className="link-btn"
            aria-expanded={moreOpen}
            onClick={() => setMoreOpen(!moreOpen)}
          >
            {t("search.moreFilters")}
            {extra > 0 && ` · ${extra}`}
          </button>
          {moreOpen && <MoreFilters filters={filters} onChange={update} />}
        </div>

        <div className="map-panel__body">
          {card ? (
            <TrackCardPanel track={card} onBack={() => select(null)} />
          ) : (
            <>
              <div className="row-between list-head">
                <button
                  type="button"
                  className="sheet-toggle"
                  aria-expanded={sheetOpen}
                  onClick={() => setSheetOpen(!sheetOpen)}
                >
                  <strong>
                    {filters.q.trim()
                      ? t("search.foundByText", { count: data?.total ?? 0 })
                      : t("search.inArea", { count: data?.total ?? 0 })}
                  </strong>
                </button>
                <label className="sort">
                  <span className="visually-hidden">{t("search.sortLabel")}</span>
                  <select
                    value={filters.sort}
                    onChange={(e) => update({ sort: e.target.value as Sort })}
                  >
                    {SORTS.map((s) => (
                      <option key={s} value={s}>
                        {t(`search.sort.${s}`)}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
              {data && data.items.length === 0 && (
                <div className="empty">{t("search.nothing")}</div>
              )}
              {data && <ResultList items={data.items} selectedId={selectedId} onSelect={select} />}
              {data && data.items.length < data.total && (
                <button
                  type="button"
                  className="btn btn--secondary btn--block"
                  onClick={() => setLimit(limit + PAGE_SIZE)}
                >
                  {t("search.more")}
                </button>
              )}
            </>
          )}
        </div>
      </aside>

      <div className="map-wrap">
        <SearchMap
          initialView={initialView}
          lines={data?.lines ?? []}
          clusters={data?.clusters ?? []}
          selectedId={selectedId}
          selectedLine={selected.data?.geometry?.coordinates ?? null}
          fitKey={selected.data ? fitKey : 0}
          onViewChange={onViewChange}
          onSelect={select}
        />
      </div>
    </main>
  );
}
