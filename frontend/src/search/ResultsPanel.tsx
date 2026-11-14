import type { RefObject } from "react";
import { useTranslation } from "react-i18next";

import type { Schemas } from "../api/client";
import type { TrackDetail } from "../tracks/api";
import { SORTS } from "./params";
import type { Filters, Sort } from "./params";
import { ResultList } from "./ResultList";
import { TrackCardPanel } from "./TrackCardPanel";

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

/** Низ левой панели главной: счётчик, сортировка, список или карточка выбранного трека. */
export function ResultsPanel({
  panelRef,
  data,
  countLabel,
  sort,
  onChange,
  listOpen,
  onListOpenChange,
  card,
  selectedId,
  onSelect,
  onBack,
  canLoadMore,
  onLoadMore,
}: {
  panelRef: RefObject<HTMLDivElement>;
  data: Schemas["SearchResponse"] | undefined;
  countLabel: string;
  sort: Sort;
  onChange: (patch: Partial<Filters>) => void;
  listOpen: boolean;
  onListOpenChange: (open: boolean) => void;
  /** Выбранный трек: вместо списка показывается его карточка. */
  card: TrackDetail | null;
  selectedId: string | null;
  onSelect: (id: string) => void;
  onBack: () => void;
  canLoadMore: boolean;
  onLoadMore: () => void;
}) {
  const { t } = useTranslation();
  return (
    <div className="map-panel__body" ref={panelRef}>
      <div className="list-head">
        <button
          type="button"
          className="sheet-toggle"
          aria-expanded={listOpen}
          onClick={() => onListOpenChange(!listOpen)}
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
            <select value={sort} onChange={(e) => onChange({ sort: e.target.value as Sort })}>
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
          <TrackCardPanel track={card} onBack={onBack} />
        ) : (
          <>
            {data && data.items.length === 0 && <div className="empty">{t("search.nothing")}</div>}
            {data && <ResultList items={data.items} selectedId={selectedId} onSelect={onSelect} />}
            {canLoadMore && (
              <button type="button" className="btn btn--secondary btn--block" onClick={onLoadMore}>
                {t("search.more")}
              </button>
            )}
          </>
        )}
      </div>
    </div>
  );
}
