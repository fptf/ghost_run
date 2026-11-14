import { useCallback, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { FiltersPanel } from "../search/FiltersPanel";
import { getHomeView, getNearbyAnswer } from "../search/homeView";
import { NearbyPrompt } from "../search/NearbyPrompt";
import {
  activeExtraFilters,
  hasActiveFilters,
  hasViewInUrl,
  readFilters,
  readView,
  sameView,
  writeParams,
} from "../search/params";
import type { Filters, View } from "../search/params";
import { ResultsPanel } from "../search/ResultsPanel";
import { SearchMap } from "../search/SearchMap";
import type { Viewport } from "../search/SearchMap";
import { MAX_LIMIT, PAGE_SIZE, useTrackSearch } from "../search/useSearch";
import { useUrlParams } from "../search/useUrlParams";
import { useTrack } from "../tracks/api";

/** Главная: карта треков с панелью фильтров и списком. */
export function HomePage() {
  const { t } = useTranslation();
  const [params, setParams] = useUrlParams();
  const filters = useMemo(() => readFilters(params), [params]);
  const [homeView, setHome] = useState<View>(getHomeView);
  const [initialView] = useState<View>(() =>
    hasViewInUrl(params) ? readView(params) : getHomeView(),
  );
  const selectedId = params.get("track");
  const [viewport, setViewport] = useState<Viewport | null>(null);
  const [moreOpen, setMoreOpen] = useState(activeExtraFilters(filters) > 0);
  const [filtersCollapsed, setFiltersCollapsed] = useState(false); // телефон: фильтры свёрнуты
  const [resetKey, setResetKey] = useState(0); // пересоздаёт фильтр дистанции при сбросе
  const [listOpen, setListOpen] = useState(false); // телефон: выдвижной список
  const [panelHidden, setPanelHidden] = useState(false); // десктоп: левая панель
  const [limit, setLimit] = useState(PAGE_SIZE);
  const [query, setQuery] = useState(filters.q);
  const [flyTo, setFlyTo] = useState<(View & { key: number }) | null>(null);
  const [askNearby] = useState(
    () => getNearbyAnswer() === null && !hasViewInUrl(params) && !params.has("track"),
  );
  // «Показать на карте»: при открытии с ?track=…&fit=1 карта подгоняется под трек один раз.
  const [fitKey, setFitKey] = useState(() => (params.get("track") && params.get("fit") ? 1 : 0));

  const filtersRef = useRef<HTMLDivElement>(null);
  const bodyRef = useRef<HTMLDivElement>(null);
  const overlays = useCallback(() => [filtersRef.current, bodyRef.current], []);

  const search = useTrackSearch(filters, viewport, limit);
  const selected = useTrack(selectedId ?? "", { enabled: Boolean(selectedId) });

  const update = useCallback(
    (patch: Partial<Filters>) => {
      setLimit(PAGE_SIZE);
      setParams((p) => writeParams(p, patch));
    },
    [setParams],
  );

  const onViewChange = useCallback(
    (v: Viewport) => {
      setViewport(v);
      setParams((p) => writeParams(p, { lat: v.center.lat, lon: v.center.lon, z: v.zoom }));
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
      }, false);
      if (id) {
        setListOpen(true);
        setPanelHidden(false);
      }
    },
    [setParams],
  );

  const reset = useCallback(() => {
    setQuery("");
    setLimit(PAGE_SIZE);
    setMoreOpen(false);
    setResetKey((k) => k + 1);
    setParams(() => new URLSearchParams());
    setFlyTo({ ...homeView, key: Date.now() });
  }, [homeView, setParams]);

  const onLocated = useCallback((view: View) => {
    setHome(view);
    setFlyTo({ ...view, key: Date.now() });
  }, []);

  const data = search.data;
  const card = selectedId && selected.data ? selected.data : null;
  const currentView = viewport
    ? { lat: viewport.center.lat, lon: viewport.center.lon, z: viewport.zoom }
    : initialView;
  const canReset =
    hasActiveFilters(filters) || Boolean(selectedId) || !sameView(currentView, homeView);
  const total = data?.total ?? 0;
  const countLabel = filters.q.trim()
    ? t("search.foundByText", { count: total })
    : t("search.inArea", { count: total });

  return (
    <main className={`map-page${panelHidden ? " map-page--panel-hidden" : ""}`}>
      <h1 className="visually-hidden">{t("search.title")}</h1>
      <aside className={`map-panel${listOpen ? " map-panel--open" : ""}`}>
        <FiltersPanel
          panelRef={filtersRef}
          filters={filters}
          query={query}
          onQueryChange={setQuery}
          onChange={update}
          collapsed={filtersCollapsed}
          onCollapsedChange={setFiltersCollapsed}
          moreOpen={moreOpen}
          onMoreOpenChange={setMoreOpen}
          resetKey={resetKey}
          canReset={canReset}
          onReset={reset}
          onHidePanel={() => setPanelHidden(true)}
        />
        <ResultsPanel
          panelRef={bodyRef}
          data={data}
          countLabel={countLabel}
          sort={filters.sort}
          onChange={update}
          listOpen={listOpen}
          onListOpenChange={setListOpen}
          card={card}
          selectedId={selectedId}
          onSelect={(id) => {
            select(id);
            setFitKey((k) => k + 1); // выбор из списка — показать трек на карте целиком
          }}
          onBack={() => select(null)}
          canLoadMore={Boolean(data && data.items.length < data.total && limit < MAX_LIMIT)}
          onLoadMore={() => setLimit(Math.min(limit + PAGE_SIZE, MAX_LIMIT))}
        />
      </aside>

      <div className="map-wrap">
        <SearchMap
          initialView={initialView}
          lines={data?.lines ?? []}
          clusters={data?.clusters ?? []}
          selectedId={selectedId}
          selectedLine={selected.data?.geometry?.coordinates ?? null}
          fitKey={selected.data ? fitKey : 0}
          overlays={overlays}
          flyTo={flyTo}
          onViewChange={onViewChange}
          onSelect={select}
        />
        {panelHidden && (
          <button
            type="button"
            className="btn btn--secondary map-float map-float--list"
            onClick={() => setPanelHidden(false)}
          >
            {t("search.listButton", { count: total })}
          </button>
        )}
        <NearbyPrompt initiallyOpen={askNearby} onLocated={onLocated} />
      </div>
    </main>
  );
}
