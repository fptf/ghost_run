import { useState } from "react";
import { useTranslation } from "react-i18next";

import { CATEGORY_LABELS } from "../lib/format";
import { CATEGORIES } from "./params";
import type { Category, Filters } from "./params";

const RANGE_HINT: Record<Category, string> = {
  "1": "до 3 км",
  "5": "от 3 до 7,5 км",
  "10": "от 7,5 до 15 км",
  "21": "от 15 до 25 км",
  "21+": "от 25 км",
};

export function DistanceFilter({
  filters,
  onChange,
}: {
  filters: Filters;
  onChange: (patch: Partial<Filters>) => void;
}) {
  const { t } = useTranslation();
  const custom = filters.dmin !== null || filters.dmax !== null;
  const [customOpen, setCustomOpen] = useState(custom);
  const hint = filters.cat
    ? RANGE_HINT[filters.cat]
    : custom
      ? t("search.customRange", { min: filters.dmin ?? 0, max: filters.dmax ?? "∞" })
      : t("search.anyDistance");

  return (
    <div className="distance-filter">
      <div className="row-between">
        <span className="field__label">{t("search.distance")}</span>
        <span className="muted">{hint}</span>
      </div>
      <div className="chips" role="group" aria-label={t("search.distance")}>
        {CATEGORIES.map((c) => (
          <button
            key={c}
            type="button"
            className="chip"
            aria-pressed={filters.cat === c}
            aria-label={CATEGORY_LABELS[c]}
            onClick={() => onChange({ cat: filters.cat === c ? null : c, dmin: null, dmax: null })}
          >
            {c}
          </button>
        ))}
        <button
          type="button"
          className="chip"
          aria-pressed={customOpen}
          onClick={() => {
            if (customOpen) onChange({ dmin: null, dmax: null });
            setCustomOpen(!customOpen);
          }}
        >
          {t("search.custom")}
        </button>
      </div>
      {customOpen && (
        <div className="grid-2">
          <label className="field field--compact">
            {t("search.fromKm")}
            <input
              className="input input--sm"
              type="number"
              min={0}
              step={0.5}
              value={filters.dmin ?? ""}
              onChange={(e) =>
                onChange({ cat: null, dmin: e.target.value === "" ? null : Number(e.target.value) })
              }
            />
          </label>
          <label className="field field--compact">
            {t("search.toKm")}
            <input
              className="input input--sm"
              type="number"
              min={0}
              step={0.5}
              value={filters.dmax ?? ""}
              onChange={(e) =>
                onChange({ cat: null, dmax: e.target.value === "" ? null : Number(e.target.value) })
              }
            />
          </label>
        </div>
      )}
    </div>
  );
}
