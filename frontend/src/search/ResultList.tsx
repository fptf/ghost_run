import { useTranslation } from "react-i18next";

import type { Schemas } from "../api/client";
import { formatDuration, formatKm, formatPace } from "../lib/format";

type Item = Schemas["SearchItem"];

export function ResultList({
  items,
  selectedId,
  onSelect,
}: {
  items: Item[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}) {
  const { t } = useTranslation();
  return (
    <ul className="result-list">
      {items.map((it) => (
        <li key={it.id}>
          <button
            type="button"
            className="result"
            aria-current={it.id === selectedId}
            onClick={() => onSelect(it.id)}
          >
            <strong className="result__title">{it.title ?? t("track.untitled")}</strong>
            <span className="result__meta">
              {formatKm(it.distance_m)} км · {formatDuration(it.total_time_s)} ·{" "}
              {formatPace(it.avg_pace_s_per_km)} /км
            </span>
            <span className="result__group">
              {it.runners_count > 1
                ? t("search.runners", { count: it.runners_count })
                : t("search.onlyAuthor")}
            </span>
          </button>
        </li>
      ))}
    </ul>
  );
}
