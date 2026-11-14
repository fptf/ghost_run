import { useCallback, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";

import { CATEGORY_LABELS } from "../lib/format";
import { DistanceFilter } from "../search/DistanceFilter";
import {
  getHomeView,
  getNearbyAnswer,
  locate,
  setHomeView,
  setNearbyAnswer,
} from "../search/homeView";
import { MoreFilters } from "../search/MoreFilters";
import {
  activeExtraFilters,
  hasActiveFilters,
  hasViewInUrl,
  readFilters,
  readView,
  sameView,
  SORTS,
  writeParams,
} from "../search/params";
import type { Filters, Sort, View } from "../search/params";
import { ResultList } from "../search/ResultList";
import { SearchMap } from "../search/SearchMap";
import type { Viewport } from "../search/SearchMap";
import { TrackCardPanel } from "../search/TrackCardPanel";
import { PAGE_SIZE, useTrackSearch } from "../search/useSearch";
import { useUrlParams } from "../search/useUrlParams";
import { useTrack } from "../tracks/api";

const NEARBY_ZOOM = 13;

function ChevronIcon({ up }: { up: boolean }) {
  return (
    <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
      <path
        d={up ? "M6 15l6-6 6 6" : "M6 9l6 6 6-6"}
        fill="none"
        stroke="currentColor"
        strokeWidth="2.2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

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
  const [askNearby, setAskNearby] = useState(
    () => getNearbyAnswer() === null && !hasViewInUrl(params) && !params.has("track"),
  );
  const [nearbyError, setNearbyError] = useState(false);
  // «Показать на карте»: при открытии с ?track=…&fit=1 карта подгоняется под трек один раз.
  const [fitKey, setFitKey] = useState(() => (params.get("track") && params.get("fit") ? 1 : 0));

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

  async function answerNearby(yes: boolean) {
    setAskNearby(false);
    setNearbyAnswer(yes ? "accepted" : "declined");
    if (!yes) return;
    try {
      const pos = await locate();
      const view = { lat: pos.lat, lon: pos.lon, z: NEARBY_ZOOM };
      setHomeView(view);
      setHome(view);
      setFlyTo({ ...view, key: Date.now() });
    } catch {
      setNearbyError(true);
      window.setTimeout(() => setNearbyError(false), 5000);
    }
  }

  const data = search.data;
  const extra = activeExtraFilters(filters);
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

  const activeCount =
    activeExtraFilters(filters) +
    (filters.fresh ? 1 : 0) +
    (filters.att ? 1 : 0) +
    (filters.q.trim() ? 1 : 0);
  const distanceLabel = filters.cat
    ? CATEGORY_LABELS[filters.cat]
    : filters.dmin !== null || filters.dmax !== null
      ? t("search.customRange", { min: filters.dmin ?? 0, max: filters.dmax ?? "∞" })
      : t("search.anyDistance");
  const filtersSummary = activeCount > 0 ? `${distanceLabel} · +${activeCount}` : distanceLabel;

  return (
    <main className={`map-page${panelHidden ? " map-page--panel-hidden" : ""}`}>
      <h1 className="visually-hidden">{t("search.title")}</h1>
      <aside className={`map-panel${listOpen ? " map-panel--open" : ""}`}>
        <div
          className={`map-panel__filters${filtersCollapsed ? " map-panel__filters--collapsed" : ""}`}
        >
          <button
            type="button"
            className="filters-compact"
            aria-expanded={!filtersCollapsed}
            onClick={() => setFiltersCollapsed(false)}
          >
            <strong>{t("search.filters")}</strong>
            <span className="muted">{filtersSummary}</span>
            <span aria-hidden>▾</span>
          </button>
          <div className="search-row">
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
            <button
              type="button"
              className="icon-btn panel-hide"
              aria-label={t("search.hidePanel")}
              title={t("search.hidePanel")}
              onClick={() => setPanelHidden(true)}
            >
              <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true">
                <path
                  d="M15 6l-6 6 6 6"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2.2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </button>
          </div>
          <DistanceFilter key={resetKey} filters={filters} onChange={update} />
          <div className="row quick-filters" role="group" aria-label={t("search.quickFilters")}>
            <button
              type="button"
              className="pill"
              aria-pressed={filters.fresh === true}
              onClick={() => update({ fresh: filters.fresh ? null : true })}
            >
              {t("search.new")}
            </button>
            <button
              type="button"
              className="pill"
              aria-pressed={filters.att === true}
              onClick={() => update({ att: filters.att ? null : true })}
            >
              {t("search.hasAttempts")}
            </button>
            <button
              type="button"
              className="pill"
              aria-expanded={moreOpen}
              onClick={() => setMoreOpen(!moreOpen)}
            >
              {t("search.moreFilters")}
              {extra > 0 && ` · ${extra}`}
            </button>
            {canReset && (
              <button type="button" className="link-btn reset-btn" onClick={reset}>
                {t("search.reset")}
              </button>
            )}
          </div>
          {moreOpen && <MoreFilters filters={filters} onChange={update} />}
          <button
            type="button"
            className="link-btn filters-hide"
            onClick={() => setFiltersCollapsed(true)}
          >
            {t("search.hideFilters")} ▴
          </button>
        </div>

        <div className="map-panel__body">
          <div className="list-head">
            <button
              type="button"
              className="sheet-toggle"
              aria-expanded={listOpen}
              onClick={() => setListOpen(!listOpen)}
            >
              <strong>{countLabel}</strong>
              <span className="sheet-toggle__action">
                {listOpen ? t("search.hideList") : t("search.showList")}
                <ChevronIcon up={!listOpen} />
              </span>
            </button>
            {!card && (
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
            )}
          </div>
          <div className="map-panel__content">
            {card ? (
              <TrackCardPanel track={card} onBack={() => select(null)} />
            ) : (
              <>
                {data && data.items.length === 0 && (
                  <div className="empty">{t("search.nothing")}</div>
                )}
                {data && (
                  <ResultList
                    items={data.items}
                    selectedId={selectedId}
                    onSelect={(id) => {
                      select(id);
                      setFitKey((k) => k + 1); // выбор из списка — показать трек на карте целиком
                    }}
                  />
                )}
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
        {askNearby && (
          <div
            className="map-float map-float--prompt"
            role="dialog"
            aria-label={t("search.nearbyQuestion")}
          >
            <strong>{t("search.nearbyQuestion")}</strong>
            <div className="row">
              <button
                type="button"
                className="btn btn--primary btn--sm"
                onClick={() => void answerNearby(true)}
              >
                {t("search.nearbyYes")}
              </button>
              <button
                type="button"
                className="btn btn--ghost btn--sm"
                onClick={() => void answerNearby(false)}
              >
                {t("search.nearbyNo")}
              </button>
            </div>
          </div>
        )}
        {nearbyError && (
          <p role="status" className="notice notice--info map-float map-float--prompt">
            {t("search.nearbyFailed")}
          </p>
        )}
      </div>
    </main>
  );
}
