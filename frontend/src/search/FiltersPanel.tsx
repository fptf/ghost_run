import type { RefObject } from "react";
import { useTranslation } from "react-i18next";

import { CATEGORY_LABELS } from "../lib/format";
import { DistanceFilter } from "./DistanceFilter";
import { MoreFilters } from "./MoreFilters";
import { activeExtraFilters } from "./params";
import type { Filters } from "./params";

/** Свёрнутые фильтры на телефоне: «5 км · +2». */
function useFiltersSummary(filters: Filters): string {
  const { t } = useTranslation();
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
  return activeCount > 0 ? `${distanceLabel} · +${activeCount}` : distanceLabel;
}

/** Верх левой панели главной: поиск, дистанция, быстрые и дополнительные фильтры. */
export function FiltersPanel({
  panelRef,
  filters,
  query,
  onQueryChange,
  onChange,
  collapsed,
  onCollapsedChange,
  moreOpen,
  onMoreOpenChange,
  resetKey,
  canReset,
  onReset,
  onHidePanel,
}: {
  panelRef: RefObject<HTMLDivElement>;
  filters: Filters;
  query: string;
  onQueryChange: (q: string) => void;
  onChange: (patch: Partial<Filters>) => void;
  collapsed: boolean;
  onCollapsedChange: (collapsed: boolean) => void;
  moreOpen: boolean;
  onMoreOpenChange: (open: boolean) => void;
  /** Меняется при сбросе — пересоздаёт фильтр дистанции. */
  resetKey: number;
  canReset: boolean;
  onReset: () => void;
  onHidePanel: () => void;
}) {
  const { t } = useTranslation();
  const summary = useFiltersSummary(filters);
  const extra = activeExtraFilters(filters);

  return (
    <div
      ref={panelRef}
      className={`map-panel__filters${collapsed ? " map-panel__filters--collapsed" : ""}`}
    >
      <button
        type="button"
        className="filters-compact"
        aria-expanded={!collapsed}
        onClick={() => onCollapsedChange(false)}
      >
        <strong>{t("search.filters")}</strong>
        <span className="muted">{summary}</span>
        <span aria-hidden>▾</span>
      </button>
      <div className="search-row">
        <form
          className="search-box"
          role="search"
          onSubmit={(e) => {
            e.preventDefault();
            onChange({ q: query });
          }}
        >
          <input
            className="input input--sm"
            type="search"
            placeholder={t("search.placeholder")}
            aria-label={t("search.placeholder")}
            value={query}
            onChange={(e) => {
              onQueryChange(e.target.value);
              if (e.target.value === "") onChange({ q: "" });
            }}
          />
        </form>
        <button
          type="button"
          className="icon-btn panel-hide"
          aria-label={t("search.hidePanel")}
          title={t("search.hidePanel")}
          onClick={onHidePanel}
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
      <DistanceFilter key={resetKey} filters={filters} onChange={onChange} />
      <div className="row quick-filters" role="group" aria-label={t("search.quickFilters")}>
        <button
          type="button"
          className="pill"
          aria-pressed={filters.fresh === true}
          onClick={() => onChange({ fresh: filters.fresh ? null : true })}
        >
          {t("search.new")}
        </button>
        <button
          type="button"
          className="pill"
          aria-pressed={filters.att === true}
          onClick={() => onChange({ att: filters.att ? null : true })}
        >
          {t("search.hasAttempts")}
        </button>
        <button
          type="button"
          className="pill"
          aria-expanded={moreOpen}
          onClick={() => onMoreOpenChange(!moreOpen)}
        >
          {t("search.moreFilters")}
          {extra > 0 && ` · ${extra}`}
        </button>
        {canReset && (
          <button type="button" className="link-btn reset-btn" onClick={onReset}>
            {t("search.reset")}
          </button>
        )}
      </div>
      {moreOpen && <MoreFilters filters={filters} onChange={onChange} />}
      <button
        type="button"
        className="link-btn filters-hide"
        onClick={() => onCollapsedChange(true)}
      >
        {t("search.hideFilters")} ▴
      </button>
    </div>
  );
}
